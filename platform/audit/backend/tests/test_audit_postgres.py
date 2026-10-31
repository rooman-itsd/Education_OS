"""What PostgreSQL guarantees for audit_record, which SQLite cannot express: row-level security and the
immutability trigger.

**Nothing here runs by default.** The module skips unless EOS_PG_ADMIN_URL points at a PostgreSQL a test may
freely create and drop databases on, for example:

    docker run -d --name eos-pg -e POSTGRES_PASSWORD=pg -p 5433:5432 postgres:16
    EOS_PG_ADMIN_URL=postgresql+psycopg://postgres:pg@localhost:5433/postgres \
      pytest tests/test_audit_postgres.py -q

The admin URL is used only for setup. Every assertion runs as `eos_app`, which is NOT a superuser and NOT
BYPASSRLS, and which is deliberately GRANTED update, delete and truncate: so a refusal here can only come from
the trigger, never from a missing privilege.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

ADMIN_URL = os.environ.get("EOS_PG_ADMIN_URL")
pytestmark = pytest.mark.skipif(not ADMIN_URL, reason="set EOS_PG_ADMIN_URL to run the PostgreSQL checks")

DB_DIR = Path(__file__).resolve().parents[2] / "db"
DATABASE = "eos_audit_pg"  # throwaway: dropped and recreated on every run
APP_ROLE = "eos_app"
APP_PASSWORD = "eos_app_test"
ORG_A = str(uuid.uuid4())
ORG_B = str(uuid.uuid4())


def _admin(database: str | None = None):
    url = ADMIN_URL if database is None else ADMIN_URL.rsplit("/", 1)[0] + "/" + database
    return create_engine(url, isolation_level="AUTOCOMMIT", future=True)


def _app_url() -> str:
    base = ADMIN_URL.rsplit("/", 1)[0]
    scheme, _, rest = base.partition("://")
    return f"{scheme}://{APP_ROLE}:{APP_PASSWORD}@{rest.rsplit('@', 1)[-1]}/{DATABASE}"


@pytest.fixture(scope="module")
def app_engine():
    with _admin().begin() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {DATABASE}"))
        if not conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": APP_ROLE}).scalar():
            conn.execute(text(f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{APP_PASSWORD}'"))
        conn.execute(text(f"ALTER ROLE {APP_ROLE} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"))
        conn.execute(text(f"CREATE DATABASE {DATABASE}"))
    cfg = Config(str(DB_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={ADMIN_URL.rsplit('/', 1)[0]}/{DATABASE}"]})()
    command.upgrade(cfg, "head")  # installs the policy and the trigger, exactly as a deployment would
    with _admin(DATABASE).begin() as conn:
        conn.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON audit_record TO {APP_ROLE}"))
    engine = create_engine(_app_url(), future=True)
    yield engine
    engine.dispose()


def _as(conn, org: str | None, *, bypass: bool = False) -> None:
    """What eos_core.db does on every transaction: set the tenant for this transaction only."""
    conn.execute(text("SELECT set_config('app.organisation_id', :o, true)"), {"o": org or ""})
    conn.execute(text("SELECT set_config('app.bypass_rls', :b, true)"), {"b": "on" if bypass else "off"})


def _insert(conn, org: str | None) -> str:
    rid = str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO audit_record (id, organisation_id, module, action, entity_type, entity_id, summary,"
            " before, after, context, occurred_at, redacted) VALUES (:id, :org, 'admissions',"
            " 'application.accepted', 'application', 'a1', 'Accepted', '{\"status\": \"submitted\"}',"
            " '{\"status\": \"accepted\"}', '{}', now(), false)"
        ),
        {"id": rid, "org": org},
    )
    return rid


def _row(app_engine, org: str | None = ORG_A) -> str:
    with app_engine.begin() as conn:
        _as(conn, org, bypass=org is None)
        return _insert(conn, org)


def _refused(app_engine, sql: str, rid: str, *, prune: bool = False) -> bool:
    try:
        with app_engine.begin() as conn:
            _as(conn, None, bypass=True)  # bypass on, so RLS cannot be the reason for a refusal
            if prune:
                conn.execute(text("SELECT set_config('audit.pruning', 'on', true)"))
            conn.execute(text(sql), {"id": rid})
    except DBAPIError as e:
        return "cannot be" in str(e.orig)
    return False


def test_the_app_role_has_no_way_around_a_policy(app_engine):
    with app_engine.connect() as conn:
        sup, bypass = conn.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
    assert not sup and not bypass


def test_an_organisation_sees_only_its_own_records(app_engine):
    mine = _row(app_engine, ORG_A)
    _row(app_engine, ORG_B)
    with app_engine.begin() as conn:
        _as(conn, ORG_A)
        assert set(conn.execute(text("SELECT id FROM audit_record")).scalars()) == {mine}


def test_platform_records_are_invisible_without_bypass(app_engine):
    platform = _row(app_engine, None)
    with app_engine.begin() as conn:
        _as(conn, ORG_A)
        assert platform not in set(conn.execute(text("SELECT id FROM audit_record")).scalars())


def test_an_organisation_cannot_write_into_another(app_engine):
    with pytest.raises(DBAPIError), app_engine.begin() as conn:
        _as(conn, ORG_A)
        _insert(conn, ORG_B)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE audit_record SET summary = 'rewritten' WHERE id = :id",
        "UPDATE audit_record SET action = 'application.rejected' WHERE id = :id",
        "UPDATE audit_record SET occurred_at = now() - interval '1 day' WHERE id = :id",
        "DELETE FROM audit_record WHERE id = :id",
    ],
)
def test_the_trigger_refuses_every_change_even_with_the_privilege(app_engine, sql):
    assert _refused(app_engine, sql, _row(app_engine))


def test_truncate_is_refused(app_engine):
    assert _refused(app_engine, "TRUNCATE audit_record", _row(app_engine))


def test_a_redaction_tombstone_is_the_one_allowed_update(app_engine):
    rid = _row(app_engine)
    tombstone = "UPDATE audit_record SET before = NULL, after = '{\"redacted\": true}', redacted = true WHERE id = :id"
    assert not _refused(app_engine, tombstone, rid)
    with app_engine.begin() as conn:
        _as(conn, None, bypass=True)
        summary, redacted = conn.execute(
            text("SELECT summary, redacted FROM audit_record WHERE id = :id"), {"id": rid}
        ).one()
    assert redacted and summary == "Accepted"  # the fact of the action survives


def test_a_redaction_cannot_carry_another_change_and_cannot_be_repeated(app_engine):
    rid = _row(app_engine)
    sneaky = "UPDATE audit_record SET after = NULL, redacted = true, summary = 'gone' WHERE id = :id"
    assert _refused(app_engine, sneaky, rid)
    assert not _refused(app_engine, "UPDATE audit_record SET after = NULL, redacted = true WHERE id = :id", rid)
    assert _refused(app_engine, "UPDATE audit_record SET before = NULL WHERE id = :id", rid)


def test_a_delete_is_allowed_only_inside_a_declared_prune(app_engine):
    rid = _row(app_engine)
    assert _refused(app_engine, "DELETE FROM audit_record WHERE id = :id", rid)
    assert not _refused(app_engine, "DELETE FROM audit_record WHERE id = :id", rid, prune=True)


def test_the_trigger_binds_a_superuser_too(app_engine):
    """Grants cannot stop a superuser; the trigger does."""
    rid = _row(app_engine)
    with pytest.raises(DBAPIError, match="cannot be altered"), _admin(DATABASE).begin() as conn:
        conn.execute(text("UPDATE audit_record SET summary = 'admin edit' WHERE id = :id"), {"id": rid})
