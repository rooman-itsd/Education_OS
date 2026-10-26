"""Every state change leaves an audit record (PRD rule; the audit SDK does not exist yet), and amounts never exceed
what the column holds."""

from datetime import date

from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_fees_accounts.application import consumers, jobs
from eos_fees_accounts.infrastructure.models import AuditEntry
from fees_support import BASE, TODAY, adhoc, head, invoice, pay_cash, published
from sqlalchemy import select


def actions(org_id: str) -> list[tuple[str, str | None]]:
    with SessionLocal() as db, platform_scope():
        q = (
            select(AuditEntry)
            .where(AuditEntry.organisation_id == org_id)
            .order_by(AuditEntry.occurred_at, AuditEntry.id)
        )
        return [(a.action, a.actor) for a in db.scalars(q)]


def test_every_state_change_is_audited(client, org):
    h = head(client, org, "AUD1")
    client.put(f"{BASE}/fee-heads/{h['id']}", json={"code": "AUD1", "name": "Renamed"}, headers=org.staff)
    s = published(client, org, [h], late_fee={"kind": "flat", "amount": "50"})
    client.post(f"{BASE}/fee-structures/{s['id']}/archive", headers=org.staff)
    s2 = published(client, org)
    client.post(
        f"{BASE}/invoices/bulk",
        json={"fee_structure_id": s2["id"], "instalment": 1, "person_ids": ["p-aud"]},
        headers=org.staff,
    )
    inv = adhoc(client, org, "1000.00")
    cash = pay_cash(client, org, inv["id"], "300.00")
    client.post(f"{BASE}/payments/{cash['id']}/refunds", json={"amount": "100", "reason": "x"}, headers=org.staff)
    cheque = client.post(
        f"{BASE}/invoices/{inv['id']}/payments",
        json={"amount": "50", "mode": "cheque", "paid_on": TODAY},
        headers=org.staff,
    ).json()
    client.post(f"{BASE}/payments/{cheque['id']}/void", json={"reason": "bounced"}, headers=org.staff)
    c1 = client.post(
        f"{BASE}/concessions",
        json={"invoice_id": inv["id"], "kind": "waiver", "amount": "10", "reason": "x"},
        headers=org.staff,
    ).json()
    client.post(f"{BASE}/concessions/{c1['id']}/decision", json={"decision": "approved"}, headers=org.manager)
    c2 = client.post(
        f"{BASE}/concessions",
        json={"invoice_id": inv["id"], "kind": "waiver", "amount": "10", "reason": "x"},
        headers=org.staff,
    ).json()
    client.post(f"{BASE}/concessions/{c2['id']}/decision", json={"decision": "rejected"}, headers=org.manager)
    cancel_me = adhoc(client, org, "5.00")
    client.post(f"{BASE}/invoices/{cancel_me['id']}/cancel", json={"reason": "x"}, headers=org.staff)
    client.put(f"{BASE}/settings", json={"invoice_library_fines": True}, headers=org.staff)
    client.put(
        f"{BASE}/collection-targets",
        json={"academic_year": "2026-27", "targets": [{"period": "2026-10", "amount": "1"}]},
        headers=org.manager,
    )
    online = adhoc(client, org, "20.00")
    with SessionLocal() as db:
        consumers.handle(
            db,
            consumers.PAYMENT_SUCCEEDED,
            {
                "organisation_id": org.id,
                "reference": "AUD-REF",
                "source_module": "fees-accounts",
                "source_reference": online["id"],
                "amount": "20.00",
                "currency": "INR",
            },
        )
    late = invoice(
        client,
        org,
        "p-late-aud",
        structure=published(
            client,
            org,
            instalments=[{"label": "All", "percent": 100, "due_date": "2026-10-01"}],
            late_fee={"kind": "flat", "amount": "25"},
        ),
    )
    with SessionLocal() as db:
        jobs.run_daily(db, date(2026, 10, 22))

    got = actions(org.id)
    names = {a for a, _ in got}
    for expected in (
        "fee_head.created",
        "fee_head.updated",
        "fee_structure.created",
        "fee_structure.published",
        "fee_structure.archived",
        "bulk_job.started",
        "bulk_job.completed",
        "invoice.issued",
        "payment.received",
        "refund.completed",
        "payment.voided",
        "concession.requested",
        "concession.approved",
        "concession.rejected",
        "invoice.cancelled",
        "settings.updated",
        "collection_target.set",
        "invoice.late_fee_updated",
        "invoice.overdue",
    ):
        assert expected in names, expected
    assert ("concession.approved", org.ids["manager"]) in got
    assert ("payment.received", None) in got  # online, from payment-sbiepay's event
    assert late["id"]


def test_amounts_never_exceed_the_column(client, org):
    h = head(client, org, "BIG1")
    r = client.post(
        f"{BASE}/invoices",
        json={"person_id": "p", "lines": [{"fee_head_id": h["id"], "amount": "10000000000"}], "due_date": "2026-11-01"},
        headers=org.staff,
    )
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_amount"
    ok = client.post(
        f"{BASE}/invoices",
        json={
            "person_id": "p",
            "lines": [{"fee_head_id": h["id"], "amount": "9999999999.99"}],
            "due_date": "2026-11-01",
        },
        headers=org.staff,
    )
    assert ok.status_code == 201
