"""Suggestions tool — lets the agent offer clickable option buttons.

The agent calls `suggest_options()` when asking a question with specific
possible answers. The Telegram bot renders these as inline keyboard buttons.
Users can tap a button or type their own answer.
"""

from kirana.agent.context import get_current_chat_id

_suggestions_store: dict[str, list[str]] = {}


def suggest_options(options: list[str]) -> dict:
    """Suggest clickable answer options for the user.

    Call this when asking a question where the user might want to pick from
    predefined answers instead of typing. The options become buttons in
    Telegram. Users can still type a custom answer.

    Args:
        options: List of answer choices, e.g. ['Pack size', 'Stock quantity']
    """
    if not options:
        return {"error": "At least one option is required.", "options": []}

    chat_id = get_current_chat_id()
    _suggestions_store[chat_id] = options
    return {
        "message": f"Options set: {options}",
        "options": options,
    }


def get_suggestions(chat_id: str) -> list[str]:
    return _suggestions_store.get(chat_id, [])


def clear_suggestions(chat_id: str):
    _suggestions_store.pop(chat_id, None)
