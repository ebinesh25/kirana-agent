"""ADK control loop — Gemini orchestrates tools per user message.

Observe → reason → act (call tool) → feed result back → continue
until Gemini produces a final answer.
"""

import asyncio
import json
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

from kirana.repo import preference_repo, bill_repo
from kirana.agent.agent import build_agent
from kirana.agent.context import get_current_chat_id, set_current_chat_id

session_service = InMemorySessionService()
APP_NAME = "kirana_store"


def format_preferences(prefs: dict) -> str:
    if not prefs:
        return "None set."
    return ", ".join(f"{k}={v}" for k, v in prefs.items())


def format_active_bill(bill: dict | None) -> str:
    if not bill:
        return "None (no active draft bill)."
    items = ", ".join(
        f"{i['quantity']}× {i['product_name_snapshot']}" for i in bill.get("items", [])
    )
    return f"Draft {bill['bill_number']}: {items}"


def _extract_file_paths(events: list) -> list[str]:
    """Scan tool results for file_path keys (from PDF/PPTX generation)."""
    files = []
    for event in events:
        for func_resp in event.get_function_responses():
            resp = func_resp.response
            if isinstance(resp, dict):
                if "file_path" in resp:
                    files.append(resp["file_path"])
            elif isinstance(resp, str):
                try:
                    data = json.loads(resp)
                    if "file_path" in data:
                        files.append(data["file_path"])
                except (json.JSONDecodeError, TypeError):
                    pass
    return files


async def handle_message(chat_id: str, user_message: str) -> dict:
    """Process one user message through the ADK + Gemini agent loop.

    Reuses existing ADK session per chat_id so Gemini remembers context.
    Returns {"text": ..., "files": [...]}.
    """
    set_current_chat_id(chat_id)

    prefs = preference_repo.get_all()
    prefs_text = format_preferences(prefs)

    active_bill = bill_repo.get_active_bill(chat_id)
    active_bill_text = format_active_bill(active_bill)

    agent = build_agent(prefs_text, active_bill_text)

    runner = Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    resp = await session_service.list_sessions(
        app_name=APP_NAME,
        user_id=chat_id,
    )
    existing = resp.sessions
    if existing:
        session = existing[-1]
    else:
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=chat_id,
        )

    user_content = Content(
        role="user",
        parts=[Part(text=user_message)],
    )

    response_text = ""
    all_events = []

    async for event in runner.run_async(
        user_id=chat_id,
        session_id=session.id,
        new_message=user_content,
    ):
        all_events.append(event)
        if event.is_final_response():
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text

    files = _extract_file_paths(all_events)

    from kirana.tools.suggestions import get_suggestions, clear_suggestions
    suggestions = get_suggestions(chat_id)
    clear_suggestions(chat_id)

    return {"text": response_text, "files": files, "suggestions": suggestions}


async def clear_session(chat_id: str):
    """Clear ADK conversation for /new chat — preferences persist in DB."""
    resp = await session_service.list_sessions(
        app_name=APP_NAME,
        user_id=chat_id,
    )
    for s in resp.sessions:
        await session_service.delete_session(
            app_name=APP_NAME,
            user_id=chat_id,
            session_id=s.id,
        )
