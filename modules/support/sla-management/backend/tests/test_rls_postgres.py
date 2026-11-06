"""Row-level security of every sla-management table on a real PostgreSQL (module standard rule 11), not only SQLite.

Skipped unless SLA_MANAGEMENT_TEST_POSTGRES_URL points at a PostgreSQL server as a superuser, for example the
postgres:16-alpine image that CI and infra/docker use. Point it at a throwaway server only.

The test never touches existing data. It creates its own database (sla_rls_<random>), runs this module's Alembic
chain into it and checks that every table has the forced tenant_isolation policy. Superusers ignore row-level
security, so isolation itself is checked as a temporary role that is neither a superuser nor allowed to bypass RLS.
The database and the role are dropped at the end, also when a check fails."""

import os
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

SERVER_URL = os.environ.get("SLA_MANAGEMENT_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not SERVER_URL, reason="SLA_MANAGEMENT_TEST_POSTGRES_URL is not set")

DB_DIR = Path(__file__).resolve().parents[2] / "db"
ORG_A = "00000000-0000-4000-8000-00000000000a"
ORG_B = "00000000-0000-4000-8000-00000000000b"


def _server_url():
    from sqlalchemy.engine import make_url

    url = make_url(SERVER_URL)
    if url.get_backend_name() != "postgresql":
        pytest.fail("SLA_MANAGEMENT_TEST_POSTGRES_URL must be a postgresql:// URL")
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
    from eos_sla_management.infrastructure.models import TABLES
    from sqlalchemy import create_engine, text

    server = _server_url()
    suffix = uuid.uuid4().hex[:12]
    db_name, role = f"sla_rls_{suffix}", f"sla_rls_probe_{suffix}"
    admin = create_engine(server, isolation_level="AUTOCOMMIT")
    engine = None
    try:
        with admin.connect() as c:
            c.execute(text(f'CREATE DATABASE "{db_name}"'))
            c.execute(text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT'))
        db_url = server.set(database=db_name)
        _alembic(db_url, "head", upgrade=True)
        engine = create_engine(db_url)
        from eos_core.events import OutboxEvent

        OutboxEvent.__table__.create(engine)  # the outbox is platform/event-bus's table; the handler test writes it
        with engine.begin() as c:
            c.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
            c.execute(text(f'GRANT SELECT, INSERT ON outbox_event TO "{role}"'))
            for table in TABLES:
                c.execute(text(f'GRANT SELECT, INSERT, UPDATE ON "{table.name}" TO "{role}"'))
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


INSERTS = {
    "sla_management_calendar": (
        "INSERT INTO sla_management_calendar (id, organisation_id, created_at, name, time_zone, always_open, "
        "working_hours, holidays, active, updated_at) VALUES (:id, :org, now(), 'probe', 'UTC', true, '[]', '[]', "
        "true, now())"
    ),
    "sla_management_ticket_ref": (
        "INSERT INTO sla_management_ticket_ref (id, organisation_id, created_at, ticket_id, created, final, "
        "updated_at) VALUES (:id, :org, now(), :id, false, false, now())"
    ),
    "sla_management_processed_event": (
        "INSERT INTO sla_management_processed_event (id, organisation_id, event_id, name, processed_at) "
        "VALUES (:id, :org, :id, 'probe', now())"
    ),
    "sla_management_audit_entry": (
        "INSERT INTO sla_management_audit_entry (id, organisation_id, action, entity, entity_id, occurred_at) "
        "VALUES (:id, :org, 'probe', 'probe', :id, now())"
    ),
}


def test_every_sla_management_table_has_the_forced_tenant_isolation_policy(pg):
    from eos_sla_management.infrastructure.models import TABLES
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
    assert len(names) == 7
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
            c.execute(text(INSERTS[table]), {"id": str(uuid.uuid4()), "org": org})
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
            c.execute(text(INSERTS[table]), {"id": str(uuid.uuid4()), "org": str(uuid.uuid4())})


def _session(engine, role: str, org: str):
    from eos_core.tenant import organisation_scope
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    session = Session(engine)
    session.info["organisation_id"] = org
    with organisation_scope(org):
        session.execute(text(f'SET LOCAL ROLE "{role}"'))
        session.execute(text("SELECT set_config('app.organisation_id', :org, true)"), {"org": org})
    return session


def test_two_first_events_of_a_ticket_at_the_same_time_do_not_collide(pg):
    """The ticket row is got or created by two transactions at once, as the non-superuser role: the second waits on
    the first's insert, then finds and locks the same row instead of failing on the unique constraint."""
    from eos_core.tenant import organisation_scope
    from eos_sla_management.infrastructure.repository import ticket_ref

    engine, role = pg
    org, ticket = str(uuid.uuid4()), str(uuid.uuid4())
    first, second = _session(engine, role, org), _session(engine, role, org)
    found: dict[str, str] = {}
    try:
        with organisation_scope(org):
            found["first"] = ticket_ref(first, org, ticket, create=True).id  # inserted, not yet committed

        def other() -> None:
            with organisation_scope(org):
                found["second"] = ticket_ref(second, org, ticket, create=True).id

        waiting = threading.Thread(target=other)
        waiting.start()
        waiting.join(timeout=1)
        assert waiting.is_alive(), "the second transaction should wait for the first"
        first.commit()
        waiting.join(timeout=10)
        second.commit()
    finally:
        first.close()
        second.close()
    assert found["first"] == found["second"]


def test_a_duplicate_event_delivered_twice_at_once_is_applied_once(pg):
    from eos_core.tenant import organisation_scope
    from eos_sla_management.infrastructure.repository import mark_processed

    engine, role = pg
    org, event_id = str(uuid.uuid4()), str(uuid.uuid4())
    first, second = _session(engine, role, org), _session(engine, role, org)
    marked: dict[str, bool] = {}
    try:
        with organisation_scope(org):
            marked["first"] = mark_processed(first, org, event_id, "helpdesk.ticket.created")

        def other() -> None:
            with organisation_scope(org):
                marked["second"] = mark_processed(second, org, event_id, "helpdesk.ticket.created")

        waiting = threading.Thread(target=other)
        waiting.start()
        waiting.join(timeout=1)
        assert waiting.is_alive(), "the second delivery should wait for the first"
        first.commit()
        waiting.join(timeout=10)
        second.commit()
    finally:
        first.close()
        second.close()
    assert marked == {"first": True, "second": False}


def test_a_helpdesk_event_is_applied_once_through_the_handler(pg):
    """The real consumer on Postgres as the non-superuser role: a first created event starts both clocks, the same
    event again is a duplicate and changes nothing."""
    from dataclasses import dataclass
    from datetime import UTC, datetime

    from eos_core.tenant import organisation_scope
    from eos_sla_management.application.consumers import CONSUMERS
    from sqlalchemy import text

    @dataclass(frozen=True)
    class Event:
        id: str
        name: str
        organisation_id: str
        payload: dict
        version: int = 1
        actor: str | None = None
        occurred_at: datetime = datetime(2026, 11, 2, 9, tzinfo=UTC)

    engine, role = pg
    org, ticket, cal, policy = (str(uuid.uuid4()) for _ in range(4))
    setup = _session(engine, role, org)
    with organisation_scope(org):
        setup.execute(text(INSERTS["sla_management_calendar"]), {"id": cal, "org": org})
        setup.execute(
            text(
                "INSERT INTO sla_management_policy (id, organisation_id, created_at, name, priority, category_key, "
                "calendar_id, response_target_minutes, resolution_target_minutes, warning_percent, "
                "pause_on_hold_reasons, escalation_levels, active, updated_at) VALUES (:id, :org, now(), 'p', 'high', "
                "'*', :cal, 60, 240, 50, '[]', '[]', true, now())"
            ),
            {"id": policy, "org": org, "cal": cal},
        )
        setup.commit()
    setup.close()
    event = Event(
        id=str(uuid.uuid4()),
        name="helpdesk.ticket.created",
        organisation_id=org,
        payload={
            "ticket_id": ticket,
            "number": "HD-1",
            "category_id": None,
            "queue_id": None,
            "priority": "high",
            "created_at": "2026-11-02T09:00:00+00:00",
        },
    )
    results = []
    for _ in range(2):
        db = _session(engine, role, org)
        try:
            with organisation_scope(org):
                results.append(CONSUMERS[event.name](db, event))
                db.commit()
        finally:
            db.close()
    assert results == ["applied", "duplicate"]
    check = _session(engine, role, org)
    try:
        with organisation_scope(org):
            count = check.execute(text("SELECT count(*) FROM sla_management_clock WHERE ticket_id = :t"), {"t": ticket})
            assert count.scalar() == 2
    finally:
        check.close()
