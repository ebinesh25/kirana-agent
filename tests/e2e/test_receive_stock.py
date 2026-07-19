"""E2E tests: receive stock flow via real Gemini orchestration."""

import pytest
from kirana.agent.loop import handle_message
from kirana.repo import product_repo


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_receive_stock_maggi(agent_session):
    chat_id = agent_session
    result = await handle_message(
        chat_id,
        "50 packets of Maggi Noodles came in, cost ₹12, MRP ₹14",
    )
    assert result["text"]
    assert any(word in result["text"].lower() for word in ["maggi", "stock", "50"])

    products = product_repo.search("Maggi")
    assert products
    maggi = products[0]
    assert maggi["quantity"] >= 98
