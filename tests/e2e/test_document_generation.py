"""E2E tests: PDF invoice and PPTX deck generation via real Gemini."""

import os
import pytest
from kirana.agent.loop import handle_message


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_pdf_invoice_generation(agent_session):
    chat_id = agent_session

    await handle_message(chat_id, "create a new bill")
    await handle_message(chat_id, "add 2 Maggi")
    await handle_message(chat_id, "finalize with UPI")

    result = await handle_message(chat_id, "generate PDF for the last bill")
    if not result.get("files"):
        result = await handle_message(chat_id, "send me that bill as a PDF")
    assert result.get("files"), "Expected at least one generated file"
    assert result["files"][0].endswith(".pdf")
    assert os.path.exists(result["files"][0])
    assert os.path.getsize(result["files"][0]) > 0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_pptx_deck_generation(agent_session):
    chat_id = agent_session

    result = await handle_message(chat_id, "make this week's sales analysis deck")
    assert result.get("files") is not None

    if result["files"]:
        assert result["files"][0].endswith(".pptx")
        assert os.path.exists(result["files"][0])
        assert os.path.getsize(result["files"][0]) > 0
