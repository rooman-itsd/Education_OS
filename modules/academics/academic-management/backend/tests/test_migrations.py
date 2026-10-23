"""The Alembic chain creates exactly the tables the models describe, under the module's own version table, and
downgrades cleanly. Every table carries organisation_id."""

import tempfile
from pathlib import Path

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see test_api_deps.py)")

from alembic import command  # noqa: E402
from alembic.autogenerate import compare_metadata  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from eos_academic_management.infrastructure.models import PREFIX, TABLES  # noqa: E402
from sqlalchemy import create_engine, inspect  # noqa: E402

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
            assert t.name.startswith(PREFIX)
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
