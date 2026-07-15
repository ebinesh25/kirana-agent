"""E2E tests: daily close and stock query via real Gemini."""

import pytest
from kirana.agent.loop import handle_message


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_daily_close(agent_session):
    chat_id = agent_session

    await handle_message(chat_id, "create a new bill")
    await handle_message(chat_id, "add 2 Maggi")
    await handle_message(chat_id, "finalize with UPI")

    result = await handle_message(chat_id, "today's sales?")
    assert result["text"]
    assert "₹" in result["text"] or "total" in result["text"].lower()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_stock_query(agent_session):
    chat_id = agent_session
    result = await handle_message(chat_id, "how much sugar is left?")
    assert result["text"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_low_stock_query(agent_session):
    chat_id = agent_session
    result = await handle_message(chat_id, "which products have low stock?")
    if not result["text"]:
        result = await handle_message(chat_id, "check low stock")
    assert result["text"]
