"""The Alembic chain creates exactly the tables the models describe, each with organisation_id, in the module's own version
table, and downgrades cleanly. Its Postgres output enables forced row-level security on every table."""

import io
import tempfile
import uuid
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


def test_the_chain_is_ex_0001_to_ex_0004_with_one_head():
    script = ScriptDirectory.from_config(_config("sqlite://"))
    assert script.get_heads() == ["ex_0004"]
    assert script.get_revision("ex_0004").down_revision == "ex_0003"
    assert script.get_revision("ex_0003").down_revision == "ex_0002"
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


DUTY_INDEXES = {"uq_examinations_duty_session_live", "uq_examinations_duty_paper_live"}


def _duty_indexes(conn) -> dict:
    return {i["name"]: i for i in inspect(conn).get_indexes(f"{PREFIX}exam_duty") if i["name"] in DUTY_INDEXES}


def test_ex_0003_adds_two_partial_unique_duty_indexes_and_downgrades_cleanly():
    cfg, engine = _upgraded()
    with engine.connect() as conn:
        found = _duty_indexes(conn)
        assert set(found) == DUTY_INDEXES
        assert all(i["unique"] for i in found.values())
        assert found["uq_examinations_duty_session_live"]["column_names"] == [
            "organisation_id",
            "staff_id",
            "duty_type",
            "exam_session_id",
        ]
        assert found["uq_examinations_duty_paper_live"]["column_names"] == [
            "organisation_id",
            "staff_id",
            "duty_type",
            "exam_paper_id",
        ]
        sql = " ".join(
            conn.exec_driver_sql(
                "SELECT sql FROM sqlite_master WHERE type = 'index' AND name LIKE 'uq_examinations_duty%'"
            )
            .scalars()
            .all()
        )
        assert sql.count("status IN ('assigned', 'completed')") == 2  # partial: a cancelled duty is not covered
    command.downgrade(cfg, "ex_0002")
    with engine.connect() as conn:
        assert _duty_indexes(conn) == {}
        assert "title" in {c["name"] for c in inspect(conn).get_columns(f"{PREFIX}exam_paper")}  # ex_0002 stays
        assert f"{PREFIX}exam_duty" in inspect(conn).get_table_names()
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert set(_duty_indexes(conn)) == DUTY_INDEXES


def _insert_duty(conn, ids, **over):
    from sqlalchemy import text

    row = {
        "id": ids.pop(),
        "o": "o" * 36,
        "c": "c" * 36,
        "s": "s" * 36,
        "t": "invigilation",
        "x": "x" * 36,
        "p": None,
        "st": "assigned",
    }
    row.update(over)
    conn.execute(
        text(
            "INSERT INTO examinations_exam_duty (id, organisation_id, created_at, exam_cycle_id, staff_id, duty_type, "
            "exam_session_id, exam_paper_id, status) VALUES (:id, :o, '2026-11-05 00:00:00', :c, :s, :t, :x, :p, :st)"
        ),
        row,
    )


def test_ex_0003_lets_a_cancelled_duty_repeat_but_not_a_live_one():
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    cfg, engine = _upgraded()
    ids = [f"{i:036d}" for i in range(1, 30)]
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        _insert_duty(conn, ids)
        _insert_duty(conn, ids, st="cancelled")  # a cancelled duty on the same target
        _insert_duty(conn, ids, st="cancelled")
        _insert_duty(conn, ids, o="p" * 36)  # another organisation
        _insert_duty(conn, ids, s="u" * 36)  # another staff member
        _insert_duty(conn, ids, t="invigilation", x="y" * 36)  # another session
        _insert_duty(conn, ids, t="evaluation", x=None, p="q" * 36)
        _insert_duty(conn, ids, t="moderation", x=None, p="q" * 36)  # another type, same paper
    for live in ("assigned", "completed"):
        with pytest.raises(IntegrityError, match="UNIQUE constraint failed"), engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            _insert_duty(conn, ids, st=live)
    with pytest.raises(IntegrityError, match="UNIQUE constraint failed"), engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        _insert_duty(conn, ids, t="evaluation", x=None, p="q" * 36)


def test_ex_0003_upgrades_a_database_that_already_holds_duties():
    from sqlalchemy import text

    cfg = _config(f"sqlite:///{tempfile.mkdtemp()}/duties.db")
    command.upgrade(cfg, "ex_0002")
    engine = create_engine(cfg.cmd_opts.x[0].removeprefix("url="))
    ids = [f"{i:036d}" for i in range(1, 10)]
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        _insert_duty(conn, ids)
        _insert_duty(conn, ids, st="cancelled")
        _insert_duty(conn, ids, st="cancelled")
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM examinations_exam_duty")).scalar() == 3


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

    created = []
    for pattern, name in (("*_0001_initial.py", "ex_0001"), ("*_0004_offering_ref_consumers.py", "ex_0004")):
        path = next((DB_DIR / "migrations" / "versions").glob(pattern))
        spec = util.spec_from_file_location(name, path)
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        created += module.TABLES if name == "ex_0001" else module.NEW_TABLES
    assert sorted(created) == sorted(t.name for t in TABLES)


def test_every_model_table_is_prefixed_and_tenant_scoped():
    assert len(TABLES) == 12
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
    assert sql.count("CREATE UNIQUE INDEX uq_examinations_duty_") == 2  # ex_0003, on Postgres too
    assert "exam_session_id IS NOT NULL AND status IN ('assigned', 'completed')" in sql
    assert "exam_paper_id IS NOT NULL AND status IN ('assigned', 'completed')" in sql
    assert "WHERE is_default" in sql and "WHERE status = 'active'" in sql  # the partial indexes exist on Postgres too


def _load(pattern: str):
    from importlib import util

    path = next((DB_DIR / "migrations" / "versions").glob(pattern))
    spec = util.spec_from_file_location(path.stem, path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_duty_indexes_of_the_model_and_of_ex_0003_have_the_same_exact_predicate():
    from eos_examinations.infrastructure import repository as repo
    from eos_examinations.infrastructure.models import ExamDutyRow

    module = _load("*_0003_duty_uniqueness.py")
    assert (module.revision, module.down_revision) == ("ex_0003", "ex_0002")
    live = "status IN (" + ", ".join(f"'{s}'" for s in repo.LIVE_DUTY_STATUSES) + ")"
    assert module.LIVE == live == "status IN ('assigned', 'completed')"  # the application's duplicate check, too
    indexes = {i.name: i for i in ExamDutyRow.__table__.indexes}
    assert {name for name, _ in module.INDEXES} <= set(indexes)
    for name, target in module.INDEXES:
        index = indexes[name]
        expected = f"{target} IS NOT NULL AND {live}"
        assert index.unique and len(name) <= POSTGRES_IDENTIFIER_LIMIT and name.startswith("uq_examinations_")
        assert [c.name for c in index.columns] == ["organisation_id", "staff_id", "duty_type", target]
        assert str(index.dialect_options["postgresql"]["where"]) == expected
        assert str(index.dialect_options["sqlite"]["where"]) == expected


def test_ex_0003_downgrade_removes_only_its_two_indexes():
    cfg, engine = _upgraded()
    with engine.connect() as conn:
        before = {i["name"] for i in inspect(conn).get_indexes(f"{PREFIX}exam_duty")}
    command.downgrade(cfg, "ex_0002")
    with engine.connect() as conn:
        after = {i["name"] for i in inspect(conn).get_indexes(f"{PREFIX}exam_duty")}
        other_tables = {t.name for t in TABLES} - {f"{PREFIX}processed_event"}  # ex_0004's table goes with it
        assert other_tables <= set(inspect(conn).get_table_names())
    assert before - after == DUTY_INDEXES and after <= before  # nothing else went, nothing came


def test_postgres_ex_0003_sql_creates_and_drops_exactly_the_two_partial_indexes():
    pytest.importorskip("psycopg")
    up, down = io.StringIO(), io.StringIO()
    for buffer, run in (
        (up, lambda c: command.upgrade(c, "ex_0002:ex_0003", sql=True)),
        (down, lambda c: command.downgrade(c, "ex_0003:ex_0002", sql=True)),
    ):
        cfg = _config("postgresql+psycopg://offline/offline")
        cfg.output_buffer = buffer
        run(cfg)
    created = [line for line in up.getvalue().splitlines() if line.startswith("CREATE")]
    assert created == [
        "CREATE UNIQUE INDEX uq_examinations_duty_session_live ON examinations_exam_duty "
        "(organisation_id, staff_id, duty_type, exam_session_id) "
        "WHERE exam_session_id IS NOT NULL AND status IN ('assigned', 'completed');",
        "CREATE UNIQUE INDEX uq_examinations_duty_paper_live ON examinations_exam_duty "
        "(organisation_id, staff_id, duty_type, exam_paper_id) "
        "WHERE exam_paper_id IS NOT NULL AND status IN ('assigned', 'completed');",
    ]
    dropped = [line for line in down.getvalue().splitlines() if line.startswith(("DROP", "ALTER", "CREATE"))]
    assert sorted(dropped) == [
        "DROP INDEX uq_examinations_duty_paper_live;",
        "DROP INDEX uq_examinations_duty_session_live;",
    ]


def _columns(conn, table: str) -> dict:
    return {c["name"]: c for c in inspect(conn).get_columns(table)}


def test_ex_0004_relaxes_offering_ref_and_adds_processed_event_and_downgrades_cleanly():
    cfg, engine = _upgraded()
    with engine.connect() as conn:
        columns = _columns(conn, f"{PREFIX}offering_ref")
        for name in ("course_id", "academic_period_id", "course_code", "course_title", "credits", "department_id"):
            assert columns[name]["nullable"], name
        assert {"status", "status_as_of"} <= set(columns) and columns["status"]["nullable"]
        assert {"event_id", "name", "organisation_id"} <= set(_columns(conn, f"{PREFIX}processed_event"))
    command.downgrade(cfg, "ex_0003")
    with engine.connect() as conn:
        columns = _columns(conn, f"{PREFIX}offering_ref")
        assert "status" not in columns and "status_as_of" not in columns
        assert not any(columns[n]["nullable"] for n in ("course_id", "course_code", "credits", "department_id"))
        assert f"{PREFIX}processed_event" not in inspect(conn).get_table_names()


def test_ex_0004_downgrade_keeps_known_offerings_and_drops_only_rows_with_no_creation():
    from sqlalchemy import text

    cfg, engine = _upgraded()
    known, partial, no_department = (str(i) for i in (uuid.uuid4(), uuid.uuid4(), uuid.uuid4()))
    with engine.begin() as conn:
        insert = text(
            f"INSERT INTO {PREFIX}offering_ref (id, organisation_id, created_at, course_offering_id, course_id, "
            "academic_period_id, course_code, course_title, credits, department_id, status) "
            "VALUES (:id, :org, '2026-11-13 00:00:00', :id, :course, :period, :code, 'T', 4, :dept, :status)"
        )
        org = str(uuid.uuid4())
        for row_id, code, dept, status in ((known, "K", known, "open"), (no_department, "N", None, None)):
            conn.execute(
                insert,
                {
                    "id": row_id,
                    "org": org,
                    "course": row_id,
                    "period": row_id,
                    "code": code,
                    "dept": dept,
                    "status": status,
                },
            )
        conn.execute(
            text(
                f"INSERT INTO {PREFIX}offering_ref (id, organisation_id, created_at, course_offering_id, status) "
                "VALUES (:id, :org, '2026-11-13 00:00:00', :id, 'open')"
            ),
            {"id": partial, "org": org},
        )
    command.downgrade(cfg, "ex_0003")
    with engine.connect() as conn:
        kept = {
            r[0]: r[1:]
            for r in conn.execute(
                text(f"SELECT course_offering_id, course_code, department_id FROM {PREFIX}offering_ref")
            )
        }
    assert kept == {known: ("K", known), no_department: ("N", "")}
