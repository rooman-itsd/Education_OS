import os
import tempfile
from pathlib import Path

# Before eos_core.db is imported: its engine is built at import time from the setting.
os.environ.setdefault("EOS_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/event-bus-test.db")
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[4]))

import pytest
from eos_core.db import SessionLocal, init_db
from eos_core.events import OutboxEvent
from eos_core.tenant import platform_scope
from sqlalchemy import delete


@pytest.fixture(scope="session", autouse=True)
def _tables():
    """The module alone: the outbox plus identity's users (a declared dependency, for the API's tokens)."""
    init_db()


@pytest.fixture(autouse=True)
def _clean():
    """The relay claims across every organisation, so a row left by one test must not reach the next."""
    with platform_scope(), SessionLocal() as s:
        if s.get_bind().dialect.name != "sqlite":
            pytest.exit("event-bus tests delete every outbox row; they run on SQLite only")
        s.execute(delete(OutboxEvent))
        s.commit()


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("EVENT_BUS_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
