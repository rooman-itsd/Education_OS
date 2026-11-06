"""The Alembic chain creates exactly the tables, columns and indexes the models describe, keeps its own version
table, gives every table organisation_id, and downgrades cleanly."""

import tempfile
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from eos_digilocker.domain.models import PREFIX, TABLES
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
        assert f"{PREFIX}alembic_version" in tables and "alembic_version" not in tables
        for t in TABLES:
            assert "organisation_id" in {c["name"] for c in insp.get_columns(t.name)}
        ctx = MigrationContext.configure(
            conn,
            opts={"include_object": lambda obj, name, type_, *_: type_ != "table" or _own(name), "compare_type": True},
        )
        diff = [d for d in compare_metadata(ctx, TABLES[0].metadata) if PREFIX in repr(d)]
        assert diff == []
    command.downgrade(cfg, "base")
    with engine.connect() as conn:
        assert not [t for t in inspect(conn).get_table_names() if _own(t)]


def test_the_chain_is_a_single_line():
    from alembic.script import ScriptDirectory

    scripts = ScriptDirectory.from_config(_config("sqlite://"))
    assert len(scripts.get_heads()) == 1 and len(scripts.get_bases()) == 1


def test_every_table_gets_the_forced_tenant_isolation_policy():
    text = (DB_DIR / "migrations/versions/20261105_0001_initial.py").read_text()
    assert "POLICY.format" in text and "for table in TABLES" in text
    from eos_core.rls import POLICY

    assert "FORCE ROW LEVEL SECURITY" in POLICY and "tenant_isolation" in POLICY
