"""PostgreSQL Row-Level Security (RLS) tests for student-information.

Tests:
- RLS enabled and forced on all four student_information tables
- tenant_isolation policy exists on all tables
- Tests with unprivileged probe role (NOSUPERUSER, NOBYPASSRLS, NOINHERIT)
- Cross-tenant read/write prevention enforced by PostgreSQL engine
- Transaction-scoped tenant setting verification (app.organisation_id)

Requirements:
- Connects using STUDENT_INFORMATION_TEST_POSTGRES_URL or EOS_TEST_POSTGRES_URL.
- Driver: postgresql+psycopg (psycopg 3).
- Runner privileges: CREATEDB and CREATEROLE (can be a dedicated non-superuser test user or admin).
- The test fixture creates a throwaway database (student_info_rls_<uuid>) and a temporary unprivileged
  probe role (student_info_probe_<uuid>). Both are dropped at fixture teardown.
- Skipped automatically when neither environment variable is configured.
"""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

SERVER_URL = os.environ.get("STUDENT_INFORMATION_TEST_POSTGRES_URL") or os.environ.get("EOS_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not SERVER_URL,
    reason="STUDENT_INFORMATION_TEST_POSTGRES_URL or EOS_TEST_POSTGRES_URL is not set",
)

DB_DIR = Path(__file__).resolve().parents[2] / "db"
ORG_A = "00000000-0000-4000-8000-00000000000a"
ORG_B = "00000000-0000-4000-8000-00000000000b"


def _server_url():
    from sqlalchemy.engine import make_url

    url = make_url(SERVER_URL)
    if url.get_backend_name() != "postgresql":
        pytest.fail("PostgreSQL test URL must be a postgresql:// URL")
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url


def _alembic(url, revision: str, upgrade: bool) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(DB_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url.render_as_string(hide_password=False)}"]})()
    (command.upgrade if upgrade else command.downgrade)(cfg, revision)


@pytest.fixture(scope="module")
def pg():
    """Sets up a fresh throwaway PostgreSQL database with an unprivileged probe role."""
    pytest.importorskip("psycopg")
    from eos_student_information.infrastructure.models import TABLES
    from sqlalchemy import create_engine, text

    server = _server_url()
    suffix = uuid.uuid4().hex[:12]
    db_name, role = f"student_info_rls_{suffix}", f"student_info_probe_{suffix}"
    admin = create_engine(server, isolation_level="AUTOCOMMIT")
    engine = None

    try:
        with admin.connect() as c:
            c.execute(text(f'CREATE DATABASE "{db_name}"'))
            c.execute(text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT'))
            c.execute(text(f'GRANT "{role}" TO CURRENT_USER'))

        db_url = server.set(database=db_name)
        _alembic(db_url, "head", upgrade=True)
        engine = create_engine(db_url)

        with engine.begin() as c:
            c.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
            for table in TABLES:
                c.execute(text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON "{table.name}" TO "{role}"'))

        try:
            yield engine, role
        finally:
            if engine is not None:
                engine.dispose()
            _alembic(db_url, "base", upgrade=False)
    finally:
        if engine is not None:
            engine.dispose()
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
            c.execute(text(f'DROP ROLE IF EXISTS "{role}"'))
        admin.dispose()


@contextmanager
def as_role(engine, role: str, organisation_id: str | None):
    """Executes a transaction as the unprivileged probe role with app.organisation_id configured."""
    from sqlalchemy import text

    with engine.begin() as c:
        c.execute(text(f'SET LOCAL ROLE "{role}"'))
        c.execute(text("SELECT set_config('app.organisation_id', :org, true)"), {"org": organisation_id or ""})
        yield c


def test_every_table_has_forced_tenant_isolation_policy(pg):
    """Verifies that all 4 tables have row-level security enabled, forced, and policy tenant_isolation."""
    from eos_student_information.infrastructure.models import TABLES
    from sqlalchemy import text

    engine, _ = pg
    with engine.connect() as c:
        policies = {
            r[0] for r in c.execute(text("SELECT tablename FROM pg_policies WHERE policyname = 'tenant_isolation'"))
        }
        forced = {
            r[0] for r in c.execute(text("SELECT relname FROM pg_class WHERE relrowsecurity AND relforcerowsecurity"))
        }

    names = {t.name for t in TABLES}
    assert names <= policies, f"Missing tenant_isolation policy on: {names - policies}"
    assert names <= forced, f"Row security not forced on: {names - forced}"


def test_probe_role_enforces_tenant_isolation(pg):
    """Unprivileged probe role can only read and write within its assigned organisation."""
    from sqlalchemy import text

    engine, role = pg

    # Verify probe role cannot bypass RLS
    with engine.connect() as c:
        superuser, bypass = c.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :r"), {"r": role}
        ).one()
    assert (superuser, bypass) == (False, False), f"Probe role must not bypass RLS: {(superuser, bypass)}"

    person_a_id = str(uuid.uuid4())
    person_b_id = str(uuid.uuid4())

    # Insert Person A under Org A
    with as_role(engine, role, ORG_A) as c:
        c.execute(
            text(
                "INSERT INTO student_information_person "
                "(id, organisation_id, first_name, last_name, status, status_effective_date, created_at, updated_at) "
                "VALUES (:id, :org, 'Alice', 'OrgA', 'pending', CURRENT_DATE, now(), now())"
            ),
            {"id": person_a_id, "org": ORG_A},
        )

    # Insert Person B under Org B
    with as_role(engine, role, ORG_B) as c:
        c.execute(
            text(
                "INSERT INTO student_information_person "
                "(id, organisation_id, first_name, last_name, status, status_effective_date, created_at, updated_at) "
                "VALUES (:id, :org, 'Bob', 'OrgB', 'pending', CURRENT_DATE, now(), now())"
            ),
            {"id": person_b_id, "org": ORG_B},
        )

    # Query as Org A: must see Person A, but NEVER Person B
    with as_role(engine, role, ORG_A) as c:
        rows = c.execute(text("SELECT id FROM student_information_person")).fetchall()
        row_ids = {r[0] for r in rows}
        assert person_a_id in row_ids
        assert person_b_id not in row_ids

    # Query as Org B: must see Person B, but NEVER Person A
    with as_role(engine, role, ORG_B) as c:
        rows = c.execute(text("SELECT id FROM student_information_person")).fetchall()
        row_ids = {r[0] for r in rows}
        assert person_b_id in row_ids
        assert person_a_id not in row_ids

    # Attempt cross-tenant insert: Org A tries to insert row tagged as Org B -> blocked by RLS WITH CHECK
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError):
        with as_role(engine, role, ORG_A) as c:
            c.execute(
                text(
                    "INSERT INTO student_information_person "
                    "(id, organisation_id, first_name, last_name, status, status_effective_date, created_at, updated_at) "
                    "VALUES (:id, :org, 'Attacker', 'OrgB', 'pending', CURRENT_DATE, now(), now())"
                ),
                {"id": str(uuid.uuid4()), "org": ORG_B},
            )
