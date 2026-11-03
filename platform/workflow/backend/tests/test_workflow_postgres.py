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


# --- Concurrency: approve/reject/delegate lock the request row (audit follow-up for #317) -------------------


def _service_ready(app_engine):
    """The service writes outbox rows; this database only ran the workflow chain, so add the table."""
    from eos_core.events import OutboxEvent

    admin = _admin(DATABASE)
    OutboxEvent.__table__.create(admin, checkfirst=True)
    with admin.begin() as conn:
        conn.execute(text(f"GRANT ALL ON {OutboxEvent.__tablename__} TO {APP_ROLE}"))
    admin.dispose()


def _seed(app_engine, org: str, steps: list[dict]) -> str:
    from eos_core.tenant import organisation_scope
    from eos_workflow.application import service
    from sqlalchemy.orm import Session

    code = f"c{uuid.uuid4().hex[:8]}"
    with organisation_scope(org), Session(app_engine, expire_on_commit=False) as s:
        service.create_chain(s, org, code, "Chain", None, steps)
        req, _ = service.create_request(
            s, org, code, "leave", "e-1", "Leave", requester_id="requester", requester_name="R"
        )
        s.commit()
        return req.id


def _race(app_engine, org: str, request_id: str, first, second) -> object:
    """Run `first` and hold its transaction open; start `second` in another thread; prove it waits on the row
    lock; commit `first`; return what `second` ended with (HTTP-like status or 'applied')."""
    import threading

    from eos_core.tenant import organisation_scope
    from eos_workflow.application import service
    from sqlalchemy.orm import Session

    outcome: dict = {}

    def run_second():
        with organisation_scope(org), Session(app_engine) as s:
            try:
                second(s)
                s.commit()
                outcome["second"] = "applied"
            except service.WorkflowError as e:
                s.rollback()
                outcome["second"] = e.status

    with organisation_scope(org), Session(app_engine) as a:
        first(a)  # flushed, uncommitted: holds the row lock
        t = threading.Thread(target=run_second)
        t.start()
        t.join(1.0)
        assert t.is_alive(), "the second action did not wait for the first one's row lock"
        a.commit()
    t.join(15)
    assert not t.is_alive()
    return outcome["second"]


def _state(app_engine, org: str, request_id: str):
    with app_engine.begin() as conn:
        _as(conn, org)
        status, step = conn.execute(
            text("SELECT status, current_step_order FROM workflow_request WHERE id = :i"), {"i": request_id}
        ).one()
        actions = [
            r[0]
            for r in conn.execute(text("SELECT action FROM workflow_action WHERE request_id = :i"), {"i": request_id})
        ]
        topics = [
            r[0]
            for r in conn.execute(
                text("SELECT name FROM outbox_event WHERE payload ->> 'request_id' = :i"),
                {"i": request_id},
            )
        ]
    return status, step, actions, topics


def test_concurrent_approve_and_reject_cannot_both_apply(app_engine):
    from eos_workflow.application import service

    _service_ready(app_engine)
    org = str(uuid.uuid4())
    final = [{"step_order": 1, "name": "Director", "approver_role": "org-admin", "is_final": True}]
    rid = _seed(app_engine, org, final)

    second = _race(
        app_engine,
        org,
        rid,
        lambda s: service.approve_request(s, org, rid, "approver-a", "A", ["org-admin"]),
        lambda s: service.reject_request(s, org, rid, "approver-b", "B", ["org-admin"]),
    )
    assert second == 409
    status, _, actions, topics = _state(app_engine, org, rid)
    assert status == "approved"
    assert actions == ["approved"]
    assert "workflow.request.rejected" not in topics and topics.count("workflow.request.approved") == 1


def test_two_approvers_on_one_step_cannot_both_apply(app_engine):
    from eos_workflow.application import service

    _service_ready(app_engine)
    org = str(uuid.uuid4())
    two = [
        {"step_order": 1, "name": "HoD", "approver_role": "department-admin", "is_final": False},
        {"step_order": 2, "name": "Director", "approver_role": "department-admin", "is_final": True},
    ]
    rid = _seed(app_engine, org, two)

    second = _race(
        app_engine,
        org,
        rid,
        lambda s: service.approve_request(s, org, rid, "hod-a", "A", ["department-admin"], expected_step_order=1),
        lambda s: service.approve_request(s, org, rid, "hod-b", "B", ["department-admin"], expected_step_order=1),
    )
    assert second == 409
    status, step, actions, topics = _state(app_engine, org, rid)
    assert (status, step, actions) == ("pending", 2, ["approved"])
    assert topics.count("workflow.step.advanced") == 1


def test_two_sla_checks_at_once_escalate_a_step_once(app_engine):
    """The escalation row's unique key settles concurrent workflow.sla-check runs (PostgreSQL, eos_app, RLS)."""
    import threading
    from datetime import UTC, datetime, timedelta

    from eos_core.tenant import platform_scope
    from eos_workflow.application import service
    from sqlalchemy.orm import Session

    _service_ready(app_engine)
    with _admin(DATABASE).begin() as conn:
        conn.execute(text(f"GRANT ALL ON workflow_escalation TO {APP_ROLE}"))
    org = str(uuid.uuid4())
    rid = _seed(
        app_engine, org, [{"step_order": 1, "name": "HoD", "approver_role": "department-admin", "is_final": True}]
    )
    later = datetime.now(UTC) + timedelta(days=30)
    start = threading.Barrier(2)
    counts: list[int] = []

    def check():
        with platform_scope(), Session(app_engine) as s:
            start.wait()
            counts.append(service.escalate_overdue(s, now=later))

    threads = [threading.Thread(target=check) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(15)
    with app_engine.begin() as conn:
        _as(conn, org)
        rows = conn.execute(text("SELECT count(*) FROM workflow_escalation WHERE request_id = :r"), {"r": rid}).scalar()
        events = conn.execute(
            text(
                "SELECT count(*) FROM outbox_event WHERE name = 'workflow.step.overdue' AND payload ->> 'request_id' = :r"
            ),
            {"r": rid},
        ).scalar()
    # The shared database also holds other tests' overdue requests, which either check may escalate; this request's
    # step must be escalated exactly once between the two.
    assert len(counts) == 2 and rows == 1 and events == 1
