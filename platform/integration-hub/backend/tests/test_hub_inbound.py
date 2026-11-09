"""Provider callbacks: verification by the adapter over the raw body, handshakes, dedup, acknowledge first, then
processing into port events; provider requests answered synchronously."""

import json
from pathlib import Path

from eos_core.db import SessionLocal
from eos_integration_hub.application import deliveries
from hub_support import (
    BASE,
    audit_actions,
    authorised_meet,
    body,
    enabled_cert,
    key_of,
    link_account,
    outbox,
    wear_connection,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _fixture(name: str) -> bytes:
    return (FIXTURES / f"{name}.json").read_bytes()


def _signed(adapter, secret: str, raw: bytes, **headers) -> dict:
    return {"content-type": "application/json", "x-fake-signature": adapter.sign(secret, raw), **headers}


def _deliveries(client, org, **params):
    return client.get(f"{BASE}/deliveries", params=params, headers=org.admin).json()["items"]


def test_a_signed_webhook_is_acknowledged_then_processed_into_port_events(client, org, adapter):
    c = authorised_meet(client, org, adapter)
    # the meeting was created through the port, so the callback is matched to the module that asked
    from eos_integration_hub.application.invoke import invoke

    made = invoke(
        port="meetings",
        operation="create_meeting",
        input={"meeting_key": "class-session-1", "title": "T"},
        idempotency_key="lms:class-session:1",
        caller_reference="class-session-1",
        caller_module="lms",
        organisation_id=org.id,
    )
    assert made["status"] == "succeeded", made
    raw = _fixture("webhook_meeting_ended")
    r = client.post(
        f"{BASE}/inbound/fake-adapter/{key_of(c)}", content=raw, headers=_signed(adapter, "meet-client-secret", raw)
    )
    assert r.status_code == 200
    [ev] = outbox("integration-hub.meeting.ended", org.id)
    assert ev == {
        "organisation_id": org.id,
        "meeting_key": "class-session-1",
        "caller_module": "lms",
        "provider": "fakemeet",
        "ended_at": "2026-11-05T05:00:00+00:00",
    }
    [d] = _deliveries(client, org, direction="inbound")
    assert d["status"] == "succeeded" and d["operation"] == "meeting_ended" and d["connection_id"] == c["id"]
    # a redelivery of the same event id is acknowledged and ignored
    r = client.post(
        f"{BASE}/inbound/fake-adapter/{key_of(c)}", content=raw, headers=_signed(adapter, "meet-client-secret", raw)
    )
    assert r.status_code == 200
    assert len(outbox("integration-hub.meeting.ended", org.id)) == 1
    assert len(_deliveries(client, org, direction="inbound")) == 1


def test_a_tampered_or_unsigned_payload_is_rejected_logged_and_never_processed(client, org, adapter):
    c = authorised_meet(client, org, adapter)
    raw = _fixture("webhook_meeting_ended")
    tampered = raw.replace(b"class-session-1", b"class-session-9")
    url = f"{BASE}/inbound/fake-adapter/{key_of(c)}"
    r = client.post(url, content=tampered, headers=_signed(adapter, "meet-client-secret", raw))
    assert r.status_code == 401 and r.json()["code"] == "signature_invalid"
    r = client.post(url, content=raw, headers={"content-type": "application/json"})
    assert r.status_code == 401
    r = client.post(url, content=raw, headers=_signed(adapter, "another-secret", raw))
    assert r.status_code == 401
    assert outbox("integration-hub.meeting.ended", org.id) == []
    # counted, not one log row and one audit record each
    rejected = _deliveries(client, org, status="rejected_inbound")
    assert len(rejected) == 1 and rejected[0]["last_error_code"] == "signature_invalid"
    assert audit_actions(org.id).count("inbound.rejected") == 1
    assert _rejected_receipts(org.id) == [3]
    assert not [x for x in adapter.CALLS if x[0] == "parse_inbound"]


def _rejected_receipts(organisation_id: str | None, adapter_name: str = "fake-adapter") -> list[int]:
    from eos_core.tenant import platform_scope
    from eos_integration_hub.infrastructure.models import InboundReceipt
    from sqlalchemy import select

    with SessionLocal() as db, platform_scope():
        q = select(InboundReceipt.rejected_count).where(
            InboundReceipt.verdict == "rejected", InboundReceipt.adapter == adapter_name
        )
        q = q.where(InboundReceipt.organisation_id == organisation_id) if organisation_id else q
        return list(db.scalars(q.order_by(InboundReceipt.window_start)))


def test_unverified_requests_are_rate_limited_per_source_and_counted(client, org, adapter, monkeypatch, clock):
    monkeypatch.setenv("INTEGRATION_HUB_INBOUND_REJECT_LIMIT_PER_MIN", "3")
    c = authorised_meet(client, org, adapter)
    url = f"{BASE}/inbound/fake-adapter/{key_of(c)}"
    unsigned = {"content-type": "application/json"}
    clock.advance(seconds=-clock.now.second)  # the start of a minute
    assert [client.post(url, content=b"{}", headers=unsigned).status_code for _ in range(3)] == [401] * 3
    verifies = len([x for x in adapter.CALLS if x[0] == "verify_inbound"])
    r = client.post(url, content=b"{}", headers=unsigned)
    assert r.status_code == 429 and r.json()["code"] == "rate_limited" and r.headers["retry-after"] == "60"
    # over the limit: the adapter is not called and nothing is written
    assert client.post(url, content=b"{}", headers=unsigned).status_code == 429
    assert len([x for x in adapter.CALLS if x[0] == "verify_inbound"]) == verifies
    assert _rejected_receipts(org.id) == [3]
    # another source is not held back by this one: the app-level URL, keyed by the caller's address
    assert client.post(f"{BASE}/inbound/fake-adapter", content=b"{}", headers=unsigned).status_code == 401
    # the next minute opens a new window, still within the hour: counted, not audited again
    clock.advance(minutes=1)
    assert client.post(url, content=b"{}", headers=unsigned).status_code == 401
    assert _rejected_receipts(org.id) == [3, 1]
    assert audit_actions(org.id).count("inbound.rejected") == 1
    clock.advance(hours=2)
    assert client.post(url, content=b"{}", headers=unsigned).status_code == 401
    assert audit_actions(org.id).count("inbound.rejected") == 2
    # a signed request on the same URL is still accepted while rejections are counted
    raw = _fixture("webhook_meeting_ended")
    r = client.post(url, content=raw, headers=_signed(adapter, "meet-client-secret", raw))
    assert r.status_code == 200


def test_rejected_requests_are_kept_briefly(client, org, adapter, clock):
    c = authorised_meet(client, org, adapter)
    url = f"{BASE}/inbound/fake-adapter/{key_of(c)}"
    assert client.post(url, content=b"{}", headers={"content-type": "application/json"}).status_code == 401
    raw = _fixture("webhook_meeting_ended")
    assert client.post(url, content=raw, headers=_signed(adapter, "meet-client-secret", raw)).status_code == 200
    clock.advance(days=8)  # INTEGRATION_HUB_INBOUND_REJECTED_RETENTION_DAYS defaults to 7
    deliveries.purge()
    assert _rejected_receipts(org.id) == []
    assert _deliveries(client, org, status="rejected_inbound") == []
    assert len(_deliveries(client, org, direction="inbound")) == 1  # the accepted one stays (log retention)


def test_signature_is_checked_over_the_raw_bytes_not_reserialised_json(client, org, adapter):
    c = authorised_meet(client, org, adapter)
    raw = b'{"event":   "meeting.started", "event_id": "evt-raw-1",\n "payload": {"meeting_key": "k-raw", "started_at": "2026-11-05T04:00:00+00:00"}}'
    r = client.post(
        f"{BASE}/inbound/fake-adapter/{key_of(c)}", content=raw, headers=_signed(adapter, "meet-client-secret", raw)
    )
    assert r.status_code == 200
    assert outbox("integration-hub.meeting.started", org.id)[0]["meeting_key"] == "k-raw"


def test_handshakes_are_answered_by_the_adapter(client, org, adapter):
    c = authorised_meet(client, org, adapter)
    raw = _fixture("webhook_url_validation")
    r = client.post(
        f"{BASE}/inbound/fake-adapter/{key_of(c)}", content=raw, headers=_signed(adapter, "meet-client-secret", raw)
    )
    assert r.status_code == 200
    answer = r.json()
    assert answer["plainToken"] == "qgg8vlvZRS6UYooatFL8Aw" and len(answer["encryptedToken"]) == 64
    # Strava-style GET on the app-level URL
    r = client.get(
        f"{BASE}/inbound/fake-adapter",
        params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "15f7d1a91c1f40f8"},
    )
    assert r.status_code == 200 and r.json() == {"hub.challenge": "15f7d1a91c1f40f8"}
    r = client.get(f"{BASE}/inbound/fake-adapter", params={"hub.mode": "subscribe", "hub.verify_token": "wrong"})
    assert r.status_code == 404  # the status the provider expects on a wrong verification code


def test_unknown_adapters_keys_and_oversize_bodies(client, org, adapter, monkeypatch):
    c = authorised_meet(client, org, adapter)
    assert client.post(f"{BASE}/inbound/nope-adapter", content=b"{}").status_code == 404
    assert client.post(f"{BASE}/inbound/Bad!", content=b"{}").status_code == 404
    assert client.post(f"{BASE}/inbound/fake-adapter/{'A' * 43}", content=b"{}").status_code == 404
    assert client.post(f"{BASE}/inbound/fake-adapter/short", content=b"{}").status_code == 404
    monkeypatch.setenv("INTEGRATION_HUB_INBOUND_MAX_BYTES", "2048")
    big = b'{"x":"' + b"a" * 4096 + b'"}'
    r = client.post(
        f"{BASE}/inbound/fake-adapter/{key_of(c)}", content=big, headers=_signed(adapter, "meet-client-secret", big)
    )
    assert r.status_code == 413 and r.json()["code"] == "payload_too_large"


def test_an_app_level_callback_is_resolved_to_the_persons_link_and_runs_a_sync(client, org, adapter):
    wear_connection(client, org)
    link = link_account(client, org, subject="athlete-42", adapter=adapter)
    raw = body(
        {
            "event": "activity",
            "owner_id": "athlete-42",
            "event_id": "act-1",
            "payload": {"data_types": ["activity"], "from": "2026-11-04", "to": "2026-11-05"},
        }
    )
    r = client.post(f"{BASE}/inbound/fake-adapter", content=raw, headers=_signed(adapter, "app-level-signing-key", raw))
    assert r.status_code == 200
    # the follow-up sync is an async delivery; the sweep runs it
    deliveries.process_due()
    [ev] = outbox("integration-hub.wearable-data.received", org.id)
    assert ev == {
        "organisation_id": org.id,
        "account_link_id": link["id"],
        "person_id": org.ids["member"],
        "provider": "fakewear",
        "data_types": ["activity"],
        "from": "2026-11-04",
        "to": "2026-11-05",
    }
    mine = client.get(f"{BASE}/me/account-links", headers=org.member).json()["items"]
    assert mine[0]["last_synced_at"] is not None
    # a callback that names nobody is rejected
    raw = body({"event": "activity", "owner_id": "nobody", "event_id": "act-2"})
    r = client.post(f"{BASE}/inbound/fake-adapter", content=raw, headers=_signed(adapter, "app-level-signing-key", raw))
    assert r.status_code == 401
    # the provider says the athlete withdrew: the link ends and the adapter is told to delete the data
    raw = body({"event": "deauthorize", "owner_id": "athlete-42", "event_id": "deauth-1"})
    r = client.post(f"{BASE}/inbound/fake-adapter", content=raw, headers=_signed(adapter, "app-level-signing-key", raw))
    assert r.status_code == 200
    assert outbox("integration-hub.account-link.revoked", org.id)[-1]["cause"] == "revoked_at_provider"


def test_attendance_ready_fetches_the_report_and_publishes_person_ids_only(client, org, adapter):
    from eos_integration_hub.application.invoke import invoke

    c = authorised_meet(client, org, adapter)
    invoke(
        port="meetings",
        operation="create_meeting",
        input={"meeting_key": "cs-77"},
        idempotency_key="lms:cs-77",
        caller_reference="cs-77",
        caller_module="lms",
        organisation_id=org.id,
    )
    raw = body({"event": "attendance.ready", "event_id": "att-77", "payload": {"meeting_key": "cs-77"}})
    r = client.post(
        f"{BASE}/inbound/fake-adapter/{key_of(c)}", content=raw, headers=_signed(adapter, "meet-client-secret", raw)
    )
    assert r.status_code == 200
    deliveries.process_due()
    [ev] = outbox("integration-hub.meeting-attendance.received", org.id)
    assert ev["meeting_key"] == "cs-77" and ev["caller_module"] == "lms" and ev["complete"] is True
    assert ev["unmatched_count"] == 1 and len(ev["participants"]) == 2
    assert ev["participants"][1] == {
        "person_id": "0d9d1c52-3f3e-4d0f-9b51-7b3e0f6c9a02",
        "role": "attendee",
        "total_seconds": 1800,
        "first_joined_at": "2026-11-05T04:05:00+00:00",
        "last_left_at": "2026-11-05T04:45:00+00:00",
    }
    assert "@" not in json.dumps(ev) and "display_name" not in json.dumps(ev)


def test_a_disabled_connection_verifies_and_logs_but_does_not_process(client, org, adapter):
    c = authorised_meet(client, org, adapter)
    client.post(f"{BASE}/connections/{c['id']}/disable", json={"reason": "maintenance"}, headers=org.admin)
    raw = body({"event": "meeting.started", "event_id": "dis-1", "payload": {"meeting_key": "m"}})
    r = client.post(
        f"{BASE}/inbound/fake-adapter/{key_of(c)}", content=raw, headers=_signed(adapter, "meet-client-secret", raw)
    )
    assert r.status_code == 200
    [d] = _deliveries(client, org, direction="inbound")
    assert d["status"] == "failed" and d["last_error_code"] == "not_configured"
    assert outbox("integration-hub.meeting.started", org.id) == []


def test_a_provider_request_is_answered_synchronously_and_logged_without_the_answer(client, org, adapter):
    c = enabled_cert(client, org)
    raw = b'<PullURIRequest ver="1.0"><DocDetails><URI>x</URI></DocDetails></PullURIRequest>'
    headers = {"content-type": "application/xml", "x-fake-signature": adapter.sign("cert-webhook-secret", raw)}
    r = client.post(f"{BASE}/inbound/fake-adapter/{key_of(c)}/pull-uri", content=raw, headers=headers)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    assert b"<Status>1</Status>" in r.content
    [d] = _deliveries(client, org, direction="inbound")
    assert d["operation"] == "provider_request:pull-uri" and d["status"] == "succeeded"
    assert "PullURIResponse" not in json.dumps(d)
    r = client.post(f"{BASE}/inbound/fake-adapter/{key_of(c)}/Bad_Channel", content=raw, headers=headers)
    assert r.status_code == 404


def test_webhook_secret_rotation_rotates_the_inbound_url(client, org, adapter):
    c = enabled_cert(client, org)
    old = key_of(c)
    r = client.put(
        f"{BASE}/connections/{c['id']}/credentials/webhook_secret", json={"value": "new-secret"}, headers=org.admin
    )
    assert r.status_code == 200
    new = key_of(client.get(f"{BASE}/connections/{c['id']}", headers=org.admin).json())
    assert new != old
    raw = body({"event": "document.pulled", "event_id": "p-1", "payload": {"issuance_key": "k"}})
    assert (
        client.post(
            f"{BASE}/inbound/fake-adapter/{old}", content=raw, headers=_signed(adapter, "new-secret", raw)
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{BASE}/inbound/fake-adapter/{new}", content=raw, headers=_signed(adapter, "new-secret", raw)
        ).status_code
        == 200
    )


def test_the_same_event_id_at_two_organisations_connections_is_processed_for_each(client, org, other_org, adapter):
    """Dedupe is per connection: a provider's event ids are only unique within one account, so another
    organisation's event with the same id is never swallowed as a redelivery."""
    a = authorised_meet(client, org, adapter)
    b = authorised_meet(client, other_org, adapter)
    raw = _fixture("webhook_meeting_ended")
    for c in (a, b):
        r = client.post(
            f"{BASE}/inbound/fake-adapter/{key_of(c)}", content=raw, headers=_signed(adapter, "meet-client-secret", raw)
        )
        assert r.status_code == 200
    assert len(outbox("integration-hub.meeting.ended", org.id)) == 1
    assert len(outbox("integration-hub.meeting.ended", other_org.id)) == 1
    assert len(_deliveries(client, org, direction="inbound")) == 1
    assert len(_deliveries(client, other_org, direction="inbound")) == 1
    # and each connection still ignores its own redelivery
    r = client.post(
        f"{BASE}/inbound/fake-adapter/{key_of(b)}", content=raw, headers=_signed(adapter, "meet-client-secret", raw)
    )
    assert r.status_code == 200 and len(_deliveries(client, other_org, direction="inbound")) == 1


def _app_level(client, adapter, data: dict):
    raw = body(data)
    return client.post(
        f"{BASE}/inbound/fake-adapter", content=raw, headers=_signed(adapter, "app-level-signing-key", raw)
    )


def _link_status(client, org, who="member"):
    return [x["status"] for x in client.get(f"{BASE}/me/account-links", headers=org.headers[who]).json()["items"]]


def test_an_app_level_callback_resolves_only_to_an_active_link(client, org, other_org, adapter):
    """The same provider account linked in organisation A (active) and, later, in B (then revoked): the callback
    reaches A's link, never B's newer revoked one."""
    from eos_integration_hub.application import inbound

    subject = f"athlete-{org.id[:8]}"
    wear_connection(client, org)
    wear_connection(client, other_org)
    link_account(client, org, subject=subject, adapter=adapter)
    b_link = link_account(client, other_org, subject=subject, adapter=adapter)
    r = client.post(
        f"{BASE}/account-links/{b_link['id']}/revoke", json={"reason": "Left the academy"}, headers=other_org.admin
    )
    assert r.status_code == 200
    with SessionLocal() as db:
        from eos_core.tenant import platform_scope

        with platform_scope():
            c, link = inbound._resolve(db, "fake-adapter", {"account_link_subject": subject})
            assert link is not None and link.organisation_id == org.id and c.organisation_id == org.id
    r = _app_level(client, adapter, {"event": "deauthorize", "owner_id": subject, "event_id": f"d-{subject}"})
    assert r.status_code == 200
    assert _link_status(client, org) == ["revoked"]  # A's link was the one ended
    assert outbox("integration-hub.account-link.revoked", other_org.id)[-1]["cause"] == "revoked_by_admin"


def test_a_subject_active_in_two_organisations_is_not_guessed(client, org, other_org, adapter):
    subject = f"twin-{org.id[:8]}"
    wear_connection(client, org)
    wear_connection(client, other_org)
    link_account(client, org, subject=subject, adapter=adapter)
    link_account(client, other_org, subject=subject, adapter=adapter)
    r = _app_level(client, adapter, {"event": "deauthorize", "owner_id": subject, "event_id": f"d-{subject}"})
    assert r.status_code == 401  # ambiguous: rejected, neither link touched
    assert _link_status(client, org) == ["active"] and _link_status(client, other_org) == ["active"]


def test_a_named_connection_scopes_the_subject_to_its_organisation(client, org, other_org, adapter):
    subject = f"scoped-{org.id[:8]}"
    wear_connection(client, org)
    b = wear_connection(client, other_org)
    link_account(client, org, subject=subject, adapter=adapter)
    link_account(client, other_org, subject=subject, adapter=adapter)
    r = _app_level(
        client,
        adapter,
        {"event": "deauthorize", "owner_id": subject, "event_id": f"d2-{subject}", "connection_id": b["id"]},
    )
    assert r.status_code == 200
    assert _link_status(client, org) == ["active"] and _link_status(client, other_org) == ["revoked"]
