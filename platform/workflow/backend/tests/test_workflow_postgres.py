"""PostgreSQL row-level security tests for workflow: proves tenant isolation as non-superuser eos_app across all 4 tables."""

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
DATABASE = "eos_workflow_pg"
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
    command.upgrade(cfg, "head")

    with _admin(DATABASE).begin() as conn:
        conn.execute(text(f"GRANT ALL ON ALL TABLES IN SCHEMA public TO {APP_ROLE}"))
        conn.execute(text(f"GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}"))

    engine = create_engine(_app_url(), future=True)
    yield engine
    engine.dispose()


def _as(conn, org: str | None, *, bypass: bool = False):
    conn.execute(text("SELECT set_config('app.organisation_id', :o, true)"), {"o": org or ""})
    conn.execute(text("SELECT set_config('app.bypass_rls', :b, true)"), {"b": "on" if bypass else "off"})


def _insert_chain(conn, org: str) -> str:
    cid = str(uuid.uuid4())
    code = f"code_{cid[:8]}"
    conn.execute(
        text(
            "INSERT INTO workflow_chain (id, organisation_id, code, title, is_active, created_at, updated_at) "
            "VALUES (:id, :org, :code, 'Title', true, now(), now())"
        ),
        {"id": cid, "org": org, "code": code},
    )
    return cid


def _insert_step(conn, org: str, chain_id: str) -> str:
    sid = str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO workflow_step (id, organisation_id, chain_id, step_order, name, approver_role, is_final, created_at) "
            "VALUES (:id, :org, :cid, 1, 'Review', 'org-admin', true, now())"
        ),
        {"id": sid, "org": org, "cid": chain_id},
    )
    return sid


def _insert_request(conn, org: str, chain_id: str) -> str:
    rid = str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO workflow_request (id, organisation_id, chain_id, entity_type, entity_id, title, requester_id, status, current_step_order, context, submitted_at) "
            "VALUES (:id, :org, :cid, 'expense', 'e-1', 'Test Request', 'user-1', 'pending', 1, '{}', now())"
        ),
        {"id": rid, "org": org, "cid": chain_id},
    )
    return rid


def _insert_action(conn, org: str, request_id: str) -> str:
    aid = str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO workflow_action (id, organisation_id, request_id, step_order, step_name, actor_id, action, occurred_at) "
            "VALUES (:id, :org, :rid, 1, 'Review', 'user-1', 'approved', now())"
        ),
        {"id": aid, "org": org, "rid": request_id},
    )
    return aid


def test_the_app_role_is_not_superuser_or_bypass(app_engine):
    with app_engine.connect() as conn:
        sup, bypass = conn.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
    assert not sup and not bypass


def test_organisation_isolation_on_all_tables(app_engine):
    # Setup rows for ORG_A
    with app_engine.begin() as conn:
        _as(conn, ORG_A)
        chain_a = _insert_chain(conn, ORG_A)
        step_a = _insert_step(conn, ORG_A, chain_a)
        req_a = _insert_request(conn, ORG_A, chain_a)
        act_a = _insert_action(conn, ORG_A, req_a)

    # Setup rows for ORG_B
    with app_engine.begin() as conn:
        _as(conn, ORG_B)
        chain_b = _insert_chain(conn, ORG_B)
        step_b = _insert_step(conn, ORG_B, chain_b)
        req_b = _insert_request(conn, ORG_B, chain_b)
        act_b = _insert_action(conn, ORG_B, req_b)

    # When connected as ORG_A:
    with app_engine.begin() as conn:
        _as(conn, ORG_A)
        # 1. workflow_chain
        chains = set(conn.execute(text("SELECT id FROM workflow_chain")).scalars())
        assert chain_a in chains
        assert chain_b not in chains

        # 2. workflow_step
        steps = set(conn.execute(text("SELECT id FROM workflow_step")).scalars())
        assert step_a in steps
        assert step_b not in steps

        # 3. workflow_request
        requests = set(conn.execute(text("SELECT id FROM workflow_request")).scalars())
        assert req_a in requests
        assert req_b not in requests

        # 4. workflow_action
        actions = set(conn.execute(text("SELECT id FROM workflow_action")).scalars())
        assert act_a in actions
        assert act_b not in actions


def test_organisation_cannot_write_into_another_on_any_table(app_engine):
    with app_engine.begin() as conn:
        _as(conn, ORG_A)
        chain_a = _insert_chain(conn, ORG_A)
        req_a = _insert_request(conn, ORG_A, chain_a)

    # 1. workflow_chain cross-org write refused
    with pytest.raises(DBAPIError), app_engine.begin() as conn:
        _as(conn, ORG_A)
        _insert_chain(conn, ORG_B)

    # 2. workflow_step cross-org write refused
    with pytest.raises(DBAPIError), app_engine.begin() as conn:
        _as(conn, ORG_A)
        _insert_step(conn, ORG_B, chain_a)

    # 3. workflow_request cross-org write refused
    with pytest.raises(DBAPIError), app_engine.begin() as conn:
        _as(conn, ORG_A)
        _insert_request(conn, ORG_B, chain_a)

    # 4. workflow_action cross-org write refused
    with pytest.raises(DBAPIError), app_engine.begin() as conn:
        _as(conn, ORG_A)
        _insert_action(conn, ORG_B, req_a)
