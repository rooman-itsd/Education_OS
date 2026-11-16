"""Row-level security of every rti table on a real PostgreSQL (module standard rule 11), not only SQLite.

Skipped unless RTI_TEST_POSTGRES_URL points at a PostgreSQL server as a superuser, for example the
postgres:16-alpine image that CI and infra/docker use. Point it at a throwaway server only.

The test never touches existing data. It creates its own database (rti_rls_<random>), runs this module's Alembic
chain into it and checks, as the platform step in .github/workflows/api.yml does, that every table has the forced
tenant_isolation policy. Superusers ignore row-level security, so isolation itself is checked as a temporary role
that is neither a superuser nor allowed to bypass RLS. The database and the role are dropped at the end, also when a
check fails."""

import os
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

SERVER_URL = os.environ.get("RTI_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not SERVER_URL, reason="RTI_TEST_POSTGRES_URL is not set")

DB_DIR = Path(__file__).resolve().parents[2] / "db"
ORG_A = "00000000-0000-4000-8000-00000000000a"
ORG_B = "00000000-0000-4000-8000-00000000000b"


def _server_url():
    from sqlalchemy.engine import make_url

    url = make_url(SERVER_URL)
    if url.get_backend_name() != "postgresql":
        pytest.fail("RTI_TEST_POSTGRES_URL must be a postgresql:// URL")
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")  # the driver on the approved stack
    return url


def _alembic(url, revision: str, upgrade: bool) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(DB_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url.render_as_string(hide_password=False)}"]})()
    (command.upgrade if upgrade else command.downgrade)(cfg, revision)


@pytest.fixture(scope="module")
def pg():
    """(engine of the throwaway database, name of the temporary role). Everything is dropped afterwards."""
    pytest.importorskip("psycopg")
    from eos_rti.infrastructure.models import TABLES
    from sqlalchemy import create_engine, text

    server = _server_url()
    suffix = uuid.uuid4().hex[:12]
    db_name, role = f"rti_rls_{suffix}", f"rti_rls_probe_{suffix}"
    admin = create_engine(server, isolation_level="AUTOCOMMIT")
    engine = None
    try:
        with admin.connect() as c:
            c.execute(text(f'CREATE DATABASE "{db_name}"'))
            c.execute(text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT'))
        db_url = server.set(database=db_name)
        _alembic(db_url, "head", upgrade=True)
        engine = create_engine(db_url)
        with engine.begin() as c:
            c.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
            for table in TABLES:
                c.execute(text(f'GRANT SELECT, INSERT ON "{table.name}" TO "{role}"'))
        try:
            yield engine, role
        finally:
            engine.dispose()
            _alembic(db_url, "base", upgrade=False)  # the chain also downgrades cleanly on Postgres
    finally:
        if engine is not None:
            engine.dispose()
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
            c.execute(text(f'DROP ROLE IF EXISTS "{role}"'))
        admin.dispose()


@contextmanager
def as_role(engine, role: str, organisation_id: str | None):
    """One transaction run as the temporary role, with app.organisation_id set as the gateway sets it."""
    from sqlalchemy import text

    with engine.begin() as c:
        c.execute(text(f'SET LOCAL ROLE "{role}"'))
        c.execute(text("SELECT set_config('app.organisation_id', :org, true)"), {"org": organisation_id or ""})
        yield c


# One valid insert per table; every table is probed, so a table added later without a probe fails the first test.
INSERTS = {
    "rti_request": (
        "INSERT INTO rti_request (id, organisation_id, created_at, seq, number, received_via, received_on, "
        "applicant_name, subject, information_sought, fee_status, status, created_by, updated_at) VALUES "
        "(:id, :org, now(), (random() * 1000000000)::int, :num, 'post', current_date, 'probe', 'probe', 'probe', 'exempt', 'received', "
        ":id, now())"
    ),
    "rti_audit_entry": (
        "INSERT INTO rti_audit_entry (id, organisation_id, action, entity, entity_id, occurred_at) "
        "VALUES (:id, :org, 'probe', 'probe', :id, now())"
    ),
}
CHILDREN = {
    "rti_referral": (
        "INSERT INTO rti_referral (id, organisation_id, created_at, request_id, custodian_id, question, status, "
        "created_by) VALUES (:id, :org, now(), :parent, :id, 'probe', 'open', :id)"
    ),
    "rti_response": (
        "INSERT INTO rti_response (id, organisation_id, created_at, request_id, type, summary, dispatched_on, "
        "dispatch_mode, responded_by) VALUES (:id, :org, now(), :parent, 'refused', 'probe', current_date, 'post', :id)"
    ),
    "rti_transfer": (
        "INSERT INTO rti_transfer (id, organisation_id, created_at, request_id, authority_name, transferred_on, "
        "reason, transferred_by) VALUES (:id, :org, now(), :parent, 'probe', current_date, 'probe', :id)"
    ),
    "rti_appeal": (
        "INSERT INTO rti_appeal (id, organisation_id, created_at, request_id, filed_on, grounds, filed_by) "
        "VALUES (:id, :org, now(), :parent, current_date, 'probe', :id)"
    ),
}


def _insert(c, table: str, org: str) -> None:
    """One row of `table` for `org` (children get a parent request of the same organisation first)."""
    from sqlalchemy import text

    params = {"id": str(uuid.uuid4()), "org": org}
    params["num"] = params["id"][:20]
    if table in CHILDREN:
        params["parent"] = str(uuid.uuid4())
        c.execute(text(INSERTS["rti_request"]), {**params, "id": params["parent"], "num": params["parent"][:20]})
        c.execute(text(CHILDREN[table]), params)
    else:
        c.execute(text(INSERTS[table]), params)


ALL_TABLES = sorted({*INSERTS, *CHILDREN})


def test_every_rti_table_has_the_forced_tenant_isolation_policy(pg):
    from eos_rti.infrastructure.models import TABLES
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
    assert names <= policies, sorted(names - policies)
    assert names <= forced, sorted(names - forced)


def test_the_probe_role_cannot_bypass_row_level_security(pg):
    from sqlalchemy import text

    engine, role = pg
    with engine.connect() as c:
        superuser, bypass = c.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :r"), {"r": role}
        ).one()
    assert (superuser, bypass) == (False, False)


def test_every_table_has_a_probe():
    from eos_rti.infrastructure.models import TABLES

    assert set(ALL_TABLES) == {t.name for t in TABLES}


@pytest.mark.parametrize("table", ALL_TABLES)
def test_each_organisation_sees_only_its_own_rows(pg, table):
    from sqlalchemy import text

    engine, role = pg
    for org in (ORG_A, ORG_B):
        with as_role(engine, role, org) as c:
            _insert(c, table, org)
    for org in (ORG_A, ORG_B):
        with as_role(engine, role, org) as c:
            seen = {r[0] for r in c.execute(text(f"SELECT organisation_id FROM {table}"))}
        assert seen == {org}, (table, org, seen)
    with as_role(engine, role, None) as c:
        assert c.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0, table


@pytest.mark.parametrize("table", ALL_TABLES)
def test_writing_another_organisations_row_is_refused(pg, table):
    from sqlalchemy.exc import DBAPIError

    engine, role = pg
    with pytest.raises(DBAPIError, match="row-level security"):
        with as_role(engine, role, ORG_A) as c:
            _insert(c, table, str(uuid.uuid4()))
