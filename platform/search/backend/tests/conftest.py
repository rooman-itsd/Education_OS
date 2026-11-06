import logging
import os
import tempfile
from pathlib import Path

# Before eos_core.db is imported: its engine is built at import time from the setting.
os.environ.setdefault("EOS_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/search-test.db")
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[4]))

import eos_audit.domain.models  # noqa: E402,F401  registers audit's table for init_db
import pytest  # noqa: E402
from eos_core import config as core_config  # noqa: E402
from eos_core.db import SessionLocal, init_db  # noqa: E402
from eos_core.events import OutboxEvent  # noqa: E402
from eos_core.tenant import platform_scope  # noqa: E402
from eos_search.application import indexer  # noqa: E402
from eos_search.application import registry as registry_module
from eos_search.domain.models import DeadLetter, Entitlement, IndexState, ReindexJob  # noqa: E402
from eos_search.infrastructure.engine import set_engine  # noqa: E402
from eos_search.infrastructure.memory_engine import InMemoryEngine  # noqa: E402
from search_support import ROLES, Org, providers, registry_of  # noqa: E402
from sqlalchemy import delete  # noqa: E402

# Every fixture name here starts with search_: in CI's combined pytest run, a fixture named like another module's
# (`db`, `_clean`) silently replaces it for that module's tests too.


@pytest.fixture(scope="session", autouse=True)
def _search_tables():
    init_db()


@pytest.fixture(autouse=True)
def _search_clean():
    with platform_scope(), SessionLocal() as s:
        for table in (ReindexJob, IndexState, Entitlement, DeadLetter, OutboxEvent):
            s.execute(delete(table))
        s.commit()


@pytest.fixture(autouse=True)
def _search_loggers_enabled():
    for name, logger in logging.Logger.manager.loggerDict.items():
        if name.startswith("eos") and isinstance(logger, logging.Logger):
            logger.disabled = False


@pytest.fixture(autouse=True)
def _search_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("SEARCH_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SEARCH_INDEX_RETRY_BACKOFF_SECONDS", "0")
    monkeypatch.setattr(indexer, "sleep", lambda s: None)


@pytest.fixture(autouse=True)
def search_grants(monkeypatch):
    """The test roles over the real catalogue; nothing else about it changes."""
    real = core_config.load_role_grants()
    monkeypatch.setattr(core_config, "load_role_grants", lambda: {**real, **ROLES})


@pytest.fixture
def search_providers():
    return providers()


@pytest.fixture
def search_registry(search_providers):
    """The three first types and their example providers, installed as the process registry for the test."""
    registry = registry_of(search_providers)
    with registry_module.use_registry(registry):
        yield registry


@pytest.fixture
def search_engine():
    engine = InMemoryEngine("dev")
    set_engine(engine)
    yield engine
    set_engine(None)


@pytest.fixture
def search_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def search_org(search_db):
    return Org(search_db)


@pytest.fixture
def search_other_org(search_db):
    return Org(search_db)
