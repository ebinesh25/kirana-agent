"""E2E tests: khata credit cycle via real Gemini."""

import pytest
from kirana.agent.loop import handle_message
from kirana.repo import khata_repo


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_khata_cycle(agent_session):
    chat_id = agent_session

    await handle_message(chat_id, "create a khata customer named Ramesh")

    customer = khata_repo.get_customer("Ramesh")
    if not customer:
        await handle_message(chat_id, "add a new khata customer: Ramesh")

    customer = khata_repo.get_customer("Ramesh")
    assert customer, "Ramesh was not created as a khata customer"

    r1 = await handle_message(chat_id, "put ₹500 on Ramesh's credit")
    assert r1["text"]
    assert "500" in r1["text"]

    r2 = await handle_message(chat_id, "Ramesh's balance?")
    assert r2["text"]
    assert "500" in r2["text"]

    r3 = await handle_message(chat_id, "Ramesh paid ₹300")
    assert r3["text"]
    assert any(w in r3["text"] for w in ["200", "settled", "paid"])


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_khata_unknown_customer(agent_session):
    chat_id = agent_session
    result = await handle_message(chat_id, "balance of nonexistentperson?")
    assert result["text"]
