"""Memory/preferences tools for Phase 4.

Simple key-value store for owner preferences (shop name, GSTIN, phone, etc.).
Values persist in `owner_preferences` table.
"""

from kirana.repo import preference_repo
from kirana.db.connection import get_session
from kirana.db.models import OwnerPreference


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def set_preference(key: str, value: str) -> dict:
    """Set or update an owner preference.

    Preferences are key-value pairs that persist across conversations.
    Examples: shop_name, shop_address, owner_phone, gstin, receipt_note.

    Args:
        key: Preference key (lowercase recommended, e.g. 'shop_name')
        value: Preference value as string
    """
    result = preference_repo.set(key, value)
    return {
        "preference": result,
        "message": f"Preference '{key}' set to '{value}'.",
    }


def get_preferences() -> dict:
    """Get all stored owner preferences.

    Returns the full dict of key-value pairs.
    """
    prefs = preference_repo.get_all()
    if not prefs:
        return {
            "preferences": {},
            "count": 0,
            "message": "No preferences set yet. Use set_preference to add them.",
        }

    items = "\n".join(f"{k}: {v}" for k, v in sorted(prefs.items()))
    return {
        "preferences": prefs,
        "count": len(prefs),
        "message": f"{len(prefs)} preference(s):\n{items}",
    }


def delete_preference(key: str) -> dict:
    """Delete a stored preference by key.

    Args:
        key: Preference key to delete
    """
    with get_session() as session:
        pref = session.query(OwnerPreference).filter(OwnerPreference.key == key).first()
        if not pref:
            return {"error": f"Preference '{key}' not found."}
        session.delete(pref)
        session.flush()

    return {
        "message": f"Preference '{key}' deleted.",
    }
