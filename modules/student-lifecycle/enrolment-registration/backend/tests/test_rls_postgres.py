"""Row-level security on a real PostgreSQL server. The fixture creates a throwaway database and an unprivileged
probe role (no superuser, no BYPASSRLS, not the table owner), runs the migration, and drops both afterwards.
Needs ENROLMENT_REGISTRATION_TEST_POSTGRES_URL or EOS_TEST_POSTGRES_URL for a user with CREATEDB and CREATEROLE;
skipped otherwise."""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

SERVER_URL = os.environ.get("ENROLMENT_REGISTRATION_TEST_POSTGRES_URL") or os.environ.get("EOS_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not SERVER_URL, reason="ENROLMENT_REGISTRATION_TEST_POSTGRES_URL or EOS_TEST_POSTGRES_URL is not set"
)

DB_DIR = Path(__file__).resolve().parents[2] / "db"
ORG_A = "00000000-0000-4000-8000-00000000000a"
ORG_B = "00000000-0000-4000-8000-00000000000b"

INSERT_ENROLMENT = (
    "INSERT INTO enrolment_registration_programme_enrolment (id, organisation_id, person_id, student_name, "
    "programme_id, roll_number, start_academic_period_id, status, enrolled_at, enrolled_by) "
    "VALUES (:id, :org, :person, 'Ana Silva', :programme, :roll, :term, 'active', now(), 'staff-1')"
)


def _server_url():
    from sqlalchemy.engine import make_url

    url = make_url(SERVER_URL)
    if url.get_backend_name() != "postgresql":
        pytest.fail("the PostgreSQL test URL must be a postgresql:// URL")
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
    pytest.importorskip("psycopg")
    from eos_enrolment_registration.infrastructure.models import TABLES
    from sqlalchemy import create_engine, text

    server = _server_url()
    suffix = uuid.uuid4().hex[:12]
    db_name, role = f"enrolreg_rls_{suffix}", f"enrolreg_probe_{suffix}"
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
def as_role(engine, role: str, organisation_id: str):
    from sqlalchemy import text

    with engine.begin() as c:
        c.execute(text(f'SET LOCAL ROLE "{role}"'))
        c.execute(text("SELECT set_config('app.organisation_id', :org, true)"), {"org": organisation_id})
        yield c


def test_every_table_has_forced_tenant_isolation_policy(pg):
    from eos_enrolment_registration.infrastructure.models import TABLES
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
    assert names <= policies, f"no tenant_isolation policy on {names - policies}"
    assert names <= forced, f"row security not forced on {names - forced}"


def test_probe_role_sees_and_writes_only_its_own_organisation(pg):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    engine, role = pg
    with engine.connect() as c:
        superuser, bypass = c.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :r"), {"r": role}
        ).one()
    assert (superuser, bypass) == (False, False)

    a_id, b_id = str(uuid.uuid4()), str(uuid.uuid4())
    for org, row_id in ((ORG_A, a_id), (ORG_B, b_id)):
        with as_role(engine, role, org) as c:
            c.execute(
                text(INSERT_ENROLMENT),
                {
                    "id": row_id,
                    "org": org,
                    "person": str(uuid.uuid4()),
                    "programme": str(uuid.uuid4()),
                    "roll": "RN2026-00001",
                    "term": str(uuid.uuid4()),
                },
            )

    with as_role(engine, role, ORG_A) as c:
        seen = {r[0] for r in c.execute(text("SELECT id FROM enrolment_registration_programme_enrolment"))}
    assert a_id in seen and b_id not in seen

    with pytest.raises(DBAPIError), as_role(engine, role, ORG_A) as c:
        c.execute(
            text(INSERT_ENROLMENT),
            {
                "id": str(uuid.uuid4()),
                "org": ORG_B,
                "person": str(uuid.uuid4()),
                "programme": str(uuid.uuid4()),
                "roll": "RN2026-00002",
                "term": str(uuid.uuid4()),
            },
        )
