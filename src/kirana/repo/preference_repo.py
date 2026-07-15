from kirana.db.connection import get_session
from kirana.db.models import OwnerPreference


def set(key: str, value: str) -> dict:
    with get_session() as session:
        pref = session.query(OwnerPreference).filter(OwnerPreference.key == key).first()
        if pref:
            pref.value = value
        else:
            pref = OwnerPreference(key=key, value=value)
            session.add(pref)
        session.flush()
        return {"key": pref.key, "value": pref.value}


def get(key: str) -> str | None:
    with get_session() as session:
        pref = session.query(OwnerPreference).filter(OwnerPreference.key == key).first()
        return pref.value if pref else None


def get_all() -> dict[str, str]:
    with get_session() as session:
        prefs = session.query(OwnerPreference).all()
        return {p.key: p.value for p in prefs}
