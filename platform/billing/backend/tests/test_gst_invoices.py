"""GST tax invoices written when a paid plan is activated: parties, place of supply, intra/inter-state tax, the
number series across the financial-year boundary, the billing profile API, and legacy behaviour with no supplier."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from eos_billing.api.router import router as billing_router
from eos_billing.application import service
from eos_billing.application.service import BillingError
from eos_billing.domain.models import BillingProfile, Invoice, InvoiceCounter, Plan, Subscription
from eos_core.db import SessionLocal, init_db
from eos_core.security import create_token
from eos_core.tenant import organisation_scope, platform_scope
from eos_identity.application import service as identity
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

MAHARASHTRA = "27AAPFU0939F1ZV"
KARNATAKA = "29AABCT1332L1ZA"
TAMIL_NADU = "33AAACC1206D1ZN"


@pytest.fixture(autouse=True)
def _db(monkeypatch):
    init_db()
    with platform_scope(), SessionLocal() as db:
        service.seed_plans(db)
        for table in (Invoice, Subscription, BillingProfile, InvoiceCounter):
            db.execute(delete(table))
        db.commit()
    assert service.settings.payment_adapter == "none"  # activation is immediate, no payment adapter in the way
    for key in ("GSTIN", "NAME", "ADDRESS"):
        monkeypatch.delenv(f"BILLING_SUPPLIER_{key}", raising=False)
    for key in ("GST_RATE", "SAC_CODE", "INVOICE_PREFIX"):
        monkeypatch.delenv(f"BILLING_{key}", raising=False)


@pytest.fixture
def supplier(monkeypatch):
    """The platform registered in Maharashtra."""
    monkeypatch.setenv("BILLING_SUPPLIER_GSTIN", MAHARASHTRA)
    monkeypatch.setenv("BILLING_SUPPLIER_NAME", "Rooman Technologies Pvt Ltd")
    monkeypatch.setenv("BILLING_SUPPLIER_ADDRESS", "Mumbai")


@pytest.fixture
def clock(monkeypatch):
    """Pin the moment an invoice is issued (service.utcnow); returns a setter."""
    now = {"t": datetime(2027, 1, 15, 6, 0, tzinfo=UTC)}
    monkeypatch.setattr(service, "utcnow", lambda: now["t"])
    return lambda *args: now.update(t=datetime(*args, tzinfo=UTC))


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(billing_router, prefix="/api/v1/billing")
    with TestClient(app) as c:
        yield c


def _paid_plan() -> tuple[str, Decimal]:
    with platform_scope(), SessionLocal() as db:
        plans = [p for p in db.query(Plan).all() if Decimal(str(p.price_per_month or 0)) > 0]
    plan = sorted(plans, key=lambda p: (Decimal(str(p.price_per_month)), p.id))[0]
    return plan.id, Decimal(str(plan.price_per_month))


def _org(*, profile: dict | None = None) -> str:
    org = str(uuid.uuid4())
    with organisation_scope(org), SessionLocal() as db:
        db.add(Subscription(organisation_id=org, plan_id="trial", status="trialing"))
        db.commit()
    if profile:
        with SessionLocal() as db:
            service.save_profile(db, organisation_id=org, **profile)
    return org


def _profile(gstin=None, state=None, name="Acme Academy", address="Bengaluru") -> dict:
    return {"legal_name": name, "gstin": gstin, "address": address, "state_code": state}


def _upgrade(org: str, cycle: str = "monthly") -> dict:
    plan, _ = _paid_plan()
    with SessionLocal() as db:
        assert service.upgrade(db, organisation_id=org, plan_id=plan, billing_cycle=cycle)["activated"]
    return _invoices(org)[0]


def _invoices(org: str) -> list[dict]:
    with SessionLocal() as db:
        return service.list_invoices(db, org)


def test_intra_state_invoice_charges_cgst_and_sgst(supplier):
    _, price = _paid_plan()
    org = _org(profile=_profile(MAHARASHTRA))
    inv = _upgrade(org)
    half = (price * Decimal("0.09")).quantize(Decimal("0.01"))
    assert inv["tax_scheme"] == "intra"
    assert inv["place_of_supply"] == "27"
    assert inv["gst_rate"] == "18.00"
    assert inv["taxable_value"] == f"{price:.2f}"
    assert inv["cgst_amount"] == inv["sgst_amount"] == f"{half:.2f}"
    assert inv["igst_amount"] == "0.00"
    assert inv["total_amount"] == f"{price + 2 * half:.2f}"
    assert inv["amount"] == float(price)  # unchanged: the taxable value, so revenue excludes GST


def test_inter_state_invoice_charges_igst(supplier):
    _, price = _paid_plan()
    org = _org(profile=_profile(KARNATAKA))
    inv = _upgrade(org)
    igst = (price * Decimal("0.18")).quantize(Decimal("0.01"))
    assert inv["tax_scheme"] == "inter"
    assert inv["place_of_supply"] == "29"
    assert (inv["cgst_amount"], inv["sgst_amount"]) == ("0.00", "0.00")
    assert inv["igst_amount"] == f"{igst:.2f}"
    assert inv["total_amount"] == f"{price + igst:.2f}"


def test_rate_is_configurable_and_yearly_cycle_multiplies_the_taxable_value(supplier, monkeypatch):
    monkeypatch.setenv("BILLING_GST_RATE", "12")
    _, price = _paid_plan()
    inv = _upgrade(_org(profile=_profile(TAMIL_NADU)), cycle="yearly")
    assert inv["gst_rate"] == "12.00"
    assert inv["taxable_value"] == f"{price * 12:.2f}"
    assert inv["igst_amount"] == f"{(price * 12 * Decimal('0.12')).quantize(Decimal('0.01')):.2f}"


def test_parties_sac_and_snapshot_are_on_the_invoice(supplier):
    org = _org(profile=_profile(KARNATAKA, address="1 MG Road, Bengaluru"))
    inv = _upgrade(org)
    assert inv["supplier"] == {
        "name": "Rooman Technologies Pvt Ltd",
        "gstin": MAHARASHTRA,
        "address": "Mumbai",
        "state_code": "27",
    }
    assert inv["recipient"] == {
        "name": "Acme Academy",
        "gstin": KARNATAKA,
        "address": "1 MG Road, Bengaluru",
        "state_code": "29",
    }
    assert inv["sac_code"] == "998315"
    # fields the invoice output had before are all still there
    for key in ("id", "organisation_id", "plan", "currency", "status", "issued_at", "period_start", "period_end"):
        assert inv[key]
    assert inv["payment_reference"] and "document_id" in inv
    # a later change to the profile does not rewrite the invoice already issued
    with SessionLocal() as db:
        service.save_profile(db, organisation_id=org, **_profile(TAMIL_NADU, name="Renamed"))
    assert _invoices(org)[0]["recipient"]["name"] == "Acme Academy"


def test_business_to_consumer_has_no_recipient_gstin_and_uses_the_given_state(supplier):
    inv = _upgrade(_org(profile=_profile(None, "29")))
    assert inv["recipient"]["gstin"] is None
    assert inv["place_of_supply"] == "29" and inv["tax_scheme"] == "inter"


def test_without_a_state_the_place_of_supply_is_the_suppliers(supplier):
    for profile in (None, _profile(None, None)):
        inv = _upgrade(_org(profile=profile))
        assert inv["place_of_supply"] == "27" and inv["tax_scheme"] == "intra"
        assert inv["recipient"]["gstin"] is None


def test_no_supplier_gstin_issues_an_untaxed_but_numbered_invoice():
    _, price = _paid_plan()
    inv = _upgrade(_org())
    assert inv["tax_scheme"] == "none"
    assert inv["total_amount"] == inv["taxable_value"] == f"{price:.2f}"
    assert inv["supplier"]["gstin"] is None
    assert inv["invoice_number"]


def test_a_bad_supplier_registration_blocks_the_upgrade_and_leaves_nothing_behind(monkeypatch):
    monkeypatch.setenv("BILLING_SUPPLIER_GSTIN", "27AAPFU0939F1ZW")  # wrong check character
    monkeypatch.setenv("BILLING_SUPPLIER_NAME", "Rooman")
    org = _org()
    plan, _ = _paid_plan()
    with SessionLocal() as db, pytest.raises(BillingError) as e:
        service.upgrade(db, organisation_id=org, plan_id=plan)
    assert e.value.status == 503
    assert _invoices(org) == []
    with platform_scope(), SessionLocal() as db:
        assert db.scalars(select(InvoiceCounter)).all() == []


def test_numbers_run_without_gaps_and_fit_sixteen_characters(supplier, clock):
    numbers = []
    for _ in range(3):
        numbers.append(_upgrade(_org(profile=_profile(KARNATAKA)))["invoice_number"])
    assert numbers == ["EOS/26-27/000001", "EOS/26-27/000002", "EOS/26-27/000003"]
    assert all(len(n) <= 16 for n in numbers)


def test_series_restarts_across_31_march_to_1_april(supplier, clock):
    clock(2027, 3, 31, 18, 29)  # 23:59 IST on 31 March
    last_of_26_27 = _upgrade(_org(profile=_profile(KARNATAKA)))
    clock(2027, 3, 31, 18, 30)  # 00:00 IST on 1 April
    first_of_27_28 = _upgrade(_org(profile=_profile(KARNATAKA)))
    clock(2027, 4, 1, 9, 0)
    second_of_27_28 = _upgrade(_org(profile=_profile(KARNATAKA)))
    assert (last_of_26_27["invoice_number"], last_of_26_27["financial_year"]) == ("EOS/26-27/000001", "26-27")
    assert (first_of_27_28["invoice_number"], first_of_27_28["financial_year"]) == ("EOS/27-28/000001", "27-28")
    assert second_of_27_28["invoice_number"] == "EOS/27-28/000002"
    # an old year keeps counting from where it stopped
    clock(2027, 3, 20, 6)
    assert _upgrade(_org(profile=_profile(KARNATAKA)))["invoice_number"] == "EOS/26-27/000002"


def test_a_failed_activation_does_not_burn_a_number(supplier, clock):
    first = _upgrade(_org())
    org = _org()
    plan, _ = _paid_plan()
    with SessionLocal() as db:
        sub = service.get_subscription(db, org)
        with organisation_scope(org):
            service._activate(db, sub, plan, "monthly", "ref")
            db.rollback()  # the surrounding transaction fails after the number was taken
    second = _upgrade(_org())
    assert first["invoice_number"] == "EOS/26-27/000001"
    assert second["invoice_number"] == "EOS/26-27/000002"


def test_prefix_is_configurable_but_must_fit(supplier, monkeypatch, clock):
    monkeypatch.setenv("BILLING_INVOICE_PREFIX", "ro")
    assert _upgrade(_org())["invoice_number"] == "RO/26-27/000001"
    monkeypatch.setenv("BILLING_INVOICE_PREFIX", "ROOM")  # 17 characters in all
    org = _org()
    plan, _ = _paid_plan()
    with SessionLocal() as db, pytest.raises(BillingError) as e:
        service.upgrade(db, organisation_id=org, plan_id=plan)
    assert e.value.status == 503


def test_an_invoice_issued_before_gst_invoicing_has_null_gst_fields():
    org = _org()
    with organisation_scope(org), SessionLocal() as db:
        db.add(
            Invoice(
                organisation_id=org,
                subscription_id="s",
                plan_id="standard",
                amount=Decimal("100"),
                status="paid",
                issued_at=datetime(2026, 11, 1, tzinfo=UTC),
                period_start=datetime(2026, 11, 1, tzinfo=UTC),
                period_end=datetime(2026, 12, 1, tzinfo=UTC),
            )
        )
        db.commit()
    inv = _invoices(org)[0]
    assert inv["invoice_number"] is None and inv["tax_scheme"] is None and inv["total_amount"] is None


# --- the billing profile ------------------------------------------------------------------------------------------


def _admin(org: str, roles=("org-admin",)) -> dict:
    with platform_scope(), SessionLocal() as db:
        u = identity.create_user(
            db,
            organisation_id=org,
            email=f"{uuid.uuid4().hex[:8]}@example.com",
            name="Admin",
            password="Passw0rd!long",
            roles=list(roles),
        )
        db.commit()
        uid = u.id
    return {"Authorization": f"Bearer {create_token(user_id=uid, organisation_id=org, roles=list(roles))}"}


URL = "/api/v1/billing/billing-profile"


def test_profile_round_trip_normalises_gstin_and_takes_the_state_from_it(client):
    org = _org()
    h = _admin(org)
    assert client.get(URL, headers=h).status_code == 404
    r = client.put(URL, headers=h, json={"legal_name": " Acme ", "gstin": f" {KARNATAKA.lower()} ", "address": "x"})
    assert r.status_code == 200, r.text
    assert r.json()["gstin"] == KARNATAKA and r.json()["state_code"] == "29" and r.json()["legal_name"] == "Acme"
    assert client.get(URL, headers=h).json()["gstin"] == KARNATAKA
    # saving again updates the one row
    client.put(URL, headers=h, json={"legal_name": "Acme", "gstin": None, "state_code": "33"})
    assert client.get(URL, headers=h).json() | {"organisation_id": org} == {
        "organisation_id": org,
        "legal_name": "Acme",
        "gstin": None,
        "address": "",
        "state_code": "33",
    }
    with platform_scope(), SessionLocal() as db:
        assert len(db.scalars(select(BillingProfile).where(BillingProfile.organisation_id == org)).all()) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"legal_name": "A", "gstin": "27AAPFU0939F1ZW"},  # checksum
        {"legal_name": "A", "gstin": "27AAPFU0939F1"},  # format
        {"legal_name": "A", "gstin": KARNATAKA, "state_code": "27"},  # state disagrees with the GSTIN
        {"legal_name": "A", "state_code": "99"},  # unknown state
        {"legal_name": "  "},  # no name
    ],
)
def test_bad_profile_is_refused_and_nothing_is_saved(client, body):
    org = _org()
    h = _admin(org)
    assert client.put(URL, headers=h, json=body).status_code == 422
    assert client.get(URL, headers=h).status_code == 404


def test_profile_is_per_organisation_and_needs_the_manage_permission(client):
    a, b = _org(), _org()
    ha, hb = _admin(a), _admin(b)
    client.put(URL, headers=ha, json={"legal_name": "A Ltd", "gstin": KARNATAKA})
    assert client.get(URL, headers=hb).status_code == 404  # another organisation never sees it
    assert client.put(URL, headers={}, json={"legal_name": "x"}).status_code in (401, 403)
    no_role = _admin(a, roles=())
    assert client.put(URL, headers=no_role, json={"legal_name": "x"}).status_code == 403


def test_invoices_of_one_organisation_are_not_listed_to_another(supplier):
    a, b = _org(profile=_profile(KARNATAKA)), _org()
    _upgrade(a)
    assert _invoices(b) == []
    assert len(_invoices(a)) == 1
