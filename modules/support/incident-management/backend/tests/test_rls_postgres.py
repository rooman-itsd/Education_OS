"""Row-level security of every incident-management table on a real PostgreSQL (module standard rule 11), not only
SQLite, and the two rows a request may create at the same moment as another: the number sequence and a problem's RCA.

Skipped unless INCIDENT_MANAGEMENT_TEST_POSTGRES_URL points at a PostgreSQL server as a superuser, for example the
postgres:16-alpine image that CI and infra/docker use. Point it at a throwaway server only.

The test never touches existing data. It creates its own database (im_rls_<random>), runs this module's Alembic
chain into it and checks, as the platform step in .github/workflows/api.yml does, that every table has the forced
tenant_isolation policy. Superusers ignore row-level security, so isolation itself is checked as a temporary role
that is neither a superuser nor allowed to bypass RLS. The database and the role are dropped at the end, also when a
check fails."""

import os
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

SERVER_URL = os.environ.get("INCIDENT_MANAGEMENT_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not SERVER_URL, reason="INCIDENT_MANAGEMENT_TEST_POSTGRES_URL is not set")

DB_DIR = Path(__file__).resolve().parents[2] / "db"
ORG_A = "00000000-0000-4000-8000-00000000000a"
ORG_B = "00000000-0000-4000-8000-00000000000b"


def _server_url():
    from sqlalchemy.engine import make_url

    url = make_url(SERVER_URL)
    if url.get_backend_name() != "postgresql":
        pytest.fail("INCIDENT_MANAGEMENT_TEST_POSTGRES_URL must be a postgresql:// URL")
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
    from eos_incident_management.infrastructure.models import TABLES
    from sqlalchemy import create_engine, text

    server = _server_url()
    suffix = uuid.uuid4().hex[:12]
    db_name, role = f"im_rls_{suffix}", f"im_rls_probe_{suffix}"
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


PROBLEM = (
    "INSERT INTO incident_management_problem (id, organisation_id, created_at, number, title, description, "
    "affected_services, status, owner_id, updated_at) "
    "VALUES (:id, :org, now(), :id, 'probe', 'probe', '[]', 'open', :id, now())"
)
INCIDENT = (
    "INSERT INTO incident_management_incident (id, organisation_id, created_at, number, title, description, "
    "affected_services, severity, status, lead_id, responder_ids, reported_by, started_at, updated_at) "
    "VALUES (:id, :org, now(), :id, 'probe', 'probe', '[]', 'low', 'open', :id, '[]', :id, now(), now())"
)

# Rows whose parent row must exist first insert it in the same statement (a CTE), as the same organisation.
INSERTS = {
    "incident_management_problem": PROBLEM,
    "incident_management_incident": INCIDENT,
    "incident_management_timeline_update": (
        f"WITH parent AS ({INCIDENT} RETURNING id) "
        "INSERT INTO incident_management_timeline_update (id, organisation_id, created_at, incident_id, author_id, "
        "body) SELECT :child, :org, now(), parent.id, :child, 'probe' FROM parent"
    ),
    "incident_management_reference": (
        f"WITH parent AS ({INCIDENT} RETURNING id) "
        "INSERT INTO incident_management_reference (id, organisation_id, created_at, incident_id, ref_module, "
        "ref_entity, ref_id, relation, created_by) "
        "SELECT :child, :org, now(), parent.id, 'helpdesk', 'ticket', 'probe', 'related_ticket', :child FROM parent"
    ),
    "incident_management_rca": (
        f"WITH parent AS ({PROBLEM} RETURNING id) "
        "INSERT INTO incident_management_rca (organisation_id, problem_id, summary, root_cause, contributing_factors, "
        "attachment_document_ids, status, updated_at) "
        "SELECT :org, parent.id, 'probe', 'probe', '[]', '[]', 'draft', now() FROM parent"
    ),
    "incident_management_corrective_action": (
        f"WITH parent AS ({PROBLEM} RETURNING id) "
        "INSERT INTO incident_management_corrective_action (id, organisation_id, created_at, problem_id, description, "
        "owner_id, due_date, status, updated_at) "
        "SELECT :child, :org, now(), parent.id, 'probe', :child, '2026-12-01', 'open', now() FROM parent"
    ),
    "incident_management_number_sequence": (
        "INSERT INTO incident_management_number_sequence (organisation_id, kind, last_number) "
        "VALUES (:org, 'incident', 0)"
    ),
    "incident_management_audit_entry": (
        "INSERT INTO incident_management_audit_entry (id, organisation_id, action, entity, entity_id, occurred_at) "
        "VALUES (:id, :org, 'probe', 'probe', :id, now())"
    ),
}


def _ids(org: str) -> dict:
    return {"id": str(uuid.uuid4()), "child": str(uuid.uuid4()), "org": org}


def test_every_table_is_probed():
    from eos_incident_management.infrastructure.models import TABLES

    assert set(INSERTS) == {t.name for t in TABLES}


def test_every_incident_management_table_has_the_forced_tenant_isolation_policy(pg):
    from eos_incident_management.infrastructure.models import TABLES
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


@pytest.mark.parametrize("table", sorted(INSERTS))
def test_each_organisation_sees_only_its_own_rows(pg, table):
    from sqlalchemy import text

    engine, role = pg
    for org in (ORG_A, ORG_B):
        with as_role(engine, role, org) as c:
            c.execute(text(INSERTS[table]), _ids(org))
    for org in (ORG_A, ORG_B):
        with as_role(engine, role, org) as c:
            seen = {r[0] for r in c.execute(text(f"SELECT organisation_id FROM {table}"))}
        assert seen == {org}, (table, org, seen)
    with as_role(engine, role, None) as c:
        assert c.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0, table


@pytest.mark.parametrize("table", sorted(INSERTS))
def test_writing_another_organisations_row_is_refused(pg, table):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    engine, role = pg
    with pytest.raises(DBAPIError, match="row-level security"):
        with as_role(engine, role, ORG_A) as c:
            c.execute(text(INSERTS[table]), _ids(str(uuid.uuid4())))


def test_two_first_numbers_at_the_same_time_do_not_collide(pg):
    """The first number of an organisation, taken by two transactions at once: the second waits on the first's insert
    of the sequence row and then takes the next number, instead of failing on the primary key."""
    from eos_incident_management.infrastructure.repository import next_number
    from sqlalchemy.orm import Session

    engine, _ = pg
    org = str(uuid.uuid4())
    first, second = Session(engine), Session(engine)
    numbers: dict[str, int] = {}
    try:
        numbers["first"] = next_number(first, org, "incident")  # row inserted, not yet committed
        waiting = threading.Thread(target=lambda: numbers.update(second=next_number(second, org, "incident")))
        waiting.start()
        waiting.join(timeout=1)
        assert waiting.is_alive(), "the second transaction should wait for the first"
        first.commit()
        waiting.join(timeout=10)
        second.commit()
    finally:
        first.close()
        second.close()
    assert numbers == {"first": 1, "second": 2}


def test_two_first_rca_drafts_at_the_same_time_do_not_collide(pg, monkeypatch):
    """Two PUT /problems/{id}/rca for a problem without an RCA, at once: the second waits on the problem row the first
    locked, then finds the first's draft and replaces it, instead of failing on the RCA's key."""
    from eos_incident_management.application import service
    from eos_incident_management.application.access import PROBLEM_MANAGE, Actor
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    engine, _ = pg
    org = str(uuid.uuid4())
    problem_id = str(uuid.uuid4())
    with engine.begin() as c:
        c.execute(text(PROBLEM), {"id": problem_id, "org": org})
    actor = Actor(user_id=str(uuid.uuid4()), organisation_id=org, permissions={PROBLEM_MANAGE})
    first, second = Session(engine), Session(engine)
    for session in (first, second):
        session.info["organisation_id"] = org
    results: dict[str, dict] = {}
    try:
        # The first request stops just before its commit: its draft is flushed and the problem row stays locked.
        monkeypatch.setattr(service, "_commit", lambda db: None)
        results["first"] = service.save_rca(first, actor, problem_id, {"summary": "One", "root_cause": "First"})
        monkeypatch.undo()
        body = {"summary": "Two", "root_cause": "Second"}
        waiting = threading.Thread(
            target=lambda: results.update(second=service.save_rca(second, actor, problem_id, body))
        )
        waiting.start()
        waiting.join(timeout=1)
        assert waiting.is_alive(), "the second draft should wait for the problem row"
        first.commit()
        waiting.join(timeout=10)
        assert not waiting.is_alive()
    finally:
        first.close()
        second.close()
    assert (results["first"]["summary"], results["second"]["summary"]) == ("One", "Two")
    with engine.connect() as c:
        rows = c.execute(
            text("SELECT summary FROM incident_management_rca WHERE problem_id = :p"), {"p": problem_id}
        ).all()
    assert [r[0] for r in rows] == ["Two"]


def _write_while_the_parent_is_being_closed(pg, parent_sql, closing_sql, write):
    """`write(session, org, parent_id)` runs while another transaction holds the parent row, already set to a status that
    refuses it. It must wait for that row, then be refused (409): a read that did not lock would still see the old
    status and add its row to a record that is closing. Returns (waited, exception)."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    engine, _ = pg
    org, parent_id = str(uuid.uuid4()), str(uuid.uuid4())
    with engine.begin() as c:
        c.execute(text(parent_sql), {"id": parent_id, "org": org})
    closing, writer = Session(engine), Session(engine)
    for session in (closing, writer):
        session.info["organisation_id"] = org
    outcome: dict[str, BaseException | None] = {"error": None}

    def run():
        try:
            write(writer, org, parent_id)
        except BaseException as err:  # noqa: BLE001 - the test reads what the request would have answered
            outcome["error"] = err

    try:
        closing.execute(text(closing_sql), {"id": parent_id})  # the close is flushed, its row lock held, not committed
        waiting = threading.Thread(target=run)
        waiting.start()
        waiting.join(timeout=1)
        waited = waiting.is_alive()
        closing.commit()
        waiting.join(timeout=10)
        assert not waiting.is_alive()
    finally:
        closing.close()
        writer.close()
    return waited, outcome["error"]


def test_a_timeline_update_waits_for_an_incident_being_closed_and_is_refused(pg):
    from eos_incident_management.application import service
    from eos_incident_management.application.access import INCIDENT_MANAGE, Actor

    def write(session, org, incident_id):
        actor = Actor(user_id=str(uuid.uuid4()), organisation_id=org, permissions={INCIDENT_MANAGE})
        service.add_update(session, actor, incident_id, {"body": "Late note"})

    waited, error = _write_while_the_parent_is_being_closed(
        pg, INCIDENT, "UPDATE incident_management_incident SET status = 'cancelled' WHERE id = :id", write
    )
    assert waited, "the update should wait for the incident row"
    assert getattr(error, "status", None) == 409, error
    engine, _ = pg
    from sqlalchemy import text

    with engine.connect() as c:
        assert (
            c.execute(
                text("SELECT count(*) FROM incident_management_timeline_update WHERE body = 'Late note'")
            ).scalar()
            == 0
        )


def test_a_corrective_action_waits_for_a_problem_being_closed_and_is_refused(pg):
    from datetime import date, timedelta

    from eos_incident_management.application import service
    from eos_incident_management.application.access import PROBLEM_MANAGE, Actor

    def write(session, org, problem_id):
        actor = Actor(user_id=str(uuid.uuid4()), organisation_id=org, permissions={PROBLEM_MANAGE})
        body = {
            "description": "Replace the access point",
            "owner_id": str(uuid.uuid4()),
            "due_date": date.today() + timedelta(days=5),
        }
        service.add_action(session, actor, problem_id, body)

    waited, error = _write_while_the_parent_is_being_closed(
        pg, PROBLEM, "UPDATE incident_management_problem SET status = 'closed' WHERE id = :id", write
    )
    assert waited, "the action should wait for the problem row"
    assert getattr(error, "status", None) == 409, error
