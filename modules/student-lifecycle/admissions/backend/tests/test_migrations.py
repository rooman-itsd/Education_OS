from __future__ import annotations

import tempfile
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from eos_admissions.infrastructure.models import PREFIX, TABLES
from sqlalchemy import create_engine, inspect

DB_DIR = Path(__file__).resolve().parents[2] / "db"
VERSION_TABLE = f"{PREFIX}alembic_version"


def _config(url: str) -> Config:
    cfg = Config(str(DB_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url}"]})()
    return cfg


def _module_tables(conn) -> set[str]:
    return {t for t in inspect(conn).get_table_names() if t.startswith(PREFIX) and t != VERSION_TABLE}


def test_upgrade_matches_models_and_downgrade_removes_tables():
    url = f"sqlite:///{tempfile.mkdtemp()}/admissions_migration.db"
    cfg = _config(url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)

    with engine.connect() as conn:
        assert _module_tables(conn) == {t.name for t in TABLES}
        assert VERSION_TABLE in inspect(conn).get_table_names()
        ctx = MigrationContext.configure(
            conn,
            opts={
                "include_object": lambda obj, name, type_, *_: (
                    type_ != "table" or (name.startswith(PREFIX) and name != VERSION_TABLE)
                ),
            },
        )
        diff = [d for d in compare_metadata(ctx, TABLES[0].metadata) if PREFIX in repr(d)]
        assert diff == [], f"migration and models differ: {diff}"

    command.downgrade(cfg, "base")
    with engine.connect() as conn:
        assert _module_tables(conn) == set()
    engine.dispose()


def test_open_offer_index_is_partial_on_both_dialects():
    offer = next(t for t in TABLES if t.name == f"{PREFIX}offer")
    index = next(i for i in offer.indexes if i.name == f"uq_{PREFIX}offer_open")
    assert index.unique
    for dialect in ("postgresql", "sqlite"):
        assert "status = 'open'" in str(index.dialect_options[dialect]["where"])
