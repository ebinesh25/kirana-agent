import pytest
from dotenv import load_dotenv

load_dotenv(".env.test")

from kirana.db.connection import seed_db  # noqa: E402
from kirana.db.models import Base  # noqa: E402
from kirana.db.connection import engine  # noqa: E402
from sqlalchemy import text  # noqa: E402


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(engine)
    seed_db()
    yield
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = OFF"))
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"DROP TABLE IF EXISTS {table.name}"))
        conn.commit()
