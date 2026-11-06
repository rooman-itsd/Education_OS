"""Scheduled jobs: each organisation's part runs as that organisation with row-level security on, never in the
caller's platform scope; and the event relay only hands a job over, it never waits for an adapter."""

import threading

import pytest
from eos_core.db import SessionLocal
from eos_core.tenant import get_current_organisation, is_bypass, platform_scope
from eos_integration_hub.application import authorisation, consumers, deliveries, health
from eos_integration_hub.application.jobs import HEALTH
from hub_support import BASE, authorised_meet, enabled_cert, key_of, link_account, wear_connection


@pytest.fixture
def tenants(monkeypatch):
    """(operation, the context's organisation, the organisation in scope, bypass on?) for every adapter call, taken
    in the hub's thread just before the adapter runs."""
    from eos_integration_hub.infrastructure import registry

    seen = []
    real = registry._run

    def run(fn, args, timeout_s):
        ctx = args[0]
        seen.append((getattr(fn, "__name__", "?"), ctx.organisation_id, get_current_organisation(), is_bypass()))
        return real(fn, args, timeout_s)

    monkeypatch.setattr(registry, "_run", run)
    return seen


def _event(job, run_id):
    return type("E", (), {"payload": {"job": job, "run_id": run_id}, "organisation_id": None})()


def test_jobs_run_each_organisations_work_as_that_organisation_without_bypass(
    client, org, other_org, adapter, clock, tenants
):
    from eos_integration_hub.application.invoke import invoke

    enabled_cert(client, org)
    made = invoke(
        port="certificate-issuance",
        operation="issue",
        input={"issuance_key": "j-1", "doc_kind": "marksheet", "holder": {"person_id": "p-1"}},
        idempotency_key="exam:j-1",
        caller_module="examinations",
        organisation_id=org.id,
    )
    assert made["status"] == "queued"
    c = authorised_meet(client, other_org, adapter)
    tenants.clear()
    raw = b'{"event": "meeting.started", "event_id": "j-evt", "payload": {"meeting_key": "k"}}'
    r = client.post(
        f"{BASE}/inbound/fake-adapter/{key_of(c)}",
        content=raw,
        headers={"content-type": "application/json", "x-fake-signature": adapter.sign("meet-client-secret", raw)},
    )
    assert r.status_code == 200  # processed right after the response (process_now), as its organisation too
    [after_response] = [t for t in tenants if t[0] == "parse_inbound"]
    assert after_response[1:] == (other_org.id, other_org.id, False)
    wear_connection(client, org)
    link_account(client, org)
    tenants.clear()  # from here on, only the jobs' calls
    with platform_scope():  # as the relay calls a platform job's consumer
        deliveries.process_due()
        clock.advance(hours=7)
        health.check_due()
        authorisation.refresh_due()
    ops = {op for op, *_ in tenants}
    assert {"issue", "healthcheck", "refresh_authorisation"} <= ops, ops
    # every call (other tests' connections in the shared database included) ran as the row's own organisation
    assert [t for t in tenants if not (t[1] == t[2] and t[3] is False)] == []
    assert [scope for op, _c, scope, _b in tenants if op == "issue"] == [org.id]


def test_the_relay_hands_a_job_over_and_never_waits_for_an_adapter(client, org, adapter, clock, monkeypatch):
    enabled_cert(client, org)
    clock.advance(minutes=20)  # due for its healthcheck
    release, entered = threading.Event(), threading.Event()
    real = adapter._record

    def slow(op, ctx):
        if op == "healthcheck":
            entered.set()
            release.wait(timeout=30)  # a provider that takes its time
        return real(op, ctx)

    monkeypatch.setattr(adapter, "_record", slow)
    with SessionLocal() as db, platform_scope():
        future = consumers.on_job_due(db, _event(HEALTH, "slow-1"))
        assert future is not None and not future.done()  # the relay's handler has returned already
        assert entered.wait(timeout=10)
        # a second due event while the run goes on is answered at once, not queued behind it
        assert consumers.on_job_due(db, _event(HEALTH, "slow-2")) is None
        db.commit()
    release.set()
    future.result(timeout=30)
    with SessionLocal() as db, platform_scope():
        from eos_core.events import OutboxEvent
        from sqlalchemy import select

        finished = {
            e.payload["run_id"]: e.payload
            for e in db.scalars(select(OutboxEvent).where(OutboxEvent.name == "integration-hub.job.finished"))
        }
    assert finished["slow-1"]["outcome"] == "succeeded" and "checked" in finished["slow-1"]["detail"]
    assert finished["slow-2"]["detail"].startswith("skipped")


def test_a_sweep_starts_no_new_attempt_after_its_budget(client, org, adapter):
    from eos_integration_hub.application.invoke import invoke

    enabled_cert(client, org)
    for i in range(3):
        invoke(
            port="certificate-issuance",
            operation="issue",
            input={"issuance_key": f"b-{i}", "doc_kind": "marksheet", "holder": {"person_id": "p-1"}},
            idempotency_key=f"exam:b-{i}",
            caller_module="examinations",
            organisation_id=org.id,
        )
    assert deliveries.process_due(budget_s=-1) == 1  # one at least, then the budget is spent
    assert deliveries.process_due() == 2
