"""Thread-safe context for passing chat_id to tools."""
import contextvars

_current_chat_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_chat_id")


def get_current_chat_id() -> str:
    try:
        return _current_chat_id.get()
    except LookupError:
        return "test"


def set_current_chat_id(chat_id: str):
    _current_chat_id.set(chat_id)
