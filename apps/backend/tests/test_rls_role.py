"""Row-level security holds for the role the API connects as (Postgres only; CI's Postgres step runs as eos_app).

A superuser or a BYPASSRLS role skips every tenant_isolation policy, so the first test fails loudly if the API
is pointed at such a role. The second writes one row for organisation A under bypass, as platform_scope() does,
and reads it back as nobody, as organisation B and as A: only A may see it."""

import uuid

import pytest
from eos_core.db import engine
from eos_core.settings import settings
from sqlalchemy import text

pytestmark = pytest.mark.skipif(not settings.is_postgres, reason="row-level security is a Postgres feature")


def _scoped(conn, *, organisation: str = "", bypass: bool = False) -> None:
    conn.execute(text("SELECT set_config('app.organisation_id', :o, true)"), {"o": organisation})
    conn.execute(text("SELECT set_config('app.bypass_rls', :b, true)"), {"b": "on" if bypass else "off"})


def _visible(event_id: str, **scope) -> int:
    with engine.begin() as conn:
        _scoped(conn, **scope)
        return conn.execute(text("SELECT count(*) FROM outbox_event WHERE id = :id"), {"id": event_id}).scalar()


def test_the_api_role_cannot_skip_row_level_security(client):
    with engine.connect() as conn:
        name, superuser, bypass = conn.execute(
            text("SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
    assert not superuser and not bypass, f"the API connects as {name}, which skips row-level security"


def test_a_row_is_visible_only_to_its_organisation(client):
    org_a, org_b, event_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    with engine.begin() as conn:
        _scoped(conn, bypass=True)
        conn.execute(
            text(
                "INSERT INTO outbox_event (id, organisation_id, name, payload, occurred_at, published)"
                " VALUES (:id, :org, 'test.rls', '{}', now(), false)"
            ),
            {"id": event_id, "org": org_a},
        )
    try:
        assert _visible(event_id) == 0  # no app.organisation_id: nothing, never everything
        assert _visible(event_id, organisation=org_b) == 0
        assert _visible(event_id, organisation=org_a) == 1  # the row is there; the policy hid it above
    finally:
        with engine.begin() as conn:
            _scoped(conn, bypass=True)
            conn.execute(text("DELETE FROM outbox_event WHERE id = :id"), {"id": event_id})
