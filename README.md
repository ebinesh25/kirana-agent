# Kirana Agent — Run a kirana store from Telegram

**Bot:** @your_bot_username (live on GCP Cloud Run)

Conversational agent that operates an Indian kirana store end-to-end through Telegram — stock management, billing, khata credit, invoices, and analytics. All in plain language.

## Harness choice: Google ADK + Gemini

I picked Google ADK because tools are plain Python functions with type hints — ADK auto-generates tool schemas from the function signatures, so there's no separate JSON schema to maintain. The ADK Runner handles the observe→reason→act→feed-back→continue loop natively. Gemini 2.5 Flash provides fast tool-use reasoning. ADK has native GCP Cloud Run deployment support via `gcloud run deploy`.

## How the control loop works

Each Telegram message enters the bot handler, which loads preferences + active bill from Supabase, injects them into the ADK Agent context, then calls `Runner.run_async()`. Gemini reasons over the conversation + injected data and calls tools as needed. The response is split if >4096 chars and sent back. `/new` clears the ADK session but preferences persist in Supabase.

## Skill / tool design

6 skill groups, ~22 thin tools. The model composes them. Business rules live in tools, not in the prompt.

| Skill | Tools | Purpose |
|-------|-------|---------|
| Inventory | search_products, add_product, receive_stock, get_stock, get_low_stock, adjust_stock | Stock management |
| Billing | create_bill, add_item, update_item, remove_item, get_bill, finalize_bill, cancel_bill | Multi-turn billing |
| Khata | get_or_create_customer, add_credit, settle_credit, get_balance, list_khata | Credit ledger |
| Analytics | get_daily_summary, get_sales_analysis, get_inventory_value | Reports |
| Documents | generate_invoice_pdf, generate_analysis_pptx | Real PDF/PPTX artifacts |
| Memory | set_preference, get_preferences, delete_preference | Cross-session memory |

## How I solved the hard parts

1. **Grounding:** Prices and stock quantities come from Supabase via tools — never from the model's memory.
2. **Oversell guard:** `SELECT ... FOR UPDATE` row locking in `finalize_bill` — aborts the transaction if stock is insufficient.
3. **GST correctness:** Per-item slab lookup (0%/5%/12%/18%/28%), CGST/SGST split, all values in paise integers, proper rounding.
4. **Multi-turn bills:** Draft bills live in the DB — items are added/updated/removed across turns. Stock is only deducted on `finalize_bill`.
5. **Idempotency:** `processed_updates` table prevents duplicate Telegram webhook processing. `finalize_bill` uses an idempotency key so retries don't double-charge.
6. **Concurrency:** Postgres `SELECT ... FOR UPDATE` row-level locking handles concurrent requests in production (Supabase).
7. **Guardrails:** Sell price must be ≥ cost price. No stock deletion (only adjustment). Khata customer must exist before adding credit.
8. **Real artifacts:** WeasyPrint generates proper PDF invoices with Tamil text support. python-pptx + matplotlib generate analysis decks with charts.
9. **Memory across sessions:** User preferences are stored in Supabase and loaded on every turn — they survive `/new` and Telegram's webhook cycle.

## Tech stack

- Python 3.12 + Google ADK + Gemini 2.5 Flash
- Supabase (Postgres) + SQLAlchemy 2.0
- python-telegram-bot + aiohttp (webhook)
- WeasyPrint (PDF) + python-pptx + matplotlib (PPTX)
- GCP Cloud Run + GitHub Actions CI/CD
- pytest + pytest-asyncio (148 unit + 15 E2E tests)

## Running locally

Bot runs in webhook mode everywhere. Telegram needs a public HTTPS URL to push updates. Use a tunnel to expose localhost:

### With ngrok

```bash
# Terminal 1 — tunnel
ngrok http 8080
# → https://abc123.ngrok.app

# Terminal 2 — bot
cd kirana-agent
cp .env.example .env  # set GOOGLE_API_KEY, TELEGRAM_BOT_TOKEN, DATABASE_URL
SERVICE_URL=https://abc123.ngrok.app python -m kirana.bot.telegram_bot
```

### With Cloudflare Tunnel

```bash
# Terminal 1 — tunnel
cloudflared tunnel --url http://localhost:8080
# → https://random-name.trycloudflare.com

# Terminal 2 — bot
SERVICE_URL=https://random-name.trycloudflare.com python -m kirana.bot.telegram_bot
```

On startup, bot calls `setWebhook` with `SERVICE_URL` — Telegram pushes all messages through the tunnel to your machine.

### Verify

```bash
curl http://localhost:8080/health
curl https://your-tunnel-url.ngrok.app/health
```

### CLI test harness (no Telegram)

```bash
python -m kirana.agent.cli
```

## Project structure

```
src/kirana/
  db/          # SQLAlchemy models, engine, session
  repo/        # Data access layer (products, bills, khata, etc.)
  tools/       # Tool groups: inventory, billing, khata, analytics, documents, memory
  agent/       # ADK Agent builder + async loop + CLI
  bot/         # Telegram bot (webhook / aiohttp server)
  config.py    # Env-based configuration
```
