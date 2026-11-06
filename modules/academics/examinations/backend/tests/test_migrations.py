"""The Alembic chain creates exactly the tables the models describe, each with organisation_id, in the module's own version
table, and downgrades cleanly. Its Postgres output enables forced row-level security on every table."""

import io
import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from eos_examinations.infrastructure.models import PREFIX, TABLES
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


def test_the_chain_is_ex_0001_then_ex_0002_with_one_head():
    script = ScriptDirectory.from_config(_config("sqlite://"))
    assert script.get_heads() == ["ex_0002"]
    assert script.get_revision("ex_0002").down_revision == "ex_0001"
    assert script.get_revision("ex_0001").down_revision is None


def test_ex_0002_adds_only_a_nullable_title_to_papers_and_downgrades_cleanly():
    cfg, engine = _upgraded()
    with engine.connect() as conn:
        columns = {c["name"]: c for c in inspect(conn).get_columns(f"{PREFIX}exam_paper")}
        assert columns["title"]["nullable"] and columns["title"]["default"] is None
        assert "organisation_id" in columns
        uniques = {u["name"] for u in inspect(conn).get_unique_constraints(f"{PREFIX}exam_paper")}
        assert "uq_examinations_paper_component" in uniques  # the batch rebuild keeps the constraints
    command.downgrade(cfg, "ex_0001")
    with engine.connect() as conn:
        columns = {c["name"] for c in inspect(conn).get_columns(f"{PREFIX}exam_paper")}
        assert "title" not in columns and "organisation_id" in columns
        assert f"{PREFIX}exam_cycle" in inspect(conn).get_table_names()  # nothing else went with it
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert "title" in {c["name"] for c in inspect(conn).get_columns(f"{PREFIX}exam_paper")}


def test_ex_0002_keeps_existing_papers_untitled_and_intact():
    from sqlalchemy import text

    cfg = _config(f"sqlite:///{tempfile.mkdtemp()}/upgrade.db")
    command.upgrade(cfg, "ex_0001")
    url = cfg.cmd_opts.x[0].removeprefix("url=")
    engine = create_engine(url)
    with engine.begin() as conn:
        ids = ["a" * 36, "b" * 36, "c" * 36, "d" * 36, "e" * 36, "f" * 36, "g" * 36]
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(
            text(
                "INSERT INTO examinations_exam_paper (id, organisation_id, created_at, exam_cycle_id, course_offering_id, "
                "assessment_component_id, max_marks, status) VALUES (:i, :o, '2026-11-05 00:00:00', :c, :f, :k, 100, 'draft')"
            ),
            {"i": ids[0], "o": ids[1], "c": ids[2], "f": ids[3], "k": ids[4]},
        )
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id, organisation_id, status, title FROM examinations_exam_paper")).one()
        assert tuple(row) == (ids[0], ids[1], "draft", None)


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
    spec = util.spec_from_file_location("ex_0001", path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert sorted(module.TABLES) == sorted(t.name for t in TABLES)


def test_every_model_table_is_prefixed_and_tenant_scoped():
    assert len(TABLES) == 11
    for table in TABLES:
        assert table.name.startswith(PREFIX), table.name
        assert "organisation_id" in table.columns, table.name
        assert table.columns["organisation_id"].index, table.name


def test_no_table_for_a_decision_that_is_not_taken():
    """Candidates, hall tickets, marks, results and the registration read model carry `student_id` or depend on
    eligibility, whose rules are unresolved; they are a later slice."""
    names = {t.name for t in TABLES}
    for blocked in ("candidate", "hall_ticket", "mark_entry", "result", "registration_ref"):
        assert f"{PREFIX}{blocked}" not in names
    for table in TABLES:
        assert "student_id" not in table.columns, table.name


def test_no_foreign_key_leaves_the_module():
    names = {t.name for t in TABLES}
    for table in TABLES:
        for fk in table.foreign_keys:
            assert fk.column.table.name in names, (table.name, fk.target_fullname)


def test_identifiers_fit_postgres():
    """PostgreSQL silently truncates identifiers over 63 characters, which would make two names collide or a migration's
    index differ from its model's."""
    for table in TABLES:
        names = [table.name, *(i.name for i in table.indexes), *(c.name for c in table.constraints if c.name)]
        for name in names:
            assert len(name) <= POSTGRES_IDENTIFIER_LIMIT, (len(name), name)


def test_the_partial_unique_indexes_and_the_duty_check_exist_in_the_database():
    _, engine = _upgraded()
    with engine.connect() as conn:
        indexes = {i["name"]: i for i in inspect(conn).get_indexes(f"{PREFIX}grading_scheme")}
        assert indexes["uq_examinations_grading_scheme_default"]["unique"]
        indexes = {i["name"]: i for i in inspect(conn).get_indexes(f"{PREFIX}assessment_scheme")}
        assert indexes["uq_examinations_assessment_scheme_active"]["unique"]
        sql = conn.exec_driver_sql("SELECT sql FROM sqlite_master WHERE name = 'examinations_exam_duty'").scalar()
        assert "ck_examinations_duty_target" in sql


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
    assert (
        "ALTER TABLE examinations_exam_paper ADD COLUMN title VARCHAR(200)" in sql
    )  # nullable: no NOT NULL, no default
    assert "WHERE is_default" in sql and "WHERE status = 'active'" in sql  # the partial indexes exist on Postgres too
