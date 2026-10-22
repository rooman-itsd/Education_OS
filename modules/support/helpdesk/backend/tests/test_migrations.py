"""The Alembic chain creates exactly the tables the models describe, each with organisation_id, in the module's own
version table, and downgrades cleanly."""

import tempfile
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from eos_helpdesk.infrastructure.models import PREFIX, TABLES
from sqlalchemy import create_engine, inspect

DB_DIR = Path(__file__).resolve().parents[2] / "db"


def _config(url: str) -> Config:
    cfg = Config(str(DB_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url}"]})()
    return cfg


def test_upgrade_matches_models_and_downgrade_removes_tables():
    url = f"sqlite:///{tempfile.mkdtemp()}/migrations.db"  # a fresh throwaway file, never a real database
    cfg = _config(url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        tables = set(inspect(conn).get_table_names())
        assert {t.name for t in TABLES} <= tables
        assert f"{PREFIX}alembic_version" in tables
        for t in TABLES:
            assert "organisation_id" in {c["name"] for c in inspect(conn).get_columns(t.name)}
        ctx = MigrationContext.configure(
            conn,
            opts={
                "include_object": lambda obj, name, type_, *_: (
                    type_ != "table" or (name.startswith(PREFIX) and "alembic" not in name)
                ),
            },
        )
        diff = [d for d in compare_metadata(ctx, TABLES[0].metadata) if PREFIX in repr(d)]
        assert diff == []
    command.downgrade(cfg, "base")
    with engine.connect() as conn:
        assert not [t for t in inspect(conn).get_table_names() if t.startswith(PREFIX) and "alembic" not in t]


def test_every_model_table_is_prefixed_and_tenant_scoped():
    for table in TABLES:
        assert table.name.startswith(PREFIX)
        assert "organisation_id" in table.columns


def test_the_open_counts_index_is_the_one_the_prd_names():
    ticket = next(t for t in TABLES if t.name == f"{PREFIX}ticket")
    index = next(i for i in ticket.indexes if i.name == "ix_helpdesk_ticket_open_counts")
    assert [c.name for c in index.columns] == ["organisation_id", "status", "priority", "queue_id"]
