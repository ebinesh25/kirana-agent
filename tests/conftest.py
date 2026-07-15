import os
import pytest
from dotenv import load_dotenv

load_dotenv(".env.test")

from kirana.db.connection import init_db, seed_db, get_session
from kirana.db.models import Base
from kirana.db.connection import engine


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(engine)
    seed_db()
    yield
    Base.metadata.drop_all(engine)
