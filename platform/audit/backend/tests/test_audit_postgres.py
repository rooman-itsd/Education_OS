"""What PostgreSQL guarantees for audit_record, which SQLite cannot express: row-level security and the
immutability trigger.

**Nothing here runs by default.** The module skips unless EOS_PG_ADMIN_URL points at a PostgreSQL a test may
freely create and drop databases on, for example:

    docker run -d --name eos-pg -e POSTGRES_PASSWORD=pg -p 5433:5432 postgres:16
    EOS_PG_ADMIN_URL=postgresql+psycopg://postgres:pg@localhost:5433/postgres \
      pytest tests/test_audit_postgres.py -q

The admin URL is used only for setup. Every assertion runs as `eos_app`, which is NOT a superuser and NOT
BYPASSRLS. The trigger tests deliberately GRANT it update, delete and truncate after the migration has revoked
them (audit_0002): so a refusal there can only come from the trigger, never from a missing privilege. What the
migration itself leaves eos_app is checked from PRIVILEGES_AFTER_MIGRATION, recorded before that grant.
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


PRIVILEGES_AFTER_MIGRATION: dict[str, bool] = {}


@pytest.fixture(scope="module")
def app_engine():
    with _admin().begin() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {DATABASE}"))
        if not conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": APP_ROLE}).scalar():
            conn.execute(text(f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{APP_PASSWORD}'"))
        conn.execute(text(f"ALTER ROLE {APP_ROLE} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"))
        conn.execute(text(f"CREATE DATABASE {DATABASE}"))
    with _admin(DATABASE).begin() as conn:  # what infra/docker/db-roles.py sets before the chains run
        conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
        conn.execute(
            text(
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}"
            )
        )
    cfg = Config(str(DB_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={ADMIN_URL.rsplit('/', 1)[0]}/{DATABASE}"]})()
    command.upgrade(cfg, "head")  # installs the policy, the trigger and the revokes, exactly as a deployment would
    with _admin(DATABASE).begin() as conn:
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"):
            PRIVILEGES_AFTER_MIGRATION[privilege] = conn.execute(
                text("SELECT has_table_privilege(:r, 'audit_record', :p)"), {"r": APP_ROLE, "p": privilege}
            ).scalar()
        for fn, signature in (
            ("audit_prune", "audit_prune(timestamptz)"),
            ("audit_redact", "audit_redact(varchar)"),
            ("audit_redact_organisation", "audit_redact_organisation(varchar)"),
        ):
            PRIVILEGES_AFTER_MIGRATION[f"EXECUTE {fn}"] = conn.execute(
                text("SELECT has_function_privilege(:r, :f, 'EXECUTE')"), {"r": APP_ROLE, "f": signature}
            ).scalar()
        # The trigger tests below need the privilege, so a refusal there can only be the trigger's.
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


def test_the_application_role_cannot_redact_even_with_the_privilege(app_engine):
    """A tombstone written by eos_app itself: refused. Redaction is the owner's (audit_redact), maintenance only."""
    rid = _row(app_engine)
    tombstone = "UPDATE audit_record SET before = NULL, after = NULL, redacted = true WHERE id = :id"
    assert _refused(app_engine, tombstone, rid)


def test_the_owner_redacts_through_audit_redact_and_only_to_a_tombstone(app_engine):
    rid = _row(app_engine)
    with _admin(DATABASE).begin() as conn:
        _as(conn, None, bypass=True)
        assert conn.execute(text("SELECT audit_redact(:id)"), {"id": rid}).scalar() is True
        assert conn.execute(text("SELECT audit_redact(:id)"), {"id": rid}).scalar() is False  # not twice
        summary, redacted, before, after = conn.execute(
            text("SELECT summary, redacted, before, after FROM audit_record WHERE id = :id"), {"id": rid}
        ).one()
    assert redacted and summary == "Accepted" and before is None and after is None  # the fact survives


def test_a_tombstone_cannot_carry_another_change_even_for_the_owner(app_engine):
    rid = _row(app_engine)
    with pytest.raises(DBAPIError, match="cannot be altered"), _admin(DATABASE).begin() as conn:
        _as(conn, None, bypass=True)
        conn.execute(
            text(
                "UPDATE audit_record SET before = NULL, after = NULL, redacted = true, summary = 'gone' WHERE id = :id"
            ),
            {"id": rid},
        )


def test_the_pruning_flag_no_longer_lets_the_application_delete(app_engine):
    """The audit's A3 bypass: set audit.pruning, then DELETE one chosen record. Refused now."""
    rid = _row(app_engine)
    assert _refused(app_engine, "DELETE FROM audit_record WHERE id = :id", rid)
    assert _refused(app_engine, "DELETE FROM audit_record WHERE id = :id", rid, prune=True)


def test_audit_prune_removes_only_records_past_the_floor(app_engine):
    old, recent = _row(app_engine), _row(app_engine)
    with _admin(DATABASE).begin() as conn:  # backdate one record past the floor (as the owner, bypassing nothing)
        conn.execute(text("ALTER TABLE audit_record DISABLE TRIGGER audit_record_immutable"))
        conn.execute(
            text("UPDATE audit_record SET occurred_at = now() - interval '2600 days' WHERE id = :id"), {"id": old}
        )
        conn.execute(text("ALTER TABLE audit_record ENABLE TRIGGER audit_record_immutable"))
    with app_engine.begin() as conn:
        _as(conn, None, bypass=True)
        removed = conn.execute(text("SELECT audit_prune(now() - interval '2555 days')")).scalar()
        left = set(
            conn.execute(text("SELECT id FROM audit_record WHERE id IN (:a, :b)"), {"a": old, "b": recent}).scalars()
        )
    assert removed >= 1 and left == {recent}


def test_audit_prune_refuses_a_cutoff_inside_the_floor(app_engine):
    rid = _row(app_engine)
    with pytest.raises(DBAPIError, match="retention floor"), app_engine.begin() as conn:
        _as(conn, None, bypass=True)
        conn.execute(text("SELECT audit_prune(now())"))
    with app_engine.begin() as conn:
        _as(conn, None, bypass=True)
        assert conn.execute(text("SELECT count(*) FROM audit_record WHERE id = :id"), {"id": rid}).scalar() == 1


def test_the_migration_leaves_the_application_role_insert_and_select_only(app_engine):
    assert PRIVILEGES_AFTER_MIGRATION == {
        "SELECT": True,
        "INSERT": True,
        "UPDATE": False,
        "DELETE": False,
        "TRUNCATE": False,
        "EXECUTE audit_prune": True,
        "EXECUTE audit_redact": False,
        "EXECUTE audit_redact_organisation": True,
    }


def test_an_organisations_trail_is_redacted_only_once_it_no_longer_exists(app_engine):
    org = str(uuid.uuid4())
    rid = _row(app_engine, org)
    with _admin(DATABASE).begin() as conn:  # tenancy's table, as in a deployment, with the organisation still in it
        conn.execute(text("CREATE TABLE IF NOT EXISTS tenancy_organisation (id varchar(36) PRIMARY KEY)"))
        conn.execute(text("INSERT INTO tenancy_organisation (id) VALUES (:o)"), {"o": org})
    with pytest.raises(DBAPIError, match="still exists"), app_engine.begin() as conn:
        _as(conn, None, bypass=True)
        conn.execute(text("SELECT audit_redact_organisation(:o)"), {"o": org})
    with _admin(DATABASE).begin() as conn:  # the purge removed it
        conn.execute(text("DELETE FROM tenancy_organisation WHERE id = :o"), {"o": org})
    with app_engine.begin() as conn:
        _as(conn, None, bypass=True)
        assert conn.execute(text("SELECT audit_redact_organisation(:o)"), {"o": org}).scalar() == 1
        redacted, after, summary = conn.execute(
            text("SELECT redacted, after, summary FROM audit_record WHERE id = :id"), {"id": rid}
        ).one()
    assert redacted and after is None and summary == "Accepted"


def test_the_trigger_binds_a_superuser_too(app_engine):
    """Grants cannot stop a superuser; the trigger does."""
    rid = _row(app_engine)
    with pytest.raises(DBAPIError, match="cannot be altered"), _admin(DATABASE).begin() as conn:
        conn.execute(text("UPDATE audit_record SET summary = 'admin edit' WHERE id = :id"), {"id": rid})
