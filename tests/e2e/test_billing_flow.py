"""E2E tests: multi-turn billing, edits, and oversell guard via real Gemini."""

import pytest
from kirana.agent.loop import handle_message
from kirana.repo import product_repo


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_multi_turn_bill_with_edit(agent_session):
    chat_id = agent_session

    r1 = await handle_message(chat_id, "create a new bill")
    assert r1["text"]

    r2 = await handle_message(chat_id, "add 2kg sugar, 4 Maggi, 1 Amul butter")
    assert r2["text"]

    r3 = await handle_message(chat_id, "drop the butter, make it 6 Maggi")
    assert r3["text"]

    r4 = await handle_message(chat_id, "finalize with UPI")
    assert r4["text"]

    stock = product_repo.get_by_id(5)
    assert stock["quantity"] < 48


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_oversell_guard_e2e(agent_session):
    chat_id = agent_session

    await handle_message(chat_id, "create a bill")
    await handle_message(chat_id, "add 1000 Maggi")
    r1 = await handle_message(chat_id, "finalize with cash")
    assert r1["text"]

    if "payment mode" in r1["text"].lower() or "specify" in r1["text"].lower():
        r1 = await handle_message(chat_id, "cash")

    stock = product_repo.get_by_id(5)
    assert stock["quantity"] == 48


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_bill_cancel(agent_session):
    chat_id = agent_session

    await handle_message(chat_id, "create a new bill")
    await handle_message(chat_id, "add 2 Maggi")
    result = await handle_message(chat_id, "cancel this bill")
    assert result["text"]
    assert any(word in result["text"].lower() for word in ["cancel", "discard", "cancelled"])

    stock = product_repo.get_by_id(5)
    assert stock["quantity"] == 48
