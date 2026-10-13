"""The payer's journey through the gateway: redirect, callback, double verification, events, notifications."""

import json
from datetime import timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from eos_core.db import SessionLocal, utcnow
from eos_core.tenant import platform_scope
from eos_payment_sbiepay.application import service
from eos_payment_sbiepay.domain.models import Notification, Payment
from eos_payment_sbiepay.infrastructure import notifier
from eos_payment_sbiepay.infrastructure.gateway import MockGateway, VerifyResult
from sbiepay_support import NOTIFY_SECRET, PREFIX, browser_pays, outbox, start
from sqlalchemy import select


def _payment(reference: str) -> Payment:
    db = SessionLocal()
    try:
        with platform_scope():
            return db.scalar(select(Payment).where(Payment.reference == reference))
    finally:
        db.close()


def test_successful_payment(client, org, receiver):
    s = start(client, org.admin)
    r = browser_pays(client, s)
    assert r.status_code == 303
    back = urlparse(r.headers["location"])
    assert back.netloc == "college.example.com"
    assert parse_qs(back.query) == {"reference": [s["reference"]], "status": ["succeeded"]}

    p = client.get(f"{PREFIX}/payments/{s['reference']}", headers=org.admin).json()
    assert p["status"] == "succeeded" and p["gateway_transaction_id"] and p["completed_at"]

    [ev] = outbox("payment-sbiepay.payment.succeeded", org.id)
    assert ev.payload["reference"] == s["reference"] and ev.payload["organisation_id"] == org.id
    assert ev.payload["amount"] == "1500.00" and ev.payload["source_module"] == "billing"

    [req] = receiver.requests
    assert str(req.url) == "https://api.example.com/api/v1/billing/webhooks/payment"
    assert notifier.verify_signature(req.content, req.headers[notifier.SIGNATURE_HEADER], NOTIFY_SECRET)
    body = json.loads(req.content)
    assert body["event_id"] == ev.id and body["event"] == "payment-sbiepay.payment.succeeded"
    assert body["status"] == "succeeded" and body["organisation_id"] == org.id


def test_repeated_callbacks_change_nothing(client, org, receiver):
    s = start(client, org.admin)
    browser_pays(client, s)
    again = client.post(
        f"{PREFIX}/callbacks/sbiepay",
        data={"mock_reference": s["reference"], "mock_outcome": "failure"},
        follow_redirects=False,
    )
    assert again.status_code == 303 and "status=succeeded" in again.headers["location"]
    assert len(outbox("payment-sbiepay.payment.succeeded", org.id)) == 1
    assert outbox("payment-sbiepay.payment.failed", org.id) == []
    assert len(receiver.requests) == 1


def test_failed_and_cancelled_payments(client, org):
    for outcome in ("failure", "cancel"):
        s = start(client, org.admin)
        r = browser_pays(client, s, outcome)
        assert "status=failed" in r.headers["location"]
    reasons = {e.payload["failure_reason"] for e in outbox("payment-sbiepay.payment.failed", org.id)}
    assert reasons == {"declined by mock gateway", "cancelled by payer"}


def test_browser_response_alone_is_never_trusted(client, org):
    """The gateway's own answer decides: an amount mismatch fails the payment even if the browser said success."""
    s = start(client, org.admin)
    MockGateway.transactions[s["reference"]] = VerifyResult(
        "succeeded", gateway_transaction_id="T1", payment_mode="card", amount=Decimal("1.00")
    )
    r = browser_pays(client, s)
    assert "status=failed" in r.headers["location"]
    p = client.get(f"{PREFIX}/payments/{s['reference']}", headers=org.admin).json()
    assert "differs" in p["failure_reason"]


def test_gateway_says_pending_keeps_the_payment_pending(client, org):
    s = start(client, org.admin)
    MockGateway.transactions[s["reference"]] = VerifyResult("pending")
    r = browser_pays(client, s)
    assert "status=pending" in r.headers["location"]
    MockGateway.transactions[s["reference"]] = VerifyResult(
        "succeeded", gateway_transaction_id="T2", payment_mode="upi"
    )
    v = client.post(f"{PREFIX}/payments/{s['reference']}/verify", headers=org.staff)
    assert v.status_code == 200 and v.json()["status"] == "succeeded"


def test_redirect_refuses_finished_or_unknown_payments(client, org):
    s = start(client, org.admin)
    browser_pays(client, s)
    assert client.get(s["payment_url"]).status_code == 410
    assert client.get(f"{PREFIX}/payments/NOPE/redirect").status_code == 410


def test_redirect_page_escapes_and_posts_to_the_callback(client, org):
    s = start(client, org.admin)
    page = client.get(s["payment_url"])
    assert page.headers["content-type"].startswith("text/html")
    assert f'action="{PREFIX}/callbacks/sbiepay"' in page.text
    assert _payment(s["reference"]).status == "pending"


def test_unreadable_or_unknown_gateway_responses(client):
    assert client.post(f"{PREFIX}/callbacks/sbiepay", data={"x": "y"}).status_code == 400
    r = client.post(f"{PREFIX}/callbacks/sbiepay", data={"mock_reference": "EOSUNKNOWN", "mock_outcome": "success"})
    assert r.status_code == 400


def test_sweep_expires_unopened_and_abandoned_payments(client, org, monkeypatch):
    unopened = start(client, org.admin)
    abandoned = start(client, org.admin)
    client.get(abandoned["payment_url"])  # browser went to the gateway and never came back
    db = SessionLocal()
    try:
        with platform_scope():
            for p in db.scalars(
                select(Payment).where(Payment.reference.in_([unopened["reference"], abandoned["reference"]]))
            ):
                p.expires_at = utcnow() - timedelta(minutes=1)
                p.created_at = utcnow() - timedelta(hours=1)
            db.commit()
        assert service.sweep_open_payments(db) >= 2
    finally:
        db.close()
    assert _payment(unopened["reference"]).status == "expired"
    assert _payment(abandoned["reference"]).status == "expired"
    expired = {e.payload["reference"] for e in outbox("payment-sbiepay.payment.expired", org.id)}
    assert {unopened["reference"], abandoned["reference"]} <= expired


def test_expired_unopened_session_lets_the_caller_start_again(client, org):
    s = start(client, org.admin, source_reference="invoice-42")
    db = SessionLocal()
    try:
        with platform_scope():
            db.scalar(select(Payment).where(Payment.reference == s["reference"])).expires_at = utcnow() - timedelta(
                minutes=1
            )
            db.commit()
    finally:
        db.close()
    again = start(client, org.admin, source_reference="invoice-42")
    assert again["reference"] != s["reference"]
    assert _payment(s["reference"]).status == "expired"


def test_failed_notifications_are_retried(client, org, receiver):
    receiver.status = 500
    s = start(client, org.admin)
    browser_pays(client, s)
    db = SessionLocal()
    try:
        with platform_scope():
            n = db.scalar(select(Notification).where(Notification.body["reference"].as_string() == s["reference"]))
            assert n.delivered_at is None and n.attempts == 1 and "500" in n.last_error
            n.next_attempt_at = utcnow() - timedelta(seconds=1)
            db.commit()
        receiver.status = 200
        assert service.deliver_notifications(db) >= 1
        with platform_scope():
            n = db.get(Notification, n.id)
            assert n.delivered_at is not None and n.attempts == 2
    finally:
        db.close()
    first, second = [q for q in receiver.requests if json.loads(q.content)["reference"] == s["reference"]]
    assert first.content == second.content  # same event_id, so the receiver can de-duplicate


def test_signature_helpers():
    raw = notifier.encode({"b": 1, "a": "x"})
    assert raw == b'{"a":"x","b":1}'
    sig = notifier.sign(raw, "k")
    assert notifier.verify_signature(raw, sig, "k")
    assert not notifier.verify_signature(raw + b" ", sig, "k")
    assert not notifier.verify_signature(raw, sig, "")


def _force_expired(reference: str) -> None:
    db = SessionLocal()
    try:
        with platform_scope():
            p = db.scalar(select(Payment).where(Payment.reference == reference))
            p.expires_at = utcnow() - timedelta(minutes=1)
            p.created_at = utcnow() - timedelta(hours=1)
            db.commit()
        service.sweep_open_payments(db)
    finally:
        db.close()


def _events(name: str, org_id: str, reference: str) -> list:
    return [e for e in outbox(name, org_id) if e.payload["reference"] == reference]


def test_payer_who_finishes_after_the_sweep_expired_the_session_is_paid(client, org):
    """The gateway is the truth: an expired payment that the gateway confirms becomes succeeded, once."""
    s = start(client, org.admin)
    assert client.get(s["payment_url"]).status_code == 200  # payer is at the gateway
    _force_expired(s["reference"])
    assert _payment(s["reference"]).status == "expired"
    r = client.post(
        f"{PREFIX}/callbacks/sbiepay",
        data={"mock_reference": s["reference"], "mock_outcome": "success"},
        follow_redirects=False,
    )
    assert "status=succeeded" in r.headers["location"]
    assert len(_events("payment-sbiepay.payment.succeeded", org.id, s["reference"])) == 1


def test_verify_picks_up_a_late_success(client, org):
    s = start(client, org.admin)
    client.get(s["payment_url"])
    _force_expired(s["reference"])
    MockGateway.transactions[s["reference"]] = VerifyResult(
        "succeeded", gateway_transaction_id="LATE", payment_mode="upi"
    )
    v = client.post(f"{PREFIX}/payments/{s['reference']}/verify", headers=org.staff)
    assert v.json()["status"] == "succeeded" and v.json()["gateway_transaction_id"] == "LATE"


def test_a_late_failure_does_not_reopen_an_expired_payment(client, org):
    s = start(client, org.admin)
    client.get(s["payment_url"])
    _force_expired(s["reference"])
    r = client.post(
        f"{PREFIX}/callbacks/sbiepay",
        data={"mock_reference": s["reference"], "mock_outcome": "failure"},
        follow_redirects=False,
    )
    assert "status=expired" in r.headers["location"]
    assert _events("payment-sbiepay.payment.failed", org.id, s["reference"]) == []


def test_a_stale_copy_cannot_apply_the_final_status_twice(client, org, receiver):
    """Callback and verify (or the sweep) racing: whoever loaded the payment earlier must not publish again."""
    from eos_core.tenant import organisation_scope

    s = start(client, org.admin)
    client.get(s["payment_url"])
    db = SessionLocal()
    try:
        with platform_scope():
            stale = db.scalar(select(Payment).where(Payment.reference == s["reference"]))
            db.commit()
        assert stale.status == "pending"
        r = client.post(
            f"{PREFIX}/callbacks/sbiepay",
            data={"mock_reference": s["reference"], "mock_outcome": "success"},
            follow_redirects=False,
        )
        assert "status=succeeded" in r.headers["location"]
        with organisation_scope(org.id):
            service._apply(db, stale, VerifyResult("succeeded", gateway_transaction_id="X", payment_mode="card"))
            db.commit()
        assert stale.status == "succeeded" and stale.gateway_transaction_id != "X"
    finally:
        db.close()
    assert len(_events("payment-sbiepay.payment.succeeded", org.id, s["reference"])) == 1
    assert len([q for q in receiver.requests if json.loads(q.content)["reference"] == s["reference"]]) == 1


def test_one_gateway_error_does_not_stop_the_sweep(client, org, monkeypatch):
    from eos_payment_sbiepay.infrastructure.gateway import GatewayUnavailableError

    broken, fine = start(client, org.admin), start(client, org.admin)
    for s in (broken, fine):
        client.get(s["payment_url"])
    real_verify = MockGateway.verify

    def verify(self, order):
        if order.reference == broken["reference"]:
            raise GatewayUnavailableError("gateway down for this one")
        return real_verify(self, order)

    monkeypatch.setattr(MockGateway, "verify", verify)
    db = SessionLocal()
    try:
        with platform_scope():
            refs = [broken["reference"], fine["reference"]]
            for p in db.scalars(select(Payment).where(Payment.reference.in_(refs))):
                p.expires_at = utcnow() - timedelta(minutes=1)
                p.created_at = utcnow() - timedelta(hours=1)
            db.commit()
        service.sweep_open_payments(db)
    finally:
        db.close()
    assert _payment(broken["reference"]).status == "pending"  # retried on the next sweep
    assert _payment(fine["reference"]).status == "expired"


def test_a_request_delivers_only_its_own_payments_notifications(client, org, receiver):
    """A broken notify_url of one payment never delays another payer's redirect."""
    receiver.status = 500
    first = start(client, org.admin)
    browser_pays(client, first)  # its notification fails and waits for the scheduler
    receiver.status = 200
    receiver.requests.clear()
    db = SessionLocal()
    try:
        with platform_scope():
            for n in db.scalars(select(Notification).where(Notification.delivered_at.is_(None))):
                n.next_attempt_at = utcnow() - timedelta(seconds=1)  # due again
            db.commit()
    finally:
        db.close()
    second = start(client, org.admin)
    browser_pays(client, second)
    assert {json.loads(q.content)["reference"] for q in receiver.requests} == {second["reference"]}
