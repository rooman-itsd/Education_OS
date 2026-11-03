"""The Alembic chain creates exactly the tables the models describe, each with organisation_id, in the module's own
version table, and downgrades cleanly. Its Postgres output enables forced row-level security on every table."""

import io
import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from eos_timetable_attendance.infrastructure.models import PREFIX, TABLES
from sqlalchemy import create_engine, inspect

DB_DIR = Path(__file__).resolve().parents[2] / "db"
POSTGRES_IDENTIFIER_LIMIT = 63


def _config(url: str) -> Config:
    cfg = Config(str(DB_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url}"]})()
    return cfg


def _upgraded():
    url = f"sqlite:///{tempfile.mkdtemp()}/migrations.db"  # a fresh throwaway file, never a real database
    cfg = _config(url)
    command.upgrade(cfg, "head")
    return cfg, create_engine(url)


def test_the_chain_has_one_revision_named_tt_0001():
    script = ScriptDirectory.from_config(_config("sqlite://"))
    assert script.get_heads() == ["tt_0001"]
    assert script.get_revision("tt_0001").down_revision is None


def test_upgrade_matches_models_and_downgrade_removes_tables():
    cfg, engine = _upgraded()
    with engine.connect() as conn:
        tables = set(inspect(conn).get_table_names())
        assert {t.name for t in TABLES} <= tables
        assert f"{PREFIX}alembic_version" in tables
        for t in TABLES:
            assert "organisation_id" in {c["name"] for c in inspect(conn).get_columns(t.name)}
        ctx = MigrationContext.configure(
            conn,
            opts={
                "compare_type": True,
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


def test_the_migration_creates_every_model_table_and_no_other():
    from importlib import util

    path = next((DB_DIR / "migrations" / "versions").glob("*_0001_initial.py"))
    spec = util.spec_from_file_location("tt_0001", path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert sorted(module.TABLES) == sorted(t.name for t in TABLES)


def test_every_model_table_is_prefixed_and_tenant_scoped():
    assert len(TABLES) == 11
    for table in TABLES:
        assert table.name.startswith(PREFIX), table.name
        assert "organisation_id" in table.columns, table.name
        assert table.columns["organisation_id"].index, table.name


def test_no_foreign_key_leaves_the_module():
    names = {t.name for t in TABLES}
    for table in TABLES:
        for fk in table.foreign_keys:
            assert fk.column.table.name in names, (table.name, fk.target_fullname)


def test_identifiers_fit_postgres():
    """PostgreSQL silently truncates identifiers over 63 characters, which would make two names collide or a
    migration's index differ from its model's."""
    for table in TABLES:
        names = [table.name, *(i.name for i in table.indexes), *(c.name for c in table.constraints if c.name)]
        for name in names:
            assert len(name) <= POSTGRES_IDENTIFIER_LIMIT, (len(name), name)


def test_postgres_migration_enables_forced_rls_on_every_table():
    pytest.importorskip("psycopg")
    buffer = io.StringIO()
    cfg = _config("postgresql+psycopg://offline/offline")
    cfg.output_buffer = buffer
    command.upgrade(cfg, "head", sql=True)
    sql = buffer.getvalue()
    for table in TABLES:
        assert f"ALTER TABLE {table.name} ENABLE ROW LEVEL SECURITY;" in sql, table.name
        assert f"ALTER TABLE {table.name} FORCE ROW LEVEL SECURITY;" in sql, table.name
        assert f"CREATE POLICY tenant_isolation ON {table.name}" in sql, table.name
    assert sql.count("CREATE POLICY tenant_isolation") == len(TABLES)
