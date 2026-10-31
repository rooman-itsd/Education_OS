"""The audit Alembic chain on a throwaway SQLite file. The PostgreSQL-only parts (RLS, the immutability
trigger) are in test_audit_postgres.py."""

import logging
import tempfile
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.runtime.migration import MigrationContext as RuntimeContext
from eos_audit.domain.models import TABLE_NAMES
from eos_core.db import Base
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

DB_DIR = Path(__file__).resolve().parents[2] / "db"
TABLES = set(TABLE_NAMES)


def _config(url: str) -> Config:
    cfg = Config(str(DB_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url}"]})()
    return cfg


def _include(obj, name, type_, *_):
    if type_ == "table":
        return name in TABLES
    return getattr(obj, "table", None) is None or obj.table.name in TABLES


def _fresh_url() -> str:
    return f"sqlite:///{tempfile.mkdtemp()}/audit.db"


def _upgraded():
    url = _fresh_url()
    cfg = _config(url)
    command.upgrade(cfg, "head")
    return url, cfg, create_engine(url)


def test_fresh_upgrade_matches_the_models_and_downgrades_cleanly():
    url, cfg, engine = _upgraded()
    insp = inspect(engine)
    assert TABLES <= set(insp.get_table_names()) and "audit_alembic_version" in insp.get_table_names()
    with engine.connect() as conn:
        # SQLite cannot reflect an expression index, so this comparison skips uq_audit_record_org_token (with a
        # warning). The index is checked below by name, and its behaviour by the duplicate-token tests.
        assert (
            compare_metadata(MigrationContext.configure(conn, opts={"include_object": _include}), Base.metadata) == []
        )
        head = RuntimeContext.configure(conn, opts={"version_table": "audit_alembic_version"}).get_current_revision()
        unique = conn.execute(text("SELECT sql FROM sqlite_master WHERE name = 'uq_audit_record_org_token'")).scalar()
    assert head == "audit_0001"
    assert unique and "UNIQUE" in unique.upper() and "coalesce" in unique
    command.downgrade(cfg, "base")
    assert not TABLES & set(inspect(create_engine(url)).get_table_names())


INSERT = text(
    "INSERT INTO audit_record (id, organisation_id, module, action, entity_type, entity_id, client_token,"
    " occurred_at, redacted) VALUES (:id, :org, 'm', 'a.b', 'e', 'e1', :token, '2026-10-24', 0)"
)


@pytest.mark.parametrize("org", [None, "org-1"])
def test_the_index_itself_refuses_a_duplicate_token_including_for_platform_records(org):
    """The application looks a token up before inserting, but two concurrent writers can both miss. The index
    is what stops the second, and on raw columns it would not for platform records: NULLs are distinct."""
    _, _, engine = _upgraded()
    with engine.begin() as conn:
        conn.execute(INSERT, {"id": str(uuid.uuid4()), "org": org, "token": "t"})
    with engine.begin() as conn, pytest.raises(IntegrityError):
        conn.execute(INSERT, {"id": str(uuid.uuid4()), "org": org, "token": "t"})


def test_records_without_a_token_are_never_treated_as_duplicates():
    _, _, engine = _upgraded()
    with engine.begin() as conn:
        for _ in range(2):
            conn.execute(INSERT, {"id": str(uuid.uuid4()), "org": None, "token": None})
        assert conn.execute(text("SELECT count(*) FROM audit_record")).scalar() == 2


def test_running_a_migration_leaves_the_host_process_loggers_alone():
    logger = logging.getLogger("eos_audit.test_fileconfig_probe")
    logger.disabled = False
    command.upgrade(_config(_fresh_url()), "head")
    assert not logger.disabled
