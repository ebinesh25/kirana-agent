"""Telegram bot integration for the Kirana agent.

Long-polling bot. Routes /start, /new, and text messages through the ADK agent loop.
Handles idempotency, error recovery, and file delivery.
"""

import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from kirana.agent.loop import handle_message, clear_session
from kirana.repo import processed_updates_repo
from kirana.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


async def start(update: Update, context):
    chat_id = str(update.effective_chat.id)
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


async def new_chat(update: Update, context):
    chat_id = str(update.effective_chat.id)
    await clear_session(chat_id)
    await context.bot.send_message(
        chat_id=chat_id,
        text="Started a new chat. Your preferences and store data are still active.",
    )


async def handle_text(update: Update, context):
    chat_id = str(update.effective_chat.id)
    update_id = update.update_id

    if processed_updates_repo.is_processed(update_id):
        logger.info("Skipping already-processed update %s", update_id)
        return
    processed_updates_repo.mark_processed(update_id)

    user_message = update.message.text

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(chat_id, context, stop_typing))

    try:
        result = await handle_message(chat_id, user_message)
    except Exception as e:
        stop_typing.set()
        await typing_task
        logger.error("Agent error: %s", e, exc_info=True)
        await context.bot.send_message(
            chat_id=chat_id,
            text="Sorry, something went wrong. Please try again.",
        )
        return
    finally:
        stop_typing.set()
        await typing_task

    if result.get("text"):
        text = result["text"]
        if len(text) <= 4096:
            await context.bot.send_message(chat_id=chat_id, text=text)
        else:
            for i in range(0, len(text), 4096):
                await context.bot.send_message(chat_id=chat_id, text=text[i:i+4096])

    for file_path in result.get("files", []):
        with open(file_path, "rb") as f:
            await context.bot.send_document(
                chat_id=chat_id,
                document=f,
                filename=file_path.split("/")[-1],
            )


def main():
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_chat))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot starting with long polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
