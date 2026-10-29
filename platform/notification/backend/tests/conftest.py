import logging
import os
import tempfile
from pathlib import Path

# The whole suite against PostgreSQL instead of SQLite, to prove the SERVICE works where it is deployed and not
# only the schema. Opt-in, and only ever against a throwaway database: these tests delete rows between tests.
# This has to run before eos_core.db is imported, because its engine is built at import time from the setting.
if os.environ.get("NOTIFICATION_PG_SUITE_URL"):
    if os.environ["NOTIFICATION_PG_SUITE_URL"].rsplit("/", 1)[-1].split("?")[0] not in {"eos_nsuite"}:
        raise SystemExit("NOTIFICATION_PG_SUITE_URL must name a throwaway database: ['eos_nsuite']")
    os.environ["EOS_DATABASE_URL"] = os.environ["NOTIFICATION_PG_SUITE_URL"]
os.environ.setdefault("EOS_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/notification-test.db")
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[4]))

import pytest
from eos_core.db import SessionLocal, init_db
from eos_core.events import OutboxEvent
from eos_core.tenant import organisation_scope, platform_scope
from eos_notification.domain.models import Message, Preference, TemplateOverride
from eos_notification.infrastructure import transport as transport_module
from notification_support import Org
from sqlalchemy import delete

# Repeated here, after the imports, for the second check against the live connection in _clean.
THROWAWAY_DATABASES = {"eos_nsuite"}


@pytest.fixture(scope="session", autouse=True)
def _tables():
    """The module alone: its own tables plus identity's (a declared dependency) and the outbox."""
    init_db()


@pytest.fixture(autouse=True)
def _clean():
    """recover_stuck sweeps every organisation, so a row left by one test must not be seen by the next."""
    # Cleanup is a platform-level act and must see every organisation. Without this, on PostgreSQL the DELETE
    # runs with no tenant set, row-level security hides every row, nothing is deleted, and rows leak into the
    # next test. On SQLite platform_scope only sets a ContextVar, so this changes nothing there.
    with platform_scope(), SessionLocal() as s:
        # EOS_DATABASE_URL may point somewhere real: never delete there. Non-SQLite is allowed only for a
        # database explicitly named as throwaway above, checked again here against the live connection.
        bind = s.get_bind()
        if bind.dialect.name != "sqlite" and bind.url.database not in THROWAWAY_DATABASES:
            pytest.exit(f"notification tests delete rows between tests; refusing to run on {bind.url.database!r}")
        for table in (Message, TemplateOverride, Preference, OutboxEvent):
            s.execute(delete(table))
        s.commit()


@pytest.fixture(autouse=True)
def _loggers_enabled():
    """Any logging.config.fileConfig call disables every logger that already exists unless it passes
    disable_existing_loggers=False. Notification's own env.py does pass it, but another service's migration in a
    full-suite run may not, and a log assertion on a silenced logger passes vacuously. This is that safety net."""
    for name, logger in logging.Logger.manager.loggerDict.items():
        if name.startswith("eos") and isinstance(logger, logging.Logger):
            logger.disabled = False


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("NOTIFICATION_"):
            monkeypatch.delenv(key, raising=False)
    transport_module.sent.clear()
    yield
    transport_module.sent.clear()


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def org(db):
    return Org.create(db)


@pytest.fixture
def other_org(db):
    return Org.create(db)


@pytest.fixture
def as_org():
    """`with as_org(org): ...` runs a block as that organisation, as the gateway would."""

    def _scope(o):
        return organisation_scope(o.id)

    return _scope
