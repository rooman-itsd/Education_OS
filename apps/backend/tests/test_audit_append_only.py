"""audit_record is append-only for the role the API connects as (Postgres only; CI's Postgres step runs as eos_app
after infra/docker/migrate.sh, so this checks what a deployment leaves: db-roles.py's grants, the audit chain's
revokes, and db-roles.py's APPEND_ONLY re-revoke on the next deploy).

#317 audit, A3: eos_app held UPDATE, DELETE and TRUNCATE, and could delete a chosen record by setting
audit.pruning. Now it may only INSERT and SELECT; retention runs through audit_prune(), which keeps the floor."""

import uuid

import pytest
from eos_core.db import engine
from eos_core.settings import settings
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.skipif(not settings.is_postgres, reason="roles and grants are a Postgres feature")


def _platform(conn) -> None:
    conn.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))


def _insert() -> str:
    rid = str(uuid.uuid4())
    with engine.begin() as conn:
        _platform(conn)
        conn.execute(
            text(
                "INSERT INTO audit_record (id, organisation_id, actor, module, action, entity_type, entity_id,"
                " context, occurred_at, redacted) VALUES (:id, NULL, NULL, 'test', 'thing.recorded', 'thing', 't1',"
                " '{}', now(), false)"
            ),
            {"id": rid},
        )
    return rid


def test_the_api_role_appends_and_reads(client):
    rid = _insert()
    with engine.begin() as conn:
        _platform(conn)
        assert conn.execute(text("SELECT count(*) FROM audit_record WHERE id = :id"), {"id": rid}).scalar() == 1


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE audit_record SET summary = 'rewritten' WHERE id = :id",
        "DELETE FROM audit_record WHERE id = :id",
        "TRUNCATE audit_record",
    ],
)
def test_the_api_role_has_no_privilege_to_change_a_record(client, sql):
    rid = _insert()
    with pytest.raises(DBAPIError, match="permission denied"), engine.begin() as conn:
        _platform(conn)
        conn.execute(text("SELECT set_config('audit.pruning', 'on', true)"))  # the old bypass changes nothing
        conn.execute(text(sql), {"id": rid})


def test_retention_runs_only_through_audit_prune_and_keeps_the_floor(client):
    rid = _insert()
    with pytest.raises(DBAPIError, match="retention floor"), engine.begin() as conn:
        _platform(conn)
        conn.execute(text("SELECT audit_prune(now())"))
    with engine.begin() as conn:
        _platform(conn)
        assert conn.execute(text("SELECT audit_prune(now() - interval '2555 days')")).scalar() >= 0
        assert conn.execute(text("SELECT count(*) FROM audit_record WHERE id = :id"), {"id": rid}).scalar() == 1


def test_the_api_role_cannot_redact(client):
    rid = _insert()
    with pytest.raises(DBAPIError, match="permission denied"), engine.begin() as conn:
        _platform(conn)
        conn.execute(text("SELECT audit_redact(:id)"), {"id": rid})
