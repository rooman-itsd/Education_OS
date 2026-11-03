"""Alembic migration test on SQLite for workflow."""

import tempfile
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.runtime.migration import MigrationContext as RuntimeContext
from eos_core.db import Base
from eos_workflow.domain.models import TABLE_NAMES
from sqlalchemy import create_engine, inspect

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
    return f"sqlite:///{tempfile.mkdtemp()}/workflow_mig.db"


def _upgraded():
    url = _fresh_url()
    cfg = _config(url)
    command.upgrade(cfg, "head")
    return url, cfg, create_engine(url)


def test_fresh_upgrade_matches_the_models_and_downgrades_cleanly():
    url, cfg, engine = _upgraded()
    insp = inspect(engine)
    assert TABLES <= set(insp.get_table_names()) and "workflow_alembic_version" in insp.get_table_names()
    with engine.connect() as conn:
        assert (
            compare_metadata(MigrationContext.configure(conn, opts={"include_object": _include}), Base.metadata) == []
        )
        head = RuntimeContext.configure(conn, opts={"version_table": "workflow_alembic_version"}).get_current_revision()
    assert head == "workflow_0001"
    command.downgrade(cfg, "base")
    assert not TABLES & set(inspect(create_engine(url)).get_table_names())
