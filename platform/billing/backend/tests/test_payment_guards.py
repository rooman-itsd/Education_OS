"""Security review N8 (#675) and N7 (#674): a paid plan is activated only against a payment.

N8: with BILLING_PAYMENT_ADAPTER=none (what deploy-api-lxc.sh writes) any organisation admin activated any paid plan
at once, with a numbered "paid" GST invoice for money never received. Outside dev mode that upgrade is now refused
with 409 `payment_not_configured`; a super admin activates the plan once payment arrives offline (PUT
/admin/subscriptions/{id}, which issues no invoice). A free plan still activates.

N7: POST /webhooks/payment took no token and checked no signature, so anyone holding a pending upgrade's reference
activated it. It now answers 404 with no adapter, and otherwise accepts only a notification signed with
BILLING_PAYMENT_WEBHOOK_SECRET (payment-sbiepay's PaymentNotification: HMAC-SHA256 of the raw body, hex, in
X-Payment-Signature), for a succeeded payment of the plan's amount."""

import hashlib
import hmac
import json
import uuid
from dataclasses import replace
from decimal import Decimal

import pytest
from eos_billing.api import router as billing_api
from eos_billing.application import service
from eos_billing.domain.models import BillingProfile, Invoice, InvoiceCounter, Plan, Subscription
from eos_core.db import SessionLocal, init_db
from eos_core.security import create_token
from eos_core.tenant import organisation_scope, platform_scope
from eos_identity.application import service as identity
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

SECRET = "test-webhook-secret-not-a-real-one"
WEBHOOK = "/api/v1/billing/webhooks/payment"


@pytest.fixture(autouse=True)
def _db(monkeypatch):
    init_db()
    with platform_scope(), SessionLocal() as db:
        service.seed_plans(db)
        for table in (Invoice, Subscription, BillingProfile, InvoiceCounter):
            db.execute(delete(table))
        db.commit()
    for key in ("SUPPLIER_GSTIN", "SUPPLIER_NAME", "SUPPLIER_ADDRESS", "GST_RATE", "PAYMENT_WEBHOOK_SECRET"):
        monkeypatch.delenv(f"BILLING_{key}", raising=False)


def _settings(monkeypatch, **values) -> None:
    for module in (service, billing_api):
        monkeypatch.setattr(module, "settings", replace(service.settings, **values), raising=False)


@pytest.fixture
def production(monkeypatch):
    """What the deployment runs: dev mode off, no payment adapter."""
    _settings(monkeypatch, dev_mode=False, payment_adapter="none")


@pytest.fixture
def adapter(monkeypatch):
    """A payment adapter configured, with its notification secret."""
    _settings(monkeypatch, dev_mode=False, payment_adapter="payment-sbiepay")
    monkeypatch.setenv("BILLING_PAYMENT_WEBHOOK_SECRET", SECRET)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(billing_api.router, prefix="/api/v1/billing")
    with TestClient(app) as c:
        yield c


def _paid_plan() -> tuple[str, Decimal]:
    with platform_scope(), SessionLocal() as db:
        plans = [p for p in db.query(Plan).all() if p.published and Decimal(str(p.price_per_month or 0)) > 0]
    plan = sorted(plans, key=lambda p: (Decimal(str(p.price_per_month)), p.id))[0]
    return plan.id, Decimal(str(plan.price_per_month))


def _org() -> str:
    org = str(uuid.uuid4())
    with organisation_scope(org), SessionLocal() as db:
        db.add(Subscription(organisation_id=org, plan_id="trial", status="trialing"))
        db.commit()
    return org


def _headers(org: str | None, roles: list[str], *, super_admin: bool = False) -> dict:
    with platform_scope(), SessionLocal() as db:
        u = identity.create_user(
            db,
            organisation_id=org,
            email=f"{uuid.uuid4().hex[:8]}@example.com",
            name="U",
            password="Passw0rd!long",
            roles=roles,
            is_super_admin=super_admin,
        )
        db.commit()
        uid = u.id
    token = create_token(user_id=uid, organisation_id=org, roles=roles, super_admin=super_admin)
    return {"Authorization": f"Bearer {token}"}


def _subscription(org: str) -> Subscription:
    with SessionLocal() as db:
        return service.get_subscription(db, org)


def _invoices(org: str) -> list[dict]:
    with SessionLocal() as db:
        return service.list_invoices(db, org)


def _numbers_taken() -> int:
    with platform_scope(), SessionLocal() as db:
        return sum(c.last_sequence for c in db.scalars(select(InvoiceCounter)))


# ---- N8: no adapter -------------------------------------------------------------------------------------------


def test_without_an_adapter_an_org_admin_cannot_activate_a_paid_plan_and_no_invoice_is_numbered(client, production):
    org, (plan, _) = _org(), _paid_plan()
    r = client.post("/api/v1/billing/subscription/upgrade", json={"plan": plan}, headers=_headers(org, ["org-admin"]))
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "payment_not_configured"
    sub = _subscription(org)
    assert (sub.plan_id, sub.status, sub.pending_plan_id) == ("trial", "trialing", None)
    assert _invoices(org) == [] and _numbers_taken() == 0


def test_without_an_adapter_a_free_plan_still_activates(client, production):
    with platform_scope(), SessionLocal() as db:
        db.merge(Plan(id="free-n8", title="Free", price_per_month=0, suites=[], modules=[], published=True))
        db.commit()
    org = _org()
    r = client.post(
        "/api/v1/billing/subscription/upgrade", json={"plan": "free-n8"}, headers=_headers(org, ["org-admin"])
    )
    assert r.status_code == 201 and r.json()["activated"] is True, r.text
    assert _subscription(org).plan_id == "free-n8"


def test_a_super_admin_activates_a_paid_plan_by_hand_once_payment_arrives_offline(client, production):
    org, (plan, _) = _org(), _paid_plan()
    sa = _headers(None, ["super-admin"], super_admin=True)
    r = client.put(
        f"/api/v1/billing/admin/subscriptions/{org}", json={"plan": plan, "reason": "paid by NEFT"}, headers=sa
    )
    assert r.status_code == 200, r.text
    sub = _subscription(org)
    assert (sub.plan_id, sub.status) == (plan, "active")
    assert _invoices(org) == [] and _numbers_taken() == 0  # no tax invoice is numbered for money the API never saw
    # and an organisation admin cannot use that route
    other = _org()
    r = client.put(
        f"/api/v1/billing/admin/subscriptions/{other}", json={"plan": plan}, headers=_headers(other, ["org-admin"])
    )
    assert r.status_code == 403


# ---- N7: the payment webhook ----------------------------------------------------------------------------------


def _pending(client, org: str, plan: str) -> str:
    r = client.post("/api/v1/billing/subscription/upgrade", json={"plan": plan}, headers=_headers(org, ["org-admin"]))
    assert r.status_code == 201 and r.json()["activated"] is False, r.text
    return r.json()["reference"]


def _notification(org: str, reference: str, amount: str, **extra) -> dict:
    """payment-sbiepay's PaymentNotification for a billing payment (contracts/openapi.yaml there)."""
    return {
        "event_id": str(uuid.uuid4()),
        "event": "payment-sbiepay.payment.succeeded",
        "organisation_id": org,
        "reference": f"SBI{uuid.uuid4().hex[:10]}",
        "purpose": "subscription",
        "source_module": "billing",
        "source_reference": reference,
        "status": "succeeded",
        "amount": amount,
        "currency": "INR",
        **extra,
    }


def _post(client, body: dict, secret: str | None = SECRET, signature: str | None = None):
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()  # as payment-sbiepay encodes it
    headers = {"Content-Type": "application/json"}
    if secret is not None:
        headers["X-Payment-Signature"] = signature or hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return client.post(WEBHOOK, content=raw, headers=headers)


def test_with_no_adapter_the_webhook_does_not_exist(client, production):
    assert _post(client, {"reference": "anything"}).status_code == 404
    assert client.post(WEBHOOK, json={"reference": "anything"}).status_code == 404


def test_an_unsigned_or_badly_signed_notification_activates_nothing(client, adapter):
    org, (plan, price) = _org(), _paid_plan()
    reference = _pending(client, org, plan)
    body = _notification(org, reference, f"{price:.2f}")
    # the review's reproduction: the reference alone, no signature
    assert client.post(WEBHOOK, json={"reference": reference}).status_code == 401
    assert _post(client, body, secret=None).status_code == 401
    assert _post(client, body, secret="another-secret").status_code == 401
    assert _post(client, body, signature="0" * 64).status_code == 401
    sub = _subscription(org)
    assert (sub.plan_id, sub.pending_plan_id) == ("trial", plan) and _invoices(org) == []


def test_with_no_secret_configured_every_notification_is_refused(client, adapter, monkeypatch):
    monkeypatch.delenv("BILLING_PAYMENT_WEBHOOK_SECRET")
    org, (plan, price) = _org(), _paid_plan()
    reference = _pending(client, org, plan)
    assert _post(client, _notification(org, reference, f"{price:.2f}"), secret="").status_code == 503
    assert _subscription(org).plan_id == "trial"


def test_a_signed_notification_must_carry_the_plans_amount(client, adapter):
    org, (plan, price) = _org(), _paid_plan()
    reference = _pending(client, org, plan)
    r = _post(client, _notification(org, reference, "1.00"))
    assert r.status_code == 409 and r.json()["code"] == "amount_mismatch", r.text
    assert _post(client, _notification(org, reference, "not-money")).status_code == 422
    assert _post(client, _notification(str(uuid.uuid4()), reference, f"{price:.2f}")).status_code == 404
    assert _subscription(org).plan_id == "trial" and _invoices(org) == []


def test_failures_and_other_modules_payments_are_acknowledged_and_activate_nothing(client, adapter):
    org, (plan, price) = _org(), _paid_plan()
    reference = _pending(client, org, plan)
    failed = _notification(org, reference, f"{price:.2f}", status="failed", event="payment-sbiepay.payment.failed")
    fee = _notification(org, reference, f"{price:.2f}", source_module="fees-accounts")
    assert _post(client, failed).status_code == 204
    assert _post(client, fee).status_code == 204
    assert _subscription(org).plan_id == "trial" and _invoices(org) == []


def test_a_signed_succeeded_payment_activates_the_upgrade_once(client, adapter):
    org, (plan, price) = _org(), _paid_plan()
    reference = _pending(client, org, plan)
    body = _notification(org, reference, f"{price:.2f}")
    assert _post(client, body).status_code == 204
    sub = _subscription(org)
    assert (sub.plan_id, sub.status, sub.pending_plan_id) == (plan, "active", None)
    (invoice,) = _invoices(org)
    assert invoice["status"] == "paid" and invoice["total_amount"] == f"{price:.2f}"
    assert _post(client, body).status_code == 204  # the adapter's retry: done already, nothing twice
    assert len(_invoices(org)) == 1
