"""The Alembic chain creates exactly the tables, columns and indexes the models describe, keeps its own
version table, and downgrades cleanly."""

import re
import tempfile
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from eos_wearables.infrastructure.models import PREFIX, TABLES
from sqlalchemy import create_engine, inspect

DB_DIR = Path(__file__).resolve().parents[1] / "db"


def _config(url: str) -> Config:
    cfg = Config(str(DB_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url}"]})()
    return cfg


def _own(name: str) -> bool:
    return name.startswith(PREFIX) and "alembic" not in name


def test_upgrade_matches_models_and_downgrade_removes_tables():
    url = f"sqlite:///{tempfile.mkdtemp()}/migrations.db"  # a fresh throwaway file, never a real database
    cfg = _config(url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        insp = inspect(conn)
        tables = set(insp.get_table_names())
        assert {t.name for t in TABLES} <= tables
        assert f"{PREFIX}alembic_version" in tables
        assert "alembic_version" not in tables  # never the shared default version table
        for t in TABLES:
            assert "organisation_id" in {c["name"] for c in insp.get_columns(t.name)}
        ctx = MigrationContext.configure(
            conn,
            opts={
                "include_object": lambda obj, name, type_, *_: type_ != "table" or _own(name),
                "compare_type": True,
            },
        )
        diff = [d for d in compare_metadata(ctx, TABLES[0].metadata) if PREFIX in repr(d)]
        assert diff == []
    command.downgrade(cfg, "base")
    with engine.connect() as conn:
        assert not [t for t in inspect(conn).get_table_names() if _own(t)]


def test_the_chain_is_a_single_line():
    from alembic.script import ScriptDirectory

    scripts = ScriptDirectory.from_config(_config("sqlite://"))
    assert len(scripts.get_heads()) == 1
    assert len(scripts.get_bases()) == 1


def test_every_table_is_tenant_scoped_and_the_migration_applies_the_forced_policy():
    """Row-level security itself is exercised on Postgres by CI's chain job (every enabled chain: tenant_isolation forced);
    SQLite has none, so here the migration is checked to ask for the policy on every table it creates."""
    text = (DB_DIR / "migrations/versions/20261105_0001_initial.py").read_text()
    assert "POLICY.format" in text and "for table in TABLES" in text
    from eos_core.rls import POLICY

    assert "FORCE ROW LEVEL SECURITY" in POLICY and "tenant_isolation" in POLICY
    created = set(re.findall(r'f"\{P\}(\w+)",\n        _id\(\)', text))
    assert (
        created == {"link_state", "record", "read_log", "audit_entry"} == {t.name.removeprefix(PREFIX) for t in TABLES}
    )
