"""Telegram bot — webhook mode for Cloud Run scale-to-zero.

Routes /start, /new, and text messages through the ADK agent loop.
Runs as an aiohttp server handling Telegram webhook POSTs, health checks, and
a browser-friendly dashboard — all on a single port.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from kirana.agent.loop import handle_message, clear_session
from kirana.repo import processed_updates_repo
from kirana.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_start_time = datetime.now(timezone.utc)

# ──────────────────────────────────────────────
# PTB Application (built once, shared)
# ──────────────────────────────────────────────

_app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()


# ──────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────

async def _keep_typing(chat_id: str, context, stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=4)
        except asyncio.TimeoutError:
            continue


async def _send_or_split(bot, chat_id: int, text: str):
    """Send a message, splitting at 4096 if needed."""
    if len(text) <= 4096:
        await bot.send_message(chat_id=chat_id, text=text)
    else:
        for i in range(0, len(text), 4096):
            await bot.send_message(chat_id=chat_id, text=text[i:i + 4096])


async def _send_files(bot, chat_id: int, file_paths: list[str]):
    """Send each generated file as a Telegram document."""
    for fp in file_paths:
        try:
            with open(fp, "rb") as f:
                await bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename=fp.split("/")[-1],
                )
        except Exception as e:
            logger.error("Failed to send file %s: %s", fp, e)


# ──────────────────────────────────────────────
# PTB Handlers
# ──────────────────────────────────────────────

def _build_app():
    _app.add_handler(CommandHandler("start", _start))
    _app.add_handler(CommandHandler("new", _new_chat))
    _app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text))


async def _start(update: Update, context):
    chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "Namaste! I'm your kirana store assistant.\n\n"
            "I can help you:\n"
            "• Receive stock — '50 Maggi came in, cost ₹12'\n"
            "• Cut bills — 'bill: 2kg sugar, 4 Maggi, UPI'\n"
            "• Check stock — 'how much sugar is left?'\n"
            "• Manage credit — 'put ₹500 on Ramesh's credit'\n"
            "• Close the day — 'today's sales?'\n"
            "• Generate invoices (PDF) and analysis decks (PPTX)\n"
            "• Remember preferences — 'always assume UPI'\n\n"
            "Just tell me what you need in plain language!"
        ),
    )


async def _new_chat(update: Update, context):
    chat_id = str(update.effective_chat.id)
    await clear_session(chat_id)
    await context.bot.send_message(
        chat_id=chat_id,
        text="Started a new chat. Your preferences and store data are still active.",
    )


async def _handle_text(update: Update, context):
    chat_id_int = update.effective_chat.id
    chat_id_str = str(chat_id_int)
    update_id = update.update_id

    if processed_updates_repo.is_processed(update_id):
        logger.info("Skipping already-processed update %s", update_id)
        return
    processed_updates_repo.mark_processed(update_id)

    # ── Placeholder — user sees this immediately ──
    placeholder = await context.bot.send_message(
        chat_id=chat_id_int,
        text="⏳ Give me a moment...",
    )

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        _keep_typing(chat_id_str, context, stop_typing)
    )

    try:
        result = await handle_message(chat_id_str, update.message.text)
    except Exception as e:
        stop_typing.set()
        await typing_task
        logger.error("Agent error: %s", e, exc_info=True)
        await placeholder.edit_text("Sorry, something went wrong. Please try again.")
        return
    finally:
        stop_typing.set()
        await typing_task

    text = result.get("text", "")

    # Replace placeholder with real response
    if text:
        if len(text) <= 4096:
            await placeholder.edit_text(text)
        else:
            # edit_text limit is 4096 — delete placeholder, send fresh
            await context.bot.delete_message(
                chat_id=chat_id_int, message_id=placeholder.message_id
            )
            await _send_or_split(context.bot, chat_id_int, text)

    # Send files (PDF/PPTX)
    await _send_files(context.bot, chat_id_int, result.get("files", []))


# ──────────────────────────────────────────────
# aiohttp routes
# ──────────────────────────────────────────────

async def _health_get(request):
    uptime = datetime.now(timezone.utc) - _start_time
    return web.json_response({
        "status": "ok",
        "service": "kirana-agent",
        "uptime": str(uptime).split(".")[0],
        "webhook": f"/{settings.WEBHOOK_PATH}",
    })


async def _index_get(request):
    uptime = datetime.now(timezone.utc) - _start_time
    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Kirana Agent</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 640px; margin: 40px auto; padding: 0 20px; }}
  .ok {{ color: #2e7d32; }} h1 {{ font-size: 1.8rem; }}
  .card {{ background: #f5f5f5; border-radius: 12px; padding: 20px; margin: 16px 0; }}
  .label {{ color: #666; font-size: 0.85rem; }}
</style></head>
<body>
<h1>Kirana Agent <span class="ok">✅</span></h1>
<div class="card">
  <div class="label">Status</div><div>Running</div>
  <div class="label" style="margin-top:8px">Uptime</div><div>{str(uptime).split('.')[0]}</div>
  <div class="label" style="margin-top:8px">Service</div><div>kirana-agent-bot</div>
</div>
</body></html>"""
    return web.Response(text=html, content_type="text/html")


async def _webhook_post(request):
    data = await request.json()
    update = Update.de_json(data, _app.bot)
    await _app.process_update(update)
    return web.Response(text="ok")


# ──────────────────────────────────────────────
# Server lifecycle
# ──────────────────────────────────────────────

async def _register_webhook():
    """Auto-register the Telegram webhook on startup if SERVICE_URL is set."""
    if settings.SERVICE_URL:
        url = f"{settings.SERVICE_URL}/{settings.WEBHOOK_PATH}"
        await _app.bot.set_webhook(url=url)
        logger.info("Telegram webhook registered: %s", url)


def main():
    """Entry point: build PTB app, start aiohttp server, run forever."""
    _build_app()

    async def _run():
        await _app.initialize()
        await _app.start()
        await _register_webhook()

        web_app = web.Application()
        web_app.router.add_get("/", _index_get)
        web_app.router.add_get(f"/{settings.HEALTH_PATH}", _health_get)
        web_app.router.add_post(f"/{settings.WEBHOOK_PATH}", _webhook_post)

        port = int(os.getenv("PORT", "8080"))
        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()

        logger.info("Bot started in webhook mode on port %s", port)

        # Run forever
        await asyncio.Event().wait()

    asyncio.run(_run())


# Public aliases for PTB handler registration (kept for test imports)
start = _start
new_chat = _new_chat
handle_text = _handle_text

if __name__ == "__main__":
    main()
