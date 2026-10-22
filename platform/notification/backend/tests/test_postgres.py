"""Blocker B4: the PostgreSQL checks. SQLite cannot express row-level security, and it does not enforce column
lengths, so every tenancy guarantee this module claims is unverified until these run.

**Nothing here runs by default.** The whole module skips unless EOS_PG_ADMIN_URL points at a PostgreSQL a test
may freely create and drop databases on, for example:

    docker run -d --name eos-pg -e POSTGRES_PASSWORD=pg -p 5433:5432 postgres:16
    EOS_PG_ADMIN_URL=postgresql+psycopg://postgres:pg@localhost:5433/postgres \
      pytest tests/test_postgres.py -q

The admin URL is used ONLY for setup: creating the `eos_app` role and the two databases. Every assertion runs on
a connection opened as `eos_app`, which is deliberately NOT a superuser and NOT BYPASSRLS — test_p2 asserts that
first, because a superuser silently passes every RLS check and would make this whole file lie.

Scope: these verify what the DATABASE guarantees — schema, policies, constraints, lengths, concurrency and
transaction semantics — through real connections and real SQL. Application behaviour on PostgreSQL (the service
layer bound to a PostgreSQL session) is NOT covered here; it needs the app wired to a PostgreSQL engine and is
still outstanding. Do not read a pass here as "the service works on PostgreSQL".
"""

from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError

ADMIN_URL = os.environ.get("EOS_PG_ADMIN_URL")
pytestmark = pytest.mark.skipif(not ADMIN_URL, reason="set EOS_PG_ADMIN_URL to run the PostgreSQL checks")

DB_DIR = Path(__file__).resolve().parents[2] / "db"
MIGRATION_DB = "eos_nmig"  # the migration runs here, on an empty database
BEHAVIOUR_DB = "eos_ntest"  # everything else runs here
APP_ROLE = "eos_app"
APP_PASSWORD = "eos_app_test"
TABLES = ("notification_message", "notification_template", "notification_preference")

ORG_A = str(uuid.uuid4())
ORG_B = str(uuid.uuid4())


def _app_url(database: str) -> str:
    base = ADMIN_URL.rsplit("/", 1)[0]
    scheme, _, rest = base.partition("://")
    host = rest.rsplit("@", 1)[-1]
    return f"{scheme}://{APP_ROLE}:{APP_PASSWORD}@{host}/{database}"


def _admin(database: str | None = None):
    url = ADMIN_URL if database is None else ADMIN_URL.rsplit("/", 1)[0] + "/" + database
    return create_engine(url, isolation_level="AUTOCOMMIT", future=True)


@pytest.fixture(scope="session")
def pg():
    """Create the role and both databases from scratch, migrate one, and hand back URLs for the eos_app role."""
    with _admin().begin() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {MIGRATION_DB}"))
        conn.execute(text(f"DROP DATABASE IF EXISTS {BEHAVIOUR_DB}"))
        exists = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": APP_ROLE}).scalar()
        if not exists:
            conn.execute(text(f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{APP_PASSWORD}'"))
        # explicit, not merely default: the whole file depends on this role having no way around a policy
        conn.execute(text(f"ALTER ROLE {APP_ROLE} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"))
        conn.execute(text(f"CREATE DATABASE {MIGRATION_DB}"))
        conn.execute(text(f"CREATE DATABASE {BEHAVIOUR_DB}"))

    for database in (MIGRATION_DB, BEHAVIOUR_DB):
        cfg = Config(str(DB_DIR / "alembic.ini"))
        admin_db_url = ADMIN_URL.rsplit("/", 1)[0] + "/" + database
        cfg.cmd_opts = type("Opts", (), {"x": [f"url={admin_db_url}"]})()
        command.upgrade(cfg, "head")
        with _admin(database).begin() as conn:
            for table in TABLES:
                # RLS is applied by eos_core.rls at deployment; mirror it here so the policy under test is the
                # one the platform actually installs.
                conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
                conn.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
                conn.execute(text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
                conn.execute(
                    text(
                        f"CREATE POLICY tenant_isolation ON {table} "
                        "USING (current_setting('app.bypass_rls', true) = 'on' "
                        "       OR organisation_id::text = current_setting('app.organisation_id', true)) "
                        "WITH CHECK (current_setting('app.bypass_rls', true) = 'on' "
                        "       OR organisation_id::text = current_setting('app.organisation_id', true))"
                    )
                )
                conn.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE}"))
    yield {"migration": _app_url(MIGRATION_DB), "behaviour": _app_url(BEHAVIOUR_DB)}


@pytest.fixture
def app_engine(pg):
    engine = create_engine(pg["behaviour"], future=True)
    yield engine
    engine.dispose()


def _as_org(conn, org: str | None, *, bypass: bool = False):
    """What eos_core.db does on every transaction: set the tenant for this transaction only."""
    conn.execute(text("SELECT set_config('app.organisation_id', :o, true)"), {"o": org or ""})
    conn.execute(text("SELECT set_config('app.bypass_rls', :b, true)"), {"b": "on" if bypass else "off"})


def _insert(conn, org: str, **over):
    row = {
        "id": str(uuid.uuid4()),
        "organisation_id": org,
        "template_key": "billing.trial.expired",
        "channel": "email",
        "category": "operational",
        "status": "queued",
        "recipient_key": "p@college.example.com",
        "variables": "{}",
        "body_template": "hello",
        "client_token": None,
        "source_event_id": None,
        "attempts": 0,
        "recovery_failures": 0,
    }
    row.update(over)
    conn.execute(
        text(
            "INSERT INTO notification_message (id, organisation_id, template_key, channel, category, status,"
            " recipient_key, variables, body_template, client_token, source_event_id, attempts,"
            " recovery_failures, created_at, updated_at)"
            " VALUES (:id, :organisation_id, :template_key, :channel, :category, :status, :recipient_key,"
            " CAST(:variables AS JSON), :body_template, :client_token, :source_event_id, :attempts,"
            " :recovery_failures, now(), now())"
        ),
        row,
    )
    return row["id"]


# --- P1: the migration ------------------------------------------------------------------------------------


def test_p1_the_migration_builds_the_schema_on_postgresql(pg):
    insp = inspect(create_engine(pg["migration"], future=True))
    present = set(insp.get_table_names())
    assert set(TABLES) <= present
    assert "notification_alembic_version" in present  # its own chain, not alembic_version
    uniques = {u["name"] for u in insp.get_unique_constraints("notification_message")}
    assert {"uq_notification_message_org_token", "uq_notification_message_org_event"} <= uniques


# --- P2: the role, and that the policies are real ---------------------------------------------------------


def test_p2_the_test_role_cannot_bypass_row_level_security(app_engine):
    """If this fails, every other assertion in this file is vacuous."""
    with app_engine.connect() as conn:
        is_super, bypasses = conn.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
    assert not is_super, "the tests must not run as a superuser: RLS would never be enforced"
    assert not bypasses, "the tests must not run as a BYPASSRLS role"


def test_p2_rls_is_enabled_and_forced_with_the_policy_on_every_tenant_table(app_engine):
    with app_engine.connect() as conn:
        for table in TABLES:
            enabled, forced = conn.execute(
                text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = :t"), {"t": table}
            ).one()
            assert enabled, f"{table} does not have row-level security enabled"
            assert forced, f"{table} does not FORCE row-level security, so its owner would bypass it"
            policies = (
                conn.execute(text("SELECT policyname FROM pg_policies WHERE tablename = :t"), {"t": table})
                .scalars()
                .all()
            )
            assert "tenant_isolation" in policies


# --- P3: cross-tenant reads and writes --------------------------------------------------------------------


def test_p3_one_organisation_cannot_read_another(app_engine):
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        mine = _insert(conn, ORG_A)
    with app_engine.begin() as conn:
        _as_org(conn, ORG_B)
        assert conn.execute(text("SELECT count(*) FROM notification_message WHERE id = :i"), {"i": mine}).scalar() == 0


def test_p3_an_insert_for_another_organisation_is_refused_by_with_check(app_engine):
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        with pytest.raises(DBAPIError):
            _insert(conn, ORG_B)  # the policy's WITH CHECK, not any application filter


def test_p3_a_row_cannot_be_moved_to_another_organisation(app_engine):
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        mine = _insert(conn, ORG_A)
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        with pytest.raises(DBAPIError):
            conn.execute(
                text("UPDATE notification_message SET organisation_id = :o WHERE id = :i"), {"o": ORG_B, "i": mine}
            )


def test_p3_no_organisation_context_sees_nothing_and_cannot_write(app_engine):
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        _insert(conn, ORG_A)
    with app_engine.begin() as conn:
        _as_org(conn, None)
        assert conn.execute(text("SELECT count(*) FROM notification_message")).scalar() == 0
        with pytest.raises(DBAPIError):
            _insert(conn, ORG_A)


def test_p3_an_empty_organisation_id_is_refused_by_the_check_constraint(app_engine):
    with app_engine.begin() as conn:
        _as_org(conn, "", bypass=True)  # bypass so it is the CHECK that refuses, not the policy
        with pytest.raises(DBAPIError):
            _insert(conn, "")


# --- P3b: tenant switching and the bypass -----------------------------------------------------------------


def test_p3_a_switch_inside_an_open_transaction_does_change_visibility(app_engine):
    """The safety here is NOT that PostgreSQL refuses a mid-transaction switch — it honours it immediately.
    This test pins that behaviour so it is tested rather than assumed.

    If this test fails, PostgreSQL did NOT switch tenant mid-transaction. That is a safer world than the one
    documented here, and the comment above should be corrected rather than the test deleted."""
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        _insert(conn, ORG_A)
    with app_engine.begin() as conn:
        _as_org(conn, ORG_B)
        assert conn.execute(text("SELECT count(*) FROM notification_message")).scalar() == 0
        _as_org(conn, ORG_A)  # a switch mid-transaction
        assert conn.execute(text("SELECT count(*) FROM notification_message")).scalar() > 0


def test_p3_a_pooled_connection_does_not_leak_the_previous_tenant(app_engine):
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        _insert(conn, ORG_A)
    with app_engine.connect() as conn:  # same pool, fresh transaction, nothing set
        assert conn.execute(text("SELECT current_setting('app.organisation_id', true)")).scalar() in (None, "")
        assert conn.execute(text("SELECT count(*) FROM notification_message")).scalar() == 0


def test_p3_the_platform_bypass_works_and_does_not_outlive_its_transaction(app_engine):
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        _insert(conn, ORG_A)
    with app_engine.begin() as conn:
        _as_org(conn, None, bypass=True)
        assert conn.execute(text("SELECT count(*) FROM notification_message")).scalar() > 0
    with app_engine.connect() as conn:
        assert conn.execute(text("SELECT current_setting('app.bypass_rls', true)")).scalar() in (None, "", "off")


# --- P4: uniqueness and races -----------------------------------------------------------------------------


def test_p4_client_token_is_unique_per_organisation_but_not_across_them(app_engine):
    token = "tok-" + uuid.uuid4().hex
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        _insert(conn, ORG_A, client_token=token)
    with app_engine.begin() as conn:
        _as_org(conn, ORG_B)
        _insert(conn, ORG_B, client_token=token)  # another tenant may reuse it
    with app_engine.begin() as conn, pytest.raises(IntegrityError):
        _as_org(conn, ORG_A)
        _insert(conn, ORG_A, client_token=token)


def test_p4_two_racing_inserts_of_the_same_event_leave_one_row(app_engine):
    event = str(uuid.uuid4())
    errors, barrier = [], threading.Barrier(2)

    def insert_once():
        try:
            with app_engine.begin() as conn:
                _as_org(conn, ORG_A)
                barrier.wait(timeout=10)
                _insert(conn, ORG_A, source_event_id=event, client_token="evt-" + event)
        except Exception as e:  # noqa: BLE001 - the loser's error is the point
            errors.append(type(e).__name__)

    threads = [threading.Thread(target=insert_once) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        rows = conn.execute(
            text("SELECT count(*) FROM notification_message WHERE source_event_id = :e"), {"e": event}
        ).scalar()
    assert rows == 1, f"expected one row, got {rows}; loser errors: {errors}"
    assert len(errors) == 1, "exactly one of the two inserts must fail"


def test_p4_two_connections_claiming_one_message_produce_one_winner(app_engine):
    """The guarded UPDATE the dispatcher uses: fenced by the attempt number, so only one claim can win."""
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        message_id = _insert(conn, ORG_A, status="queued", attempts=0)

    won, barrier = [], threading.Barrier(2)

    def claim():
        with app_engine.begin() as conn:
            _as_org(conn, ORG_A)
            barrier.wait(timeout=10)
            result = conn.execute(
                text(
                    "UPDATE notification_message SET status = 'sending', attempts = attempts + 1,"
                    " lease_expires_at = now() + interval '5 minutes'"
                    " WHERE id = :i AND status = 'queued' AND attempts = 0"
                ),
                {"i": message_id},
            )
            won.append(result.rowcount)

    threads = [threading.Thread(target=claim) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(won) == [0, 1], f"exactly one claim must win, got {won}"
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        attempts = conn.execute(
            text("SELECT attempts FROM notification_message WHERE id = :i"), {"i": message_id}
        ).scalar()
    assert attempts == 1, "the loser must not have incremented the attempt count"


# --- P5: lengths ------------------------------------------------------------------------------------------


def test_p5_column_lengths_are_enforced_unlike_sqlite(app_engine):
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        with pytest.raises(DBAPIError):
            _insert(conn, ORG_A, client_token="x" * 121)  # String(120)
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        with pytest.raises(DBAPIError):
            _insert(conn, ORG_A, source_event_id="x" * 37)  # String(36)


def test_p5_an_oversized_provider_message_id_is_refused_by_the_column(app_engine):
    """The exact failure the service-layer provider-id guard exists for. The SENT update runs AFTER the
    provider accepted the message, so a value the column cannot hold leaves the row in `sending` and recovery
    sends it a second time. SQLite stores 201 characters happily, so this is only real here. It is written as
    an UPDATE, not an INSERT, because the update is where it happened."""
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        message_id = _insert(conn, ORG_A, status="sending")
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        with pytest.raises(DBAPIError):
            conn.execute(
                text("UPDATE notification_message SET provider_message_id = :p WHERE id = :i"),
                {"p": "p" * 201, "i": message_id},  # String(200)
            )
    # and exactly 200 is accepted, so the guard's boundary is the column's and not a guess
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        conn.execute(
            text("UPDATE notification_message SET provider_message_id = :p WHERE id = :i"),
            {"p": "p" * 200, "i": message_id},
        )
        stored = conn.execute(
            text("SELECT provider_message_id FROM notification_message WHERE id = :i"), {"i": message_id}
        ).scalar()
    assert stored == "p" * 200


# --- P6: transaction semantics ------------------------------------------------------------------------------


def test_p6_a_savepoint_rolled_back_after_a_read_leaves_no_row(app_engine):
    """On SQLite with the default driver settings a savepoint opened after only a read commits when released.
    On PostgreSQL it must behave properly, so an accepted-then-rolled-back message leaves nothing behind."""
    probe = str(uuid.uuid4())
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        conn.execute(text("SELECT count(*) FROM notification_message"))  # a read first, as the service does
        conn.execute(text("SAVEPOINT sp"))
        _insert(conn, ORG_A, client_token=probe)
        conn.execute(text("ROLLBACK TO SAVEPOINT sp"))
    with app_engine.begin() as conn:
        _as_org(conn, ORG_A)
        assert (
            conn.execute(
                text("SELECT count(*) FROM notification_message WHERE client_token = :t"), {"t": probe}
            ).scalar()
            == 0
        )
