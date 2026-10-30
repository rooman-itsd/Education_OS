import os
import tempfile
from pathlib import Path

# Before eos_core.db is imported: its engine is built at import time from the setting.
os.environ.setdefault("EOS_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/scheduler-test.db")
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[4]))

import pytest
from eos_core.db import SessionLocal, init_db
from eos_core.events import OutboxEvent
from eos_core.tenant import platform_scope
from eos_scheduler.domain.models import Run, Schedule
from sqlalchemy import delete


@pytest.fixture(scope="session", autouse=True)
def _tables():
    init_db()


@pytest.fixture(autouse=True)
def _clean():
    """The tick fires every organisation's schedules, so a row left by one test must not reach the next."""
    with platform_scope(), SessionLocal() as s:
        if s.get_bind().dialect.name != "sqlite":
            pytest.exit("scheduler tests delete every schedule; they run on SQLite only")
        for table in (Run, Schedule, OutboxEvent):
            s.execute(delete(table))
        s.commit()


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("SCHEDULER_"):
            monkeypatch.delenv(key, raising=False)
