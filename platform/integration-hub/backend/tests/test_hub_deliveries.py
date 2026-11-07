"""invoke (the modules' calling surface), the delivery log, retries with backoff, dead letters, manual retry and
retention."""

import json
from datetime import timedelta

import pytest
from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_integration_hub.application import deliveries
from eos_integration_hub.application.invoke import invoke
from eos_integration_hub.infrastructure.models import Delivery
from hub_support import BASE, audit_actions, authorised_meet, code, create, enabled_cert, outbox

HOLDER = "5b0e4a7e-58d4-4c39-8a1b-4f4b8b1f2c01"


def _issue(org, key="res-1:marksheet", **kw):
    payload = {
        "issuance_key": key,
        "doc_kind": "marksheet",
        "title": "B.Sc. Physics, Semester 4",
        "holder": {"person_id": HOLDER, "name": "Riya Sharma", "mobile": "+919845012345"},
    }
    args = {
        "port": "certificate-issuance",
        "operation": "issue",
        "input": payload,
        "idempotency_key": f"exam:{key}",
        "caller_reference": key,
        "caller_module": "examinations",
        "organisation_id": org.id,
    }
    args.update(kw)
    return invoke(**args)


def _sweep():
    return deliveries.process_due()


def _row(delivery_id):
    with SessionLocal() as db, platform_scope():
        return db.get(Delivery, delivery_id)


def test_not_configured_without_an_enabled_connection(client, org):
    r = _issue(org)
    assert r["status"] == "failed" and r["error"]["code"] == "not_configured" and r["delivery_id"] is None
    create(client, org)  # created but not enabled
    assert _issue(org)["error"]["code"] == "not_configured"


def test_bad_calls_answer_an_error_never_raise(client, org):
    enabled_cert(client, org)
    assert _issue(org, port="no-port")["error"]["code"] == "unsupported"
    assert _issue(org, operation="explode")["error"]["code"] == "unsupported"
    assert _issue(org, caller_module="Not A Module")["error"]["code"] == "invalid_request"
    assert _issue(org, idempotency_key="")["error"]["code"] == "invalid_request"
    assert _issue(org, idempotency_key="k" * 201)["error"]["code"] == "invalid_request"
    assert _issue(org, input={"x": float("nan")})["error"]["code"] == "invalid_request"
    assert _issue(org, input="not an object")["error"]["code"] == "invalid_request"
    assert _issue(org, organisation_id=None)["error"]["code"] == "invalid_request"  # no tenant in context
    assert _issue(org, provider="Bad Provider!")["error"]["code"] == "invalid_request"


def test_an_async_operation_returns_at_once_and_the_sweep_runs_it(client, org, adapter):
    enabled_cert(client, org)
    r = _issue(org)
    assert r["status"] == "queued" and r["delivery_id"] and r["output"] is None
    assert not [x for x in adapter.CALLS if x[0] == "issue"]  # nothing called yet
    row = _row(r["delivery_id"])
    assert row.payload_encrypted and b"Riya" not in row.payload_encrypted  # input kept encrypted, for retries only
    assert row.subject_key == "res-1:marksheet" and row.person_id == HOLDER and row.refs == {"doc_kind": "marksheet"}
    assert _sweep() >= 1
    [call] = [x for x in adapter.CALLS if x[0] == "issue"]
    assert call[1:] == ("sandbox", ("api_key", "webhook_secret"), "certificate-issuance")
    d = client.get(f"{BASE}/deliveries/{r['delivery_id']}", headers=org.admin).json()
    assert (
        d["status"] == "succeeded"
        and d["attempts"] == 1
        and d["provider_reference"] == "in.fake.issuer-MARKS-2026-0042"
    )
    assert [a["outcome"] for a in d["attempt_log"]] == ["succeeded"]
    assert "Riya" not in json.dumps(d) and "+9198" not in json.dumps(d)
    [ok] = outbox("integration-hub.delivery.succeeded", org.id)
    assert ok == {
        "organisation_id": org.id,
        "delivery_id": r["delivery_id"],
        "port": "certificate-issuance",
        "operation": "issue",
        "caller_module": "examinations",
        "caller_reference": "res-1:marksheet",
        "provider_reference": "in.fake.issuer-MARKS-2026-0042",
    }
    [issued] = outbox("integration-hub.certificate.issued", org.id)
    assert issued == {
        "organisation_id": org.id,
        "issuance_key": "res-1:marksheet",
        "person_id": HOLDER,
        "doc_kind": "marksheet",
        "status": "available_for_pull",
        "provider": "fakecert",
    }
    # withdraw names only the key: the person and kind come from the delivery that issued it
    w = invoke(
        port="certificate-issuance",
        operation="withdraw",
        input={"issuance_key": "res-1:marksheet", "reason": "issued in error"},
        idempotency_key="exam:w1",
        caller_module="examinations",
        organisation_id=org.id,
    )
    _sweep()
    assert _row(w["delivery_id"]).status == "succeeded"
    [wd] = outbox("integration-hub.certificate.withdrawn", org.id)
    assert wd["person_id"] == HOLDER and wd["doc_kind"] == "marksheet"


def test_the_same_idempotency_key_returns_the_first_delivery_and_never_calls_again(client, org, adapter, clock):
    enabled_cert(client, org)
    first = _issue(org)
    again = _issue(org)
    assert again["delivery_id"] == first["delivery_id"] and again["replayed"] is True
    _sweep()
    assert len([x for x in adapter.CALLS if x[0] == "issue"]) == 1
    # another module may use the same key string for its own call
    other = _issue(org, caller_module="admissions")
    assert other["delivery_id"] != first["delivery_id"]
    clock.advance(days=31)  # past INTEGRATION_HUB_IDEMPOTENCY_WINDOW_DAYS
    assert _issue(org)["delivery_id"] != first["delivery_id"]


def test_a_sync_operation_answers_now_and_a_retryable_failure_is_returned_as_is(client, org, adapter):
    authorised_meet(client, org, adapter)
    r = invoke(
        port="meetings",
        operation="create_meeting",
        input={"meeting_key": "s-1"},
        idempotency_key="lms:s-1",
        caller_module="lms",
        organisation_id=org.id,
    )
    assert r["status"] == "succeeded" and r["output"]["join_url"] == "https://meet.fake.example/j/85746065432"
    assert r["error"] is None
    adapter.SCRIPT["create_meeting"] = [{"error": {"code": "throttled", "retry_after_s": 30, "provider_code": "429"}}]
    r = invoke(
        port="meetings",
        operation="create_meeting",
        input={"meeting_key": "s-2"},
        idempotency_key="lms:s-2",
        caller_module="lms",
        organisation_id=org.id,
    )
    assert r["status"] == "failed" and r["error"]["code"] == "throttled" and r["error"]["retryable"] is True
    assert r["error"]["retry_after_s"] == 30
    assert outbox("integration-hub.delivery.failed", org.id) == []  # sync: the caller has the answer
    d = client.get(f"{BASE}/deliveries/{r['delivery_id']}", headers=org.admin).json()
    assert d["attempt_log"][0]["provider_code"] == "429"


def test_adapter_exceptions_unknown_codes_and_timeouts_become_error_codes(client, org, adapter, monkeypatch):
    import time

    authorised_meet(client, org, adapter)

    def call(key):
        return invoke(
            port="meetings",
            operation="create_meeting",
            input={"meeting_key": key},
            idempotency_key=f"lms:{key}",
            caller_module="lms",
            organisation_id=org.id,
        )

    adapter.SCRIPT["create_meeting"] = [RuntimeError("boom with secret meet-client-secret")]
    r = call("e-1")
    assert r["error"]["code"] == "provider_error" and "meet-client-secret" not in json.dumps(r)
    adapter.SCRIPT["create_meeting"] = [{"error": {"code": "vendor_said_no", "detail": "x" * 2000}}]
    r = call("e-2")
    assert r["error"]["code"] == "provider_error" and len(r["error"]["detail"]) <= 500
    adapter.SCRIPT["create_meeting"] = [{"error": {"code": "conflict", "retry_after_s": float("inf")}}]
    r = call("e-3")
    assert r["error"]["code"] == "conflict" and r["error"]["retryable"] is False and r["error"]["retry_after_s"] is None
    monkeypatch.setenv("INTEGRATION_HUB_SYNC_TIMEOUT_S", "1")
    original = type(adapter.FakeAdapter()).create_meeting

    def slow(self, ctx, payload):
        time.sleep(1.5)
        return original(self, ctx, payload)

    monkeypatch.setattr(adapter.FakeAdapter, "create_meeting", slow)
    from eos_integration_hub.infrastructure import registry

    registry.reset_cache()
    assert call("e-4")["error"]["code"] == "transport_unavailable"


def test_retryable_failures_back_off_then_dead_letter_and_a_manual_retry_runs_once_more(
    client, org, adapter, clock, monkeypatch
):
    monkeypatch.setenv("INTEGRATION_HUB_RETRY_MAX_ATTEMPTS", "3")
    enabled_cert(client, org)
    adapter.SCRIPT["issue"] = [{"error": {"code": "provider_error"}}] * 3
    r = _issue(org)
    _sweep()
    row = _row(r["delivery_id"])
    assert row.status == "retry_scheduled" and row.attempts == 1 and row.last_error_code == "provider_error"
    delay = (row.next_attempt_at.replace(tzinfo=clock.now.tzinfo) - clock.now).total_seconds()
    assert 1 <= delay <= 30  # full jitter under the first ceiling (30 s base)
    _sweep()
    assert _row(r["delivery_id"]).attempts == 1  # not due yet
    for _ in range(2):
        clock.advance(hours=7)
        _sweep()
    row = _row(r["delivery_id"])
    assert row.status == "dead_lettered" and row.attempts == 3
    [failed] = outbox("integration-hub.delivery.failed", org.id)
    assert failed["dead_lettered"] is True and failed["error_code"] == "provider_error"
    retried = client.post(f"{BASE}/deliveries/{r['delivery_id']}/retry", headers=org.admin)
    assert retried.status_code == 202 and retried.json()["status"] == "queued"
    assert "delivery.retried" in audit_actions(org.id)
    _sweep()
    assert _row(r["delivery_id"]).status == "succeeded"
    r2 = client.post(f"{BASE}/deliveries/{r['delivery_id']}/retry", headers=org.admin)
    assert r2.status_code == 409 and code(r2) == "not_retryable"
    assert client.post(f"{BASE}/deliveries/{r['delivery_id']}/retry", headers=org.member).status_code == 403


def test_a_non_retryable_failure_is_retryable_by_hand_only_after_the_connection_changed(client, org, adapter, clock):
    c = enabled_cert(client, org)
    adapter.SCRIPT["issue"] = [{"error": {"code": "auth_failed"}}]
    r = _issue(org)
    _sweep()
    assert _row(r["delivery_id"]).status == "failed"
    assert outbox("integration-hub.delivery.failed", org.id)[0]["dead_lettered"] is False
    url = f"{BASE}/deliveries/{r['delivery_id']}/retry"
    assert code(client.post(url, headers=org.admin)) == "not_retryable"
    clock.advance(minutes=1)
    client.put(f"{BASE}/connections/{c['id']}/credentials/api_key", json={"value": "fixed"}, headers=org.admin)
    assert client.post(url, headers=org.admin).status_code == 202


def test_throttling_holds_the_connections_queue(client, org, adapter, clock):
    enabled_cert(client, org)
    adapter.SCRIPT["issue"] = [{"error": {"code": "throttled", "retry_after_s": 600}}]
    first, second = _issue(org, key="t-1"), _issue(org, key="t-2")
    _sweep()
    assert _row(first["delivery_id"]).status == "retry_scheduled"
    second_row = _row(second["delivery_id"])
    assert second_row.attempts == 0  # held, not spent
    clock.advance(minutes=11)
    _sweep()
    assert _row(first["delivery_id"]).status == "succeeded" and _row(second["delivery_id"]).status == "succeeded"


def test_manual_action_required_is_its_own_outcome(client, org, adapter):
    enabled_cert(client, org)
    adapter.SCRIPT["issue"] = [{"error": {"code": "manual_action_required"}}]
    r = _issue(org)
    _sweep()
    assert _row(r["delivery_id"]).status == "manual_action_required"
    [ev] = outbox("integration-hub.delivery.manual-action-required", org.id)
    assert ev["caller_reference"] == "res-1:marksheet"


def test_a_disabled_connection_keeps_its_queue_until_it_expires(client, org, adapter, clock):
    c = enabled_cert(client, org)
    r = _issue(org)
    client.post(f"{BASE}/connections/{c['id']}/disable", headers=org.admin)
    _sweep()
    assert _row(r["delivery_id"]).status == "queued"
    client.post(f"{BASE}/connections/{c['id']}/enable", headers=org.admin)
    clock.advance(minutes=6)
    _sweep()
    assert _row(r["delivery_id"]).status == "succeeded"
    r2 = _issue(org, key="q-2")
    client.post(f"{BASE}/connections/{c['id']}/disable", headers=org.admin)
    clock.advance(hours=73)
    _sweep()
    row = _row(r2["delivery_id"])
    assert row.status == "failed" and row.last_error_code == "not_configured"


def test_deliveries_queued_in_one_mode_are_never_replayed_in_another(client, org, adapter):
    c = enabled_cert(client, org)
    r = _issue(org)
    client.post(f"{BASE}/connections/{c['id']}/mode", json={"mode": "live", "confirm_live": True}, headers=org.admin)
    _sweep()
    row = _row(r["delivery_id"])
    assert row.status == "failed" and row.last_error_code == "not_configured"
    assert not [x for x in adapter.CALLS if x[0] == "issue"]
    assert code(client.post(f"{BASE}/deliveries/{r['delivery_id']}/retry", headers=org.admin)) == "not_retryable"


def test_several_providers_for_a_port_need_the_caller_to_name_one(client, org, adapter):
    enabled_cert(client, org)
    # a second provider on the same port: fakecert again under another connection is the same provider, so add a
    # meetings connection and check the per-port rule with the meetings port instead
    authorised_meet(client, org, adapter)
    r = invoke(
        port="meetings",
        operation="create_meeting",
        input={"meeting_key": "p-1"},
        idempotency_key="lms:p-1",
        caller_module="lms",
        organisation_id=org.id,
        provider="fakecert",
    )
    assert r["error"]["code"] == "not_configured"  # fakecert does not serve meetings
    r = invoke(
        port="meetings",
        operation="create_meeting",
        input={"meeting_key": "p-2"},
        idempotency_key="lms:p-2",
        caller_module="lms",
        organisation_id=org.id,
        provider="fakemeet",
    )
    assert r["status"] == "succeeded"


def test_an_operation_for_a_person_needs_their_active_link(client, org, adapter):
    from hub_support import link_account, wear_connection

    wear_connection(client, org)
    link = link_account(client, org)
    args = {
        "port": "wearable-data",
        "operation": "sync",
        "idempotency_key": "ap:sync-1",
        "caller_module": "athlete-performance",
        "organisation_id": org.id,
    }
    r = invoke(input={"account_link_id": "00000000-0000-0000-0000-000000000000", "data_types": ["sleep"]}, **args)
    assert r["error"]["code"] == "consent_required"
    r = invoke(
        input={"account_link_id": link["id"], "data_types": ["sleep"], "from": "2026-11-01", "to": "2026-11-04"},
        **{**args, "idempotency_key": "ap:sync-2"},
    )
    _sweep()
    assert _row(r["delivery_id"]).status == "succeeded"
    [call] = [x for x in adapter.CALLS if x[0] == "sync"]
    assert "access_token" in call[2]  # the person's token reached the adapter for this call


def test_retention_purges_inputs_raw_callbacks_and_old_rows(client, org, adapter, clock):
    enabled_cert(client, org)
    r = _issue(org)
    _sweep()
    clock.advance(days=31)
    deliveries.purge()
    assert _row(r["delivery_id"]).payload_encrypted is None
    clock.advance(days=400)
    deliveries.purge()
    assert _row(r["delivery_id"]) is None


def test_listing_filters_and_pages(client, org, adapter):
    enabled_cert(client, org)
    for i in range(3):
        _issue(org, key=f"l-{i}")
    page = client.get(
        f"{BASE}/deliveries", params={"limit": 2, "status": "queued,retry_scheduled"}, headers=org.admin
    ).json()
    assert len(page["items"]) == 2 and page["next_cursor"] == "2"
    rest = client.get(f"{BASE}/deliveries", params={"limit": 2, "cursor": "2"}, headers=org.admin).json()
    assert len(rest["items"]) == 1 and rest["next_cursor"] is None
    only = client.get(f"{BASE}/deliveries", params={"caller_reference": "l-1"}, headers=org.admin).json()["items"]
    assert [d["caller_reference"] for d in only] == ["l-1"]
    assert client.get(f"{BASE}/deliveries", headers=org.member).status_code == 403


@pytest.mark.parametrize("attempt,ceiling", [(1, 30), (2, 60), (5, 480), (12, 21600), (60, 21600)])
def test_backoff_has_full_jitter_under_an_exponential_cap(attempt, ceiling):
    from eos_integration_hub.domain.rules import backoff_s

    assert backoff_s(attempt, base_s=30, max_s=21600, rng=lambda: 0.999999) in (ceiling - 1, ceiling)
    assert backoff_s(attempt, base_s=30, max_s=21600, rng=lambda: 0.0) == 1
    assert backoff_s(attempt, base_s=30, max_s=21600, retry_after_s=99999, rng=lambda: 0.0) == 21600
    assert backoff_s(1, base_s=30, max_s=21600, retry_after_s=120, rng=lambda: 0.0) == 120


def test_sweep_leaves_rows_of_a_missing_adapter_failed_not_crashed(client, org, adapter, monkeypatch):
    enabled_cert(client, org)
    r = _issue(org)
    monkeypatch.setenv("INTEGRATION_HUB_ADAPTERS", "some-other-adapter")
    from eos_integration_hub.infrastructure import registry

    registry.reset_cache()
    _sweep()
    row = _row(r["delivery_id"])
    assert row.last_error_code == "not_configured"
    assert row.status == "failed"
    assert row.next_attempt_at is None or row.next_attempt_at > (row.created_at - timedelta(days=1))


def test_the_idempotency_key_is_unique_in_the_table():
    [ix] = [i for i in Delivery.__table__.indexes if i.name == "ix_integration_hub_delivery_idempotency"]
    assert ix.unique and [c.name for c in ix.columns] == ["organisation_id", "caller_module", "idempotency_key"]


def test_two_invokes_racing_with_one_key_insert_one_delivery(client, org, adapter, monkeypatch):
    """Both calls find no delivery for the key before either inserts: the unique index lets one insert, and the
    other answers with the winner's delivery, replayed, without calling the provider."""
    import threading

    enabled_cert(client, org)
    barrier = threading.Barrier(2)
    real = deliveries.enqueue

    def enqueue_after_both_checked(*a, **kw):
        try:
            barrier.wait(timeout=2)
        except threading.BrokenBarrierError:
            pass
        return real(*a, **kw)

    monkeypatch.setattr(deliveries, "enqueue", enqueue_after_both_checked)
    results = []
    threads = [threading.Thread(target=lambda: results.append(_issue(org, key="race-1"))) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    monkeypatch.setattr(deliveries, "enqueue", real)
    assert len(results) == 2 and len({r["delivery_id"] for r in results}) == 1, results
    assert sorted(r["replayed"] for r in results) == [False, True]
    _sweep()
    assert len([x for x in adapter.CALLS if x[0] == "issue"]) == 1
    with SessionLocal() as db, platform_scope():
        rows = db.query(Delivery).filter(Delivery.organisation_id == org.id, Delivery.idempotency_key == "exam:race-1")
        assert rows.count() == 1
