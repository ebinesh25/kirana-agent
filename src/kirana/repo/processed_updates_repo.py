"""Repository for Telegram update idempotency.

Stores processed update IDs so redelivered updates are safely skipped.
"""

from kirana.db.connection import get_session
from kirana.db.models import ProcessedUpdate


def is_processed(update_id: int) -> bool:
    with get_session() as session:
        return session.query(ProcessedUpdate).filter(
            ProcessedUpdate.telegram_update_id == update_id
        ).first() is not None


def mark_processed(update_id: int):
    with get_session() as session:
        session.add(ProcessedUpdate(telegram_update_id=update_id))
        session.flush()
