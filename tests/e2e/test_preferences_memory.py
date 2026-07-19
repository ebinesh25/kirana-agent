"""E2E tests: preferences persist across /new chat via real Gemini."""

import pytest
from kirana.agent.loop import handle_message, clear_session
from kirana.repo import preference_repo


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_preference_survives_new_chat(agent_session):
    chat_id = agent_session

    r1 = await handle_message(chat_id, "set default payment to UPI")
    assert r1["text"]

    if not any("upi" in v.lower() for v in preference_repo.get_all().values()):
        await handle_message(chat_id, "remember: always assume UPI for payments")
        await handle_message(chat_id, "set preference default_payment_mode to UPI")

    await clear_session(chat_id)

    result = await handle_message(chat_id, "make a bill with 2 Maggi")
    assert result["text"]

    prefs = preference_repo.get_all()
    assert prefs, "No preferences found"
    assert any("upi" in v.lower() for v in prefs.values()), f"No UPI in prefs: {prefs}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_shop_name_preference(agent_session):
    chat_id = agent_session

    await handle_message(chat_id, 'set shop name to "My Kirana"')

    prefs = preference_repo.get_all()
    if "shop_name" not in prefs:
        await handle_message(chat_id, "remember: shop name is My Kirana")
    prefs = preference_repo.get_all()
    assert "shop_name" in prefs
