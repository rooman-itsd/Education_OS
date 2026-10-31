"""The Alembic chain creates exactly the tables the models describe, and downgrades cleanly."""

import tempfile
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from eos_core.db import Base
from eos_documents.domain.models import TABLE_NAMES
from sqlalchemy import create_engine, inspect

DB_DIR = Path(__file__).resolve().parents[2] / "db"


def _config(url: str) -> Config:
    cfg = Config(str(DB_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url}"]})()
    return cfg


def _include(obj, name, type_, *_) -> bool:
    if type_ == "table":
        return name in TABLE_NAMES
    table = getattr(obj, "table", None)
    return table is not None and table.name in TABLE_NAMES


def test_fresh_upgrade_matches_the_models_and_downgrades_cleanly():
    url = f"sqlite:///{tempfile.mkdtemp()}/documents_mig.db"
    cfg = _config(url)
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    with engine.connect() as conn:
        tables = set(inspect(conn).get_table_names())
        assert set(TABLE_NAMES) <= tables
        assert "documents_alembic_version" in tables

        for t in TABLE_NAMES:
            cols = {c["name"] for c in inspect(conn).get_columns(t)}
            assert "organisation_id" in cols

        ctx = MigrationContext.configure(conn, opts={"include_object": _include})
        diff = compare_metadata(ctx, Base.metadata)
        assert diff == []

    command.downgrade(cfg, "base")
    with engine.connect() as conn:
        remaining = [t for t in inspect(conn).get_table_names() if t in TABLE_NAMES]
        assert remaining == []
