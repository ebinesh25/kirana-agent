"""E2E test fixtures — shared session-level DB setup + clean agent sessions.

These tests use the real Gemini API (not mocked) and a dedicated test database.
Run with: pytest -m e2e -v --timeout=60
"""

import os
import random

import pytest
import pytest_asyncio

from kirana.db.connection import init_db, seed_db, engine, get_session
from kirana.db.models import Base
from sqlalchemy import text


TABLE_ORDER = [
    "bill_items",
    "bills",
    "khata_transactions",
    "khata_customers",
    "stock_movements",
    "chat_state",
    "processed_updates",
    "owner_preferences",
    "products",
]


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Set up test database once per session: create tables, seed data."""
    init_db()
    seed_db()
    yield
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = OFF"))
        for table in TABLE_ORDER:
            conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
        conn.commit()


@pytest_asyncio.fixture
async def agent_session():
    """Provide a clean agent session for each E2E test."""
    from kirana.agent.loop import clear_session

    chat_id = f"e2e-test-{random.randint(10000, 99999)}"
    yield chat_id
    await clear_session(chat_id)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "e2e: end-to-end tests with real Gemini API calls (slow, costs money)",
    )
