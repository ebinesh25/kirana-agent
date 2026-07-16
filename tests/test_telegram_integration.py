"""Tests for Telegram bot integration handlers.

Uses unittest.mock to test handler logic without hitting Telegram API.
"""

from unittest.mock import AsyncMock, Mock, patch, call, mock_open, ANY
import pytest
from kirana.bot.telegram_bot import start, new_chat, handle_text


def _make_update(update_id=1, text="hello", chat_id="12345"):
    update = Mock()
    update.update_id = update_id
    update.effective_chat.id = chat_id
    update.message.text = text
    return update


def _make_context():
    ctx = Mock()
    placeholder = AsyncMock()
    placeholder.edit_text = AsyncMock()
    placeholder.message_id = 99
    ctx.bot.send_message = AsyncMock(return_value=placeholder)
    ctx.bot.send_chat_action = AsyncMock()
    ctx.bot.send_document = AsyncMock()
    ctx.bot.delete_message = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_start_sends_welcome():
    update = _make_update()
    context = _make_context()
    await start(update, context)
    context.bot.send_message.assert_awaited_once()
    args = context.bot.send_message.await_args
    assert "Namaste" in args.kwargs["text"]


@pytest.mark.asyncio
async def test_new_chat_clears_session():
    update = _make_update()
    context = _make_context()
    with patch("kirana.bot.telegram_bot.clear_session", AsyncMock()) as mock_clear:
        await new_chat(update, context)
        mock_clear.assert_awaited_once_with("12345")
    context.bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_idempotency_skips_duplicate():
    update = _make_update(update_id=42)
    context = _make_context()

    with (
        patch("kirana.bot.telegram_bot.processed_updates_repo.is_processed", return_value=True) as mock_check,
        patch("kirana.bot.telegram_bot.handle_message", AsyncMock()) as mock_handle,
    ):
        await handle_text(update, context)

    mock_check.assert_called_once_with(42)
    mock_handle.assert_not_awaited()
    context.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_text_message_routes_to_agent():
    update = _make_update(text="how much sugar?")
    context = _make_context()

    with (
        patch("kirana.bot.telegram_bot.processed_updates_repo.is_processed", return_value=False),
        patch("kirana.bot.telegram_bot.processed_updates_repo.mark_processed"),
        patch("kirana.bot.telegram_bot.handle_message", AsyncMock(return_value={"text": "42 kg left.", "suggestions": []})) as mock_handle,
    ):
        await handle_text(update, context)

    mock_handle.assert_awaited_once_with("12345", "how much sugar?")
    context.bot.send_message.assert_awaited_once()
    placeholder = context.bot.send_message.await_args.kwargs["text"]
    assert "⏳" in placeholder
    # Placeholder edited with real response
    placeholder_msg = context.bot.send_message.return_value
    placeholder_msg.edit_text.assert_awaited_once_with("42 kg left.", reply_markup=None)


@pytest.mark.asyncio
async def test_file_response_sent_as_document():
    update = _make_update(text="send invoice")
    context = _make_context()

    with (
        patch("kirana.bot.telegram_bot.processed_updates_repo.is_processed", return_value=False),
        patch("kirana.bot.telegram_bot.processed_updates_repo.mark_processed"),
        patch("kirana.bot.telegram_bot.handle_message", AsyncMock(return_value={
            "text": "Invoice ready",
            "files": ["/tmp/invoice_INV-0001.pdf"],
        })),
        patch("builtins.open", mock_open(read_data=b"pdf content")),
    ):
        await handle_text(update, context)

    context.bot.send_document.assert_awaited_once()
    args = context.bot.send_document.await_args
    assert args.kwargs["filename"] == "invoice_INV-0001.pdf"


@pytest.mark.asyncio
async def test_error_handling():
    update = _make_update(text="do something")
    context = _make_context()

    with (
        patch("kirana.bot.telegram_bot.processed_updates_repo.is_processed", return_value=False),
        patch("kirana.bot.telegram_bot.processed_updates_repo.mark_processed"),
        patch("kirana.bot.telegram_bot.handle_message", AsyncMock(side_effect=Exception("boom"))),
    ):
        await handle_text(update, context)

    context.bot.send_message.assert_awaited_once()
    placeholder_msg = context.bot.send_message.return_value
    placeholder_msg.edit_text.assert_awaited_once()
    err_text = placeholder_msg.edit_text.await_args[0][0]
    assert "wrong" in err_text


@pytest.mark.asyncio
async def test_long_response_split():
    update = _make_update(text="get summary")
    context = _make_context()
    long_text = "x" * 5000

    with (
        patch("kirana.bot.telegram_bot.processed_updates_repo.is_processed", return_value=False),
        patch("kirana.bot.telegram_bot.processed_updates_repo.mark_processed"),
        patch("kirana.bot.telegram_bot.handle_message", AsyncMock(return_value={"text": long_text, "suggestions": []})),
    ):
        await handle_text(update, context)

    # Placeholder + 2 split chunks = 3 calls
    assert context.bot.send_message.await_count == 3
    # First call is placeholder
    placeholder_text = context.bot.send_message.await_args_list[0].kwargs["text"]
    assert "⏳" in placeholder_text
    # Second and third calls are split text chunks
    chunk1 = context.bot.send_message.await_args_list[1].kwargs["text"]
    chunk2 = context.bot.send_message.await_args_list[2].kwargs["text"]
    assert len(chunk1) == 4096
    assert len(chunk2) == 5000 - 4096
    # Delete called on placeholder
    context.bot.delete_message.assert_awaited_once()
