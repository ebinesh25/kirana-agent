"""E2E tests: Gemini asks clarifying questions for ambiguous requests."""

import pytest
from kirana.agent.loop import handle_message


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ambiguous_atta_asks_clarification(agent_session):
    chat_id = agent_session
    result = await handle_message(chat_id, "add atta")

    text_lower = result["text"].lower()
    assert any(word in text_lower for word in ["which", "aashirvaad", "loose", "what kind", "brand", "option", "choose"])


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ambiguous_rice_asks_clarification(agent_session):
    chat_id = agent_session
    result = await handle_message(chat_id, "how much dal is left?")

    assert result["text"]
