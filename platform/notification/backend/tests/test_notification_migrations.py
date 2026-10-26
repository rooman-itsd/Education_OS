"""The notification Alembic chain: a fresh database, and the existing-schema path (verify, then stamp)."""

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
from eos_core.db import Base
from eos_notification.domain.models import TABLE_NAMES
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError

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


def _drift(engine) -> list:
    """Differences between the database and the models, for notification's tables only."""
    with engine.connect() as conn:
        return compare_metadata(MigrationContext.configure(conn, opts={"include_object": _include}), Base.metadata)


def _fresh_url() -> str:
    return f"sqlite:///{tempfile.mkdtemp()}/notification.db"  # a throwaway file, never a real database


def _head(engine) -> str | None:
    with engine.connect() as conn:
        return RuntimeContext.configure(
            conn, opts={"version_table": "notification_alembic_version"}
        ).get_current_revision()


def test_fresh_database_upgrade_head_matches_the_models_and_downgrades_cleanly():
    url = _fresh_url()
    cfg = _config(url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    insp = inspect(engine)
    assert TABLES <= set(insp.get_table_names()) and "notification_alembic_version" in insp.get_table_names()
    assert _drift(engine) == []
    uniques = {u["name"] for u in insp.get_unique_constraints("notification_message")}
    assert {"uq_notification_message_org_token", "uq_notification_message_org_event"} <= uniques
    assert _head(engine) == "notification_0001"
    command.downgrade(cfg, "base")
    assert not TABLES & set(inspect(create_engine(url)).get_table_names())


def test_the_migrated_schema_enforces_organisation_rules_itself():
    url = _fresh_url()
    command.upgrade(_config(url), "head")
    engine = create_engine(url)
    insert = text(
        "INSERT INTO notification_message (id, organisation_id, created_at, template_key, channel, category, status,"
        " recipient_key, variables, body_template, attempts, updated_at) VALUES (:id, :org, '2026-10-13', 't', 'email',"
        " 'operational', 'queued', 'r', '{}', 'b', 0, '2026-10-13')"
    )
    with engine.begin() as conn:
        conn.execute(insert, {"id": str(uuid.uuid4()), "org": str(uuid.uuid4())})  # a valid row is accepted
    for org in (None, ""):
        with engine.begin() as conn, pytest.raises(IntegrityError):
            conn.execute(insert, {"id": str(uuid.uuid4()), "org": org})


def test_existing_schema_path_needs_verification_then_stamp_never_a_blind_upgrade():
    """A database whose tables were made by init_db()/create_all has no Alembic version. A plain upgrade would
    fail ("already exists"); the safe path is: prove the schema equals the models, then stamp."""
    url = _fresh_url()
    engine = create_engine(url)
    Base.metadata.create_all(engine, tables=[t for t in Base.metadata.sorted_tables if t.name in TABLES])
    cfg = _config(url)
    with pytest.raises(OperationalError):
        command.upgrade(cfg, "head")
    assert _head(engine) is None  # the failed upgrade stamped nothing

    assert _drift(engine) == []  # verified: identical to the models
    command.stamp(cfg, "head")
    assert _head(engine) == "notification_0001"
    command.upgrade(cfg, "head")  # now a no-op
    assert _drift(engine) == []


def test_a_drifted_existing_schema_is_detected_so_it_is_not_stamped():
    url = _fresh_url()
    engine = create_engine(url)
    Base.metadata.create_all(engine, tables=[t for t in Base.metadata.sorted_tables if t.name in TABLES])
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE notification_message DROP COLUMN request_hash"))
    assert _drift(engine) != []  # the verification step refuses; nothing is stamped
    assert _head(engine) is None


def test_running_a_migration_leaves_the_host_process_loggers_alone():
    """env.py calls fileConfig, whose default disables every logger that already exists. A migration run inside a
    host process (or a test session) must not silence the loggers that process is already using."""
    logger = logging.getLogger("eos_notification.test_fileconfig_probe")
    logger.disabled = False
    command.upgrade(_config(_fresh_url()), "head")
    assert not logger.disabled
