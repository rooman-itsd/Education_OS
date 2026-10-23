"""The daily sweep, the cross-tenant leak test, the Alembic chain and drift between code and contract."""

import tempfile
from datetime import date
from pathlib import Path

import pytest
import yaml
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from eos_core.db import SessionLocal
from eos_fees_accounts.api.router import router
from eos_fees_accounts.application import jobs
from eos_fees_accounts.application.access import PERMISSION_KEYS
from eos_fees_accounts.domain import rules
from eos_fees_accounts.infrastructure.models import PREFIX, TABLES
from eos_testing import assert_no_cross_tenant_leak
from fees_support import BASE, adhoc, head, invoice, outbox, pay_cash, published
from sqlalchemy import create_engine, inspect

MODULE = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- daily sweep


def test_overdue_is_published_once_and_late_fees_grow_to_the_cap(client, org):
    h = head(client, org, "LATE1")
    s = published(
        client,
        org,
        [h],
        instalments=[{"label": "All", "percent": 100, "due_date": "2026-10-01"}],
        late_fee={"kind": "per_day", "amount": "10", "grace_days": 2, "cap": "100"},
    )
    inv = invoice(client, org, "p-late", structure=s)
    paid = invoice(client, org, "p-paid", structure=s)
    pay_cash(client, org, paid["id"], paid["balance"])
    with SessionLocal() as db:
        jobs.run_daily(db, date(2026, 10, 5))
        jobs.run_daily(db, date(2026, 10, 6))
    after = client.get(f"{BASE}/invoices/{inv['id']}", headers=org.staff).json()
    assert after["late_fee"] == "30.00" and after["balance"] == "30030.00"
    assert [e["invoice_id"] for e in outbox("fees-accounts.invoice.overdue", org.id)] == [inv["id"]]
    with SessionLocal() as db:
        jobs.run_daily(db, date(2026, 12, 1))
    assert client.get(f"{BASE}/invoices/{inv['id']}", headers=org.staff).json()["late_fee"] == "100.00"
    entries = client.get(f"{BASE}/accounts/p-late/statement", headers=org.staff).json()["entries"]
    assert [e["kind"] for e in entries] == ["invoice", "late_fee"]


# ---------------------------------------------------------------- tenancy


def seed(client, org):
    h = head(client, org, "LEAK")
    inv = adhoc(client, org, "100.00", person="student")
    p = pay_cash(client, org, inv["id"], "40.00")
    c = client.post(
        f"{BASE}/concessions",
        json={"invoice_id": inv["id"], "kind": "other", "amount": "5", "reason": "x"},
        headers=org.staff,
    ).json()
    published(client, org, [h])
    return inv, p, c


def test_no_cross_tenant_leak(client, org, other_org):
    inv_a, pay_a, con_a = seed(client, org)
    seed(client, other_org)
    for path, who in (
        ("/fee-heads", "staff"),
        ("/fee-structures", "staff"),
        ("/invoices", "staff"),
        ("/payments", "staff"),
        ("/concessions", "staff"),
        ("/me/invoices", "student"),
        ("/me/receipts", "student"),
    ):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", org.token(who), other_org.token(who))
    b = other_org.staff
    for path in (f"/invoices/{inv_a['id']}", f"/payments/{pay_a['id']}", f"/receipts/{pay_a['receipt_id']}"):
        assert client.get(f"{BASE}{path}", headers=b).status_code == 404
    assert (
        client.post(
            f"{BASE}/invoices/{inv_a['id']}/payments",
            json={"amount": "1", "mode": "cash", "paid_on": "2026-10-22"},
            headers=b,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{BASE}/concessions/{con_a['id']}/decision", json={"decision": "approved"}, headers=other_org.manager
        ).status_code
        == 404
    )
    # same person id in another organisation sees nothing of this one
    assert client.get(f"{BASE}/dues?person_id={org.ids['student']}", headers=b).json()["balance"] == "0.00"
    assert client.get(f"{BASE}/accounts/{org.ids['student']}/statement", headers=b).json()["entries"] == []


def test_numbers_are_sequential_per_organisation(client, org, other_org):
    a = adhoc(client, org, "1.00")
    b = adhoc(client, other_org, "1.00")
    assert b["number"] == "INV-000001" and a["number"].startswith("INV-")


# ---------------------------------------------------------------- migrations


def _config(url: str) -> Config:
    cfg = Config(str(MODULE / "db" / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url}"]})()
    return cfg


def test_migrations_match_the_models_and_downgrade():
    url = f"sqlite:///{tempfile.mkdtemp()}/migrations.db"  # a fresh throwaway file, never a real database
    cfg = _config(url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        insp = inspect(conn)
        tables = set(insp.get_table_names())
        assert {t.name for t in TABLES} <= tables and f"{PREFIX}alembic_version" in tables
        for t in TABLES:
            assert "organisation_id" in {c["name"] for c in insp.get_columns(t.name)}
        ctx = MigrationContext.configure(
            conn,
            opts={
                "include_object": lambda obj, name, type_, *_: (
                    type_ != "table" or (name.startswith(PREFIX) and "alembic" not in name)
                ),
                "compare_type": True,
            },
        )
        assert [d for d in compare_metadata(ctx, TABLES[0].metadata) if PREFIX in repr(d)] == []
    command.downgrade(cfg, "base")
    with engine.connect() as conn:
        assert not [t for t in inspect(conn).get_table_names() if t.startswith(PREFIX) and "alembic" not in t]


# ---------------------------------------------------------------- drift between code and contract


@pytest.fixture(scope="module")
def openapi():
    return yaml.safe_load((MODULE / "contracts" / "openapi.yaml").read_text(encoding="utf-8"))


def test_permission_keys_match_the_catalogue():
    catalogue = yaml.safe_load((MODULE / "contracts" / "permissions.yaml").read_text(encoding="utf-8"))
    assert set(PERMISSION_KEYS) == {p["key"] for p in catalogue["permissions"]}


def test_every_contract_operation_is_served_and_nothing_else(openapi):
    contract = {
        (method.upper(), path)
        for path, ops in openapi["paths"].items()
        for method in ops
        if method in ("get", "post", "put", "delete", "patch")
    }
    served = set()
    for route in router.routes:
        path = route.path
        for name in ("head_id", "structure_id", "invoice_id", "job_id", "payment_id", "receipt_id", "concession_id"):
            path = path.replace("{" + name + "}", "{id}")
        served |= {(m, path) for m in route.methods}
    assert served == contract


def test_enums_match_the_contract(openapi):
    schemas = openapi["components"]["schemas"]
    assert list(rules.INVOICE_STATUSES) == schemas["InvoiceStatus"]["enum"]
    assert list(rules.PAYMENT_MODES) == schemas["PaymentMode"]["enum"]
    assert list(rules.FEE_HEAD_CATEGORIES) == schemas["FeeHeadInput"]["properties"]["category"]["enum"]
    assert (
        list(rules.AGEING_BUCKETS)
        == schemas["OutstandingReport"]["properties"]["ageing"]["items"]["properties"]["bucket"]["enum"]
    )
    assert list(rules.CONCESSION_KINDS) == schemas["ConcessionInput"]["properties"]["kind"]["enum"]
