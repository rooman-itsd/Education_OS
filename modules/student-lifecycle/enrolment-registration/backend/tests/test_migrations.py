from __future__ import annotations

import tempfile
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from eos_enrolment_registration.infrastructure.models import PREFIX, TABLES
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
    url = f"sqlite:///{tempfile.mkdtemp()}/enrolment_registration_migration.db"
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


def test_partial_unique_indexes_on_both_dialects():
    expected = {
        f"{PREFIX}programme_enrolment": (f"uq_{PREFIX}programme_enrolment_active", "status = 'active'"),
        f"{PREFIX}course_registration": (f"uq_{PREFIX}course_registration_confirmed", "status = 'confirmed'"),
    }
    for table_name, (index_name, where) in expected.items():
        table = next(t for t in TABLES if t.name == table_name)
        index = next(i for i in table.indexes if i.name == index_name)
        assert index.unique
        for dialect in ("postgresql", "sqlite"):
            assert where in str(index.dialect_options[dialect]["where"])
