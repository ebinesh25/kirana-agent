import pytest
from dotenv import load_dotenv

load_dotenv(".env.test")

from kirana.db.connection import seed_db
from kirana.db.models import Base
from kirana.db.connection import engine
from sqlalchemy import text


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
