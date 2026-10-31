"""The super admin's subscription and revenue report, GET /admin/reports/subscriptions (platform:revenue:read).

Counts per plan and status across every organisation; monthly recurring revenue from active subscriptions only;
paid invoices of the last 30 days only; trials ending within 14 days, soonest first, named through the
organisation directory; money as exact decimal strings. Only the super admin may read it."""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from eos_billing.api.router import router as billing_router
from eos_billing.application import organisations, reports, service
from eos_billing.domain.models import Invoice, Plan, Subscription
from eos_core.db import SessionLocal, init_db, utcnow
from eos_core.security import create_token
from eos_core.tenant import organisation_scope, platform_scope
from eos_identity.application import service as identity
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete

URL = "/api/v1/billing/admin/reports/subscriptions"


@pytest.fixture(autouse=True)
def _db(monkeypatch):
    init_db()
    with platform_scope(), SessionLocal() as db:
        service.seed_plans(db)
        for table in (Invoice, Subscription):
            db.execute(delete(table))
        db.commit()
    # Tenancy is not installed with billing's own tests: the directory answers from this map instead.
    names: dict[str, str] = {}
    monkeypatch.setattr(organisations, "name", lambda db, org: names.get(org))
    return names


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(billing_router, prefix="/api/v1/billing")
    with TestClient(app) as c:
        yield c


def _user(*, super_admin: bool = False, roles: list[str] | None = None, org: str | None = None) -> dict:
    with platform_scope(), SessionLocal() as db:
        u = identity.create_user(
            db,
            organisation_id=org,
            email=f"{uuid.uuid4().hex[:8]}@example.com",
            name="Someone",
            password="Passw0rd!long",
            roles=roles or [],
            is_super_admin=super_admin,
        )
        db.commit()
        uid = u.id
    token = create_token(user_id=uid, organisation_id=org, roles=roles or [], super_admin=super_admin)
    return {"Authorization": f"Bearer {token}"}


def _plan_price(plan_id: str) -> Decimal:
    with platform_scope(), SessionLocal() as db:
        return Decimal(str(db.get(Plan, plan_id).price_per_month))


def _paid_plan() -> str:
    """The cheapest seeded plan with a price, so the test follows config/plans.yaml rather than hard-coding it."""
    with platform_scope(), SessionLocal() as db:
        plans = [p for p in db.query(Plan).all() if Decimal(str(p.price_per_month or 0)) > 0]
    return sorted(plans, key=lambda p: (Decimal(str(p.price_per_month)), p.id))[0].id


def _noon(days: int) -> timedelta:
    """From now to noon UTC `days` calendar days from today: the trial's end date never depends on the clock."""
    now = utcnow()
    return now.replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=days) - now


def _sub(plan: str, status: str, trial_ends_in: timedelta | None = None) -> str:
    org = str(uuid.uuid4())
    with organisation_scope(org), SessionLocal() as db:
        db.add(
            Subscription(
                organisation_id=org,
                plan_id=plan,
                status=status,
                trial_ends_at=utcnow() + trial_ends_in if trial_ends_in is not None else None,
            )
        )
        db.commit()
    return org


def _invoice(org: str, plan: str, amount: str, *, status: str = "paid", days_ago: int = 1) -> None:
    issued = utcnow() - timedelta(days=days_ago)
    with organisation_scope(org), SessionLocal() as db:
        db.add(
            Invoice(
                organisation_id=org,
                subscription_id=str(uuid.uuid4()),
                plan_id=plan,
                amount=Decimal(amount),
                status=status,
                issued_at=issued,
                period_start=issued,
                period_end=issued + timedelta(days=30),
            )
        )
        db.commit()


def _row(report: dict, plan: str) -> dict:
    return next(r for r in report["plans"] if r["plan"] == plan)


def test_counts_per_plan_and_status_and_recurring_revenue_from_active_only(client):
    paid = _paid_plan()
    for status in ("active", "active", "past_due", "read_only", "cancelled"):
        _sub(paid, status)
    _sub("trial", "trialing", _noon(30))

    r = client.get(URL, headers=_user(super_admin=True))

    assert r.status_code == 200, r.text
    row = _row(r.json(), paid)
    assert row["subscriptions"] == {"trialing": 0, "active": 2, "past_due": 1, "read_only": 1, "cancelled": 1}
    assert row["total"] == 5
    assert row["monthly_recurring"] == str((_plan_price(paid) * 2).quantize(Decimal("0.01")))
    trial = _row(r.json(), "trial")
    assert trial["subscriptions"]["trialing"] == 1 and trial["monthly_recurring"] == "0.00"


def test_paid_last_30_days_counts_only_paid_invoices_inside_the_window(client):
    paid = _paid_plan()
    org = _sub(paid, "active")
    _invoice(org, paid, "1000.10", days_ago=1)
    _invoice(org, paid, "2000.20", days_ago=29)
    _invoice(org, paid, "500.00", days_ago=31)  # outside the window
    _invoice(org, paid, "700.00", status="void", days_ago=2)  # not paid
    _invoice(org, paid, "800.00", status="due", days_ago=2)  # not paid

    row = _row(client.get(URL, headers=_user(super_admin=True)).json(), paid)

    assert row["paid_last_30_days"] == "3000.30"  # exact: Decimal, not float


def test_trials_ending_within_14_days_soonest_first_with_names(client, _db):
    later = _sub("trial", "trialing", _noon(10))
    today = _sub("trial", "trialing", _noon(0))
    edge = _sub("trial", "trialing", _noon(14))
    _sub("trial", "trialing", _noon(15))  # outside the window
    _sub("trial", "trialing", _noon(-1))  # already ended
    _sub(_paid_plan(), "active", _noon(2))  # not trialing any more
    _db[today] = "Morning Music Academy"

    expiring = client.get(URL, headers=_user(super_admin=True)).json()["trials_expiring"]

    assert [t["organisation_id"] for t in expiring] == [today, later, edge]
    assert [t["days_left"] for t in expiring] == [0, 10, 14]
    assert expiring[0]["organisation_name"] == "Morning Music Academy"
    assert expiring[1]["organisation_name"] is None  # not in the directory: shown without a name
    assert expiring[0]["plan"] == "trial"


def test_an_empty_platform_reports_every_plan_with_zeros(client):
    report = client.get(URL, headers=_user(super_admin=True)).json()
    assert report["trials_expiring"] == []
    assert report["plans"] and all(r["total"] == 0 and r["paid_last_30_days"] == "0.00" for r in report["plans"])
    assert report["trial_window_days"] == 14 and report["paid_window_days"] == 30


def test_only_the_super_admin_may_read_it(client):
    org = str(uuid.uuid4())
    assert client.get(URL, headers=_user(roles=["org-admin"], org=org)).status_code == 403
    assert client.get(URL).status_code == 401


def test_the_directory_lookup_is_found_on_the_entry_point(monkeypatch):
    """Without tenancy installed nothing is registered, and the name is None rather than an error."""
    monkeypatch.undo()  # the real lookup, not the fixture's map
    organisations.reset_cache()
    monkeypatch.setattr(organisations.metadata, "entry_points", lambda group: [])
    with SessionLocal() as db:
        assert organisations.name(db, str(uuid.uuid4())) is None
    organisations.reset_cache()
    assert reports.TRIAL_WINDOW_DAYS == 14
