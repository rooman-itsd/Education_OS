"""Refunds, settlement reconciliation, the Finance Staff summary and the merchant account."""

from decimal import Decimal

from eos_core.db import utcnow
from eos_payment_sbiepay.infrastructure.gateway import MockGateway, SettlementRow
from sbiepay_support import PREFIX, browser_pays, outbox, start

FEE = {"purpose": "fee", "source_module": "fees-accounts"}


def _paid(client, org, **overrides) -> str:
    s = start(client, org.admin, **overrides)
    assert "status=succeeded" in browser_pays(client, s).headers["location"]
    return s["reference"]


def _fee_paid(client, org) -> str:
    """Refunds are for fee payments: the organisation's own merchant account received the money."""
    client.put(f"{PREFIX}/merchant-account", json={"merchant_id": "FEE-R", "mode": "sandbox"}, headers=org.admin)
    return _paid(client, org, **FEE)


def test_partial_then_full_refund(client, org, receiver):
    ref = _fee_paid(client, org)
    r = client.post(
        f"{PREFIX}/payments/{ref}/refunds", json={"amount": "500.00", "reason": "overcharged"}, headers=org.staff
    )
    assert r.status_code == 202 and r.json()["status"] == "succeeded" and r.json()["gateway_refund_id"]
    p = client.get(f"{PREFIX}/payments/{ref}", headers=org.staff).json()
    assert p["status"] == "partially_refunded" and p["refunded_amount"] == "500.00"

    too_much = client.post(
        f"{PREFIX}/payments/{ref}/refunds", json={"amount": "1000.01", "reason": "x"}, headers=org.staff
    )
    assert too_much.status_code == 422

    rest = client.post(
        f"{PREFIX}/payments/{ref}/refunds", json={"amount": "1000", "reason": "cancelled"}, headers=org.staff
    )
    assert rest.status_code == 202
    assert client.get(f"{PREFIX}/payments/{ref}", headers=org.staff).json()["status"] == "refunded"

    events = outbox("payment-sbiepay.payment.refunded", org.id)
    assert [e.payload["refunded_total"] for e in events] == ["500.00", "1500.00"]
    assert events[0].payload["amount"] == "500.00" and events[0].payload["refund_id"]
    assert len(receiver.requests) == 3  # succeeded + two refunds


def test_refund_only_after_success(client, org):
    client.put(f"{PREFIX}/merchant-account", json={"merchant_id": "FEE-R", "mode": "sandbox"}, headers=org.admin)
    s = start(client, org.admin, **FEE)
    r = client.post(
        f"{PREFIX}/payments/{s['reference']}/refunds", json={"amount": "1", "reason": "x"}, headers=org.staff
    )
    assert r.status_code == 409


def test_refused_refund_changes_nothing(client, org):
    ref = _fee_paid(client, org)
    MockGateway.fail_refunds = True
    r = client.post(f"{PREFIX}/payments/{ref}/refunds", json={"amount": "100", "reason": "x"}, headers=org.staff)
    assert r.status_code == 202 and r.json()["status"] == "failed"
    p = client.get(f"{PREFIX}/payments/{ref}", headers=org.staff).json()
    assert p["status"] == "succeeded" and p["refunded_amount"] == "0.00"


def test_refund_permission(client, org):
    ref = _fee_paid(client, org)
    r = client.post(f"{PREFIX}/payments/{ref}/refunds", json={"amount": "1", "reason": "x"}, headers=org.admin)
    assert r.status_code == 403


def test_reconciliation_finds_every_kind_of_mismatch(client, org):
    client.put(f"{PREFIX}/merchant-account", json={"merchant_id": "FEE-M", "mode": "sandbox"}, headers=org.admin)
    fee = FEE
    matched = _paid(client, org, **fee)
    wrong_amount = _paid(client, org, **fee)
    missing = _paid(client, org, **fee)
    unpaid = start(client, org.admin, **fee)["reference"]
    today = utcnow().date()
    MockGateway.settlements[("FEE-M", today)] = [
        SettlementRow(matched, "G1", Decimal("1500.00")),
        SettlementRow(wrong_amount, "G2", Decimal("1400.00")),
        SettlementRow(unpaid, "G3", Decimal("1500.00")),
        SettlementRow("NOT-OURS", "G4", Decimal("99.00")),
    ]
    r = client.post(f"{PREFIX}/reconciliation/runs", json={"settlement_date": today.isoformat()}, headers=org.staff)
    assert r.status_code == 202
    run = r.json()
    assert run["status"] == "completed" and run["matched"] == 1
    kinds = {m["reference"]: m["kind"] for m in run["mismatches"]}
    assert kinds == {
        wrong_amount: "amount_differs",
        unpaid: "status_differs",
        "NOT-OURS": "missing_in_records",
        missing: "missing_in_gateway",
    }
    assert len(outbox("payment-sbiepay.reconciliation.mismatch-found", org.id)) == 4

    assert client.get(f"{PREFIX}/reconciliation/runs/{run['id']}", headers=org.staff).json()["id"] == run["id"]
    assert run["id"] in {x["id"] for x in client.get(f"{PREFIX}/reconciliation/runs", headers=org.staff).json()}

    summary = client.get(f"{PREFIX}/reconciliation/summary", headers=org.staff).json()
    assert summary["date"] == today.isoformat()
    assert summary["succeeded"] == {"count": 3, "amount": "4500.00"}
    assert summary["pending"]["count"] == 1
    assert summary["settled"] == {"count": 1, "amount": "1500.00"}
    assert summary["mismatches"] == 4 and summary["last_run_at"]


def test_reconciliation_without_merchant_account_fails_cleanly(client, org):
    r = client.post(f"{PREFIX}/reconciliation/runs", json={"settlement_date": "2026-10-01"}, headers=org.staff)
    assert r.status_code == 202 and r.json()["status"] == "failed"


def test_uploaded_settlement_reports_are_not_supported_yet(client, org):
    r = client.post(
        f"{PREFIX}/reconciliation/runs",
        json={"settlement_date": "2026-10-01", "report_document_id": "doc-1"},
        headers=org.staff,
    )
    assert r.status_code == 501


def test_unknown_run_is_404(client, org):
    assert client.get(f"{PREFIX}/reconciliation/runs/nope", headers=org.staff).status_code == 404


def test_merchant_account(client, org):
    assert client.get(f"{PREFIX}/merchant-account", headers=org.admin).status_code == 404
    r = client.put(f"{PREFIX}/merchant-account", json={"merchant_id": "M9", "mode": "live"}, headers=org.admin)
    assert r.status_code == 200
    assert r.json() | {"updated_at": None} == {
        "merchant_id": "M9",
        "mode": "live",
        "active": True,
        "key_set": False,
        "updated_at": None,
    }
    assert client.get(f"{PREFIX}/merchant-account", headers=org.admin).json()["merchant_id"] == "M9"
    assert client.get(f"{PREFIX}/merchant-account", headers=org.staff).status_code == 403


def test_encryption_key_is_not_stored_until_it_can_be_encrypted(client, org):
    r = client.put(
        f"{PREFIX}/merchant-account",
        json={"merchant_id": "M9", "mode": "live", "encryption_key": "secret"},
        headers=org.admin,
    )
    assert r.status_code == 501
    assert "secret" not in r.text


def test_subscription_payments_are_not_refunded_by_the_organisation(client, org):
    """A plan upgrade was paid into the platform's account; an organisation's finance staff cannot refund it."""
    ref = _paid(client, org)  # purpose=subscription, source billing
    r = client.post(f"{PREFIX}/payments/{ref}/refunds", json={"amount": "1", "reason": "x"}, headers=org.staff)
    assert r.status_code == 403
    assert client.get(f"{PREFIX}/payments/{ref}", headers=org.staff).json()["refunded_amount"] == "0.00"


def test_refunds_the_gateway_has_not_settled_count_against_the_balance(client, org):
    ref = _fee_paid(client, org)
    MockGateway.defer_refunds = True
    first = client.post(f"{PREFIX}/payments/{ref}/refunds", json={"amount": "1000", "reason": "x"}, headers=org.staff)
    assert first.status_code == 202 and first.json()["status"] == "requested"
    second = client.post(f"{PREFIX}/payments/{ref}/refunds", json={"amount": "600", "reason": "x"}, headers=org.staff)
    assert second.status_code == 422  # only 500.00 is left while 1000.00 is in flight
    third = client.post(f"{PREFIX}/payments/{ref}/refunds", json={"amount": "500", "reason": "x"}, headers=org.staff)
    assert third.status_code == 202
    assert outbox("payment-sbiepay.payment.refunded", org.id) == []  # nothing has succeeded yet


def test_refund_reads_the_payment_for_update():
    """Two refunds of one payment run one after the other on Postgres: the row is locked until commit."""
    from eos_core.db import SessionLocal
    from eos_core.tenant import organisation_scope
    from eos_payment_sbiepay.application import service
    from sqlalchemy import event

    statements = []
    db = SessionLocal()

    @event.listens_for(db.get_bind(), "before_cursor_execute")
    def capture(conn, cursor, statement, *args):
        statements.append(statement)

    try:
        with organisation_scope("no-such-org"):
            try:
                service.refund(db, reference="EOSNONE", user_id="u", amount="1", reason="x")
            except service.PaymentError as e:
                assert e.status == 404
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", capture)
        db.close()
    payment_reads = [s for s in statements if "FROM payment_sbiepay_payment" in s]
    assert payment_reads
    dialect = SessionLocal().get_bind().dialect.name
    if dialect == "postgresql":
        assert "FOR UPDATE" in payment_reads[0]


def test_scheduler_can_run_reconciliation_outside_a_request(client, org):
    """run_reconciliation sets its own organisation scope instead of relying on the request's session."""
    from eos_core.db import SessionLocal
    from eos_payment_sbiepay.application import service

    client.put(f"{PREFIX}/merchant-account", json={"merchant_id": "FEE-S", "mode": "sandbox"}, headers=org.admin)
    ref = _paid(client, org, **FEE)
    MockGateway.settlements[("FEE-S", utcnow().date())] = [SettlementRow(ref, "G9", Decimal("1500.00"))]
    db = SessionLocal()
    try:
        run = service.run_reconciliation(
            db, organisation_id=org.id, user_id="scheduler", settlement_date=utcnow().date(), report_document_id=None
        )
    finally:
        db.close()
    assert run["status"] == "completed" and run["matched"] == 1 and run["mismatches"] == []
