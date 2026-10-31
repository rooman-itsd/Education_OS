import logging
import os
import tempfile
from pathlib import Path

# Before eos_core.db is imported: its engine is built at import time from the setting.
os.environ.setdefault("EOS_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/audit-test.db")
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[4]))

import pytest
from audit_support import PREFIX, WRITER_ROLE
from eos_audit.api.router import WRITE, router
from eos_audit.domain.models import AuditRecord
from eos_core import config as core_config
from eos_core.db import SessionLocal, init_db
from eos_core.events import OutboxEvent
from eos_core.tenant import platform_scope
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete

# Every fixture name here starts with audit_. In CI's single combined pytest run, conftests of trees outside the
# chosen rootdir can end up with the same scope id, so a fixture named like another module's (`db`, `_clean`)
# silently replaces it for that module's tests too. That once made notification's tests run this cleanup instead
# of their own. For the same reason each autouse fixture below must stay harmless around another module's tests.


@pytest.fixture(scope="session", autouse=True)
def _audit_tables():
    """The module alone: its own table plus identity's (a declared dependency) and the outbox."""
    init_db()


@pytest.fixture(autouse=True)
def _audit_clean():
    """SQLite only: init_db() installs no trigger there, so rows can be cleared between tests. On any other
    database this does nothing rather than exiting, because it may also run around another module's tests, such
    as notification's opt-in PostgreSQL suite. The PostgreSQL checks for audit are in test_audit_postgres.py and
    use their own throwaway database."""
    with platform_scope(), SessionLocal() as s:
        if s.get_bind().dialect.name != "sqlite":
            return
        s.execute(delete(AuditRecord))
        s.execute(delete(OutboxEvent))
        s.commit()


@pytest.fixture(autouse=True)
def _audit_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("AUDIT_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def _audit_loggers_enabled():
    """A migration's fileConfig can disable loggers that already exist; a log assertion on a silenced logger
    would pass vacuously."""
    for name, logger in logging.Logger.manager.loggerDict.items():
        if name.startswith("eos") and isinstance(logger, logging.Logger):
            logger.disabled = False


@pytest.fixture(autouse=True)
def _audit_writer_role(monkeypatch):
    """audit:record:write is granted only to the `service` block, which no person may hold (platform/
    identity is to refuse it on a user), so the HTTP write route is exercised through one test-only role instead
    of a user carrying `service`. The real catalogue is otherwise untouched."""
    real = core_config.load_role_grants()
    grants = {name: set(keys) for name, keys in real.items()}
    grants[WRITER_ROLE] = {WRITE}
    monkeypatch.setattr(core_config, "load_role_grants", lambda: grants)


@pytest.fixture
def audit_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def audit_client():
    app = FastAPI()
    app.include_router(router, prefix=PREFIX)
    with TestClient(app) as c:
        yield c
