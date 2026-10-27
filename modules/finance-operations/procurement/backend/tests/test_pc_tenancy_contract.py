"""The cross-tenant leak test, reads and writes across organisations, the Alembic chain, drift between code and contract,
event payloads against events.yaml, and the audit trail."""

import tempfile
from pathlib import Path

import pytest
import yaml
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_core.tenant import platform_scope
from eos_procurement.api.router import router
from eos_procurement.application.access import PERMISSION_KEYS
from eos_procurement.domain import rules
from eos_procurement.infrastructure.models import PREFIX, TABLES, AuditEntry
from eos_testing import assert_no_cross_tenant_leak
from pc_support import BASE, LATER, TODAY, approved_indent, indent, issued_order, item, receive, vendor
from sqlalchemy import create_engine, inspect, select

MODULE = Path(__file__).resolve().parents[2]


def seed(client, org):
    """One of everything, so every list has a row."""
    po = issued_order(client, org)
    receive(client, org, po, (0, 10, 10))
    inv = client.post(
        f"{BASE}/vendor-invoices",
        json={"purchase_order_id": po["id"], "invoice_number": "S/1", "invoice_date": TODAY, "amount": "1180.00"},
        headers=org.staff,
    ).json()
    vendor(client, org)
    t = client.post(
        f"{BASE}/tenders",
        json={
            "title": "t",
            "indent_ids": [approved_indent(client, org, "60000.00")["id"]],
            "method": "quotation",
            "category": "lab equipment",
            "closes_at": LATER,
        },
        headers=org.staff,
    ).json()
    return po, inv, t, indent(client, org)


def test_no_cross_tenant_leak(client, org, other_org):
    po_a, inv_a, tender_a, indent_a = seed(client, org)
    seed(client, other_org)
    indent_b = approved_indent(client, other_org)
    for path, who in (
        ("/vendors", "staff"),
        ("/indents", "manager"),
        ("/me/indents", "faculty"),
        ("/tenders", "staff"),
        ("/purchase-orders", "staff"),
        ("/vendor-invoices", "staff"),
    ):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", org.token(who), other_org.token(who))
    receipts_a = client.get(f"{BASE}/purchase-orders/{po_a['id']}/goods-receipts", headers=org.staff).json()
    assert receipts_a and {r["organisation_id"] for r in receipts_a} == {org.id}
    # reads across organisations are 404
    b = other_org
    for path, who in (
        (f"/purchase-orders/{po_a['id']}", "staff"),
        (f"/purchase-orders/{po_a['id']}/goods-receipts", "staff"),
        (f"/vendor-invoices/{inv_a['id']}", "staff"),
        (f"/tenders/{tender_a['id']}", "staff"),
        (f"/indents/{indent_a['id']}", "manager"),
        (f"/vendors/{po_a['vendor_id']}", "staff"),
    ):
        assert client.get(f"{BASE}{path}", headers=b.headers[who]).status_code == 404, path
    # writes across organisations are 404 and change nothing
    attempts = [
        ("post", f"/purchase-orders/{po_a['id']}/cancel", {"reason": "x"}, "manager"),
        (
            "post",
            f"/purchase-orders/{po_a['id']}/goods-receipts",
            {"received_on": TODAY, "items": [{"item_index": 0, "received": 1, "accepted": 1}]},
            "facility",
        ),
        ("post", f"/vendor-invoices/{inv_a['id']}/decision", {"decision": "approved"}, "staff"),
        ("post", f"/vendors/{po_a['vendor_id']}/status", {"status": "blacklisted", "reason": "x"}, "staff"),
        ("post", f"/indents/{indent_a['id']}/decision", {"decision": "rejected"}, "manager"),
        ("post", f"/tenders/{tender_a['id']}/publish", None, "staff"),
        (
            "post",
            "/vendor-invoices",
            {"purchase_order_id": po_a["id"], "invoice_number": "X", "invoice_date": TODAY, "amount": "1.00"},
            "staff",
        ),
        (
            "post",
            "/purchase-orders",
            {
                "vendor_id": po_a["vendor_id"],
                "indent_ids": [indent_b["id"]],
                "items": [item()],
                "delivery_by": "2026-11-30",
            },
            "staff",
        ),
    ]
    for method, path, body, who in attempts:
        r = getattr(client, method)(f"{BASE}{path}", json=body, headers=b.headers[who])
        assert r.status_code == 404, (path, r.status_code, r.text)
    assert client.get(f"{BASE}/purchase-orders/{po_a['id']}", headers=org.staff).json()["status"] == "received"
    assert client.get(f"{BASE}/vendor-invoices/{inv_a['id']}", headers=org.staff).json()["status"] == "recorded"
    assert client.get(f"{BASE}/vendors/{po_a['vendor_id']}", headers=org.staff).json()["status"] == "approved"


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


def _contract(name: str) -> dict:
    return yaml.safe_load((MODULE / "contracts" / name).read_text(encoding="utf-8"))


def test_permission_keys_match_the_catalogue():
    assert set(PERMISSION_KEYS) == {p["key"] for p in _contract("permissions.yaml")["permissions"]}


def test_every_contract_operation_is_served_with_its_permission():
    openapi = _contract("openapi.yaml")
    contract = {}
    for path, ops in openapi["paths"].items():
        for method, op in ops.items():
            if method in ("get", "post", "put", "delete", "patch"):
                contract[(method.upper(), path)] = op["summary"]
    served = {}
    for route in router.routes:
        path = route.path
        for name in ("vendor_id", "indent_id", "tender_id", "po_id", "invoice_id"):
            path = path.replace("{" + name + "}", "{id}")
        perms = next(d.call.permissions for d in route.dependant.dependencies if hasattr(d.call, "permissions"))
        for m in route.methods:
            served[(m, path)] = perms
    assert set(served) == set(contract)
    for key, perms in served.items():
        # the permission the contract names for the operation; one indent is also readable by its requester
        named = set(perms) - ({"procurement:indent:create"} if key == ("GET", "/indents/{id}") else set())
        assert named and all(perm in contract[key] for perm in named), (key, perms)


def test_enums_match_the_contract():
    schemas = _contract("openapi.yaml")["components"]["schemas"]
    assert list(rules.VENDOR_STATUSES) == schemas["VendorStatus"]["enum"]
    assert list(rules.INDENT_STATUSES) == schemas["IndentStatus"]["enum"]
    assert list(rules.TENDER_STATUSES) == schemas["TenderStatus"]["enum"]
    assert list(rules.PURCHASE_ORDER_STATUSES) == schemas["PurchaseOrderStatus"]["enum"]
    assert list(rules.VENDOR_INVOICE_STATUSES) == schemas["VendorInvoiceStatus"]["enum"]
    assert list(rules.PURCHASE_METHODS) == schemas["Indent"]["allOf"][1]["properties"]["purchase_method"]["enum"]
    assert list(rules.TENDER_METHODS) == schemas["TenderInput"]["properties"]["method"]["enum"]


def test_published_events_carry_exactly_the_payload_of_events_yaml(client, org, monkeypatch):
    """Every procurement.* event in the outbox, after a full run, has the keys events.yaml declares: budget-grants and
    notification read these payloads."""
    declared = {e["name"]: set(e["payload"]) for e in _contract("events.yaml")["events"]}
    seed(client, org)
    i = indent(client, org)
    client.post(f"{BASE}/indents/{i['id']}/submit", headers=org.faculty)
    client.post(f"{BASE}/indents/{i['id']}/decision", json={"decision": "rejected", "note": "no"}, headers=org.manager)
    v = vendor(client, org)
    client.post(f"{BASE}/vendors/{v['id']}/status", json={"status": "blacklisted", "reason": "x"}, headers=org.staff)
    po = issued_order(client, org)
    client.post(f"{BASE}/purchase-orders/{po['id']}/cancel", json={"reason": "x"}, headers=org.manager)
    with SessionLocal() as db, platform_scope():
        published = list(db.scalars(select(OutboxEvent).where(OutboxEvent.organisation_id == org.id)))
    names = {e.name for e in published}
    assert names >= set(declared) - {
        "procurement.tender.awarded",
        "procurement.tender.published",
        "procurement.vendor-invoice.approved",
        "procurement.vendor-invoice.paid",
    }
    for e in published:
        assert e.name in declared, e.name
        assert set(e.payload) == declared[e.name], (e.name, set(e.payload) ^ declared[e.name])


def test_every_state_change_is_audited(client, org):
    po = issued_order(client, org)
    receive(client, org, po, (0, 10, 10))
    with SessionLocal() as db, platform_scope():
        rows = list(db.scalars(select(AuditEntry).where(AuditEntry.organisation_id == org.id)))
    actions = {(r.action, r.actor) for r in rows}
    staff, manager, faculty, facility = (org.ids[x] for x in ("staff", "manager", "faculty", "facility"))
    for expected in (
        ("vendor.registered", staff),
        ("vendor.approved", staff),
        ("indent.created", faculty),
        ("indent.submitted", faculty),
        ("indent.approved", manager),
        ("purchase_order.created", staff),
        ("purchase_order.submitted", staff),
        ("purchase_order.issued", manager),
        ("indent.ordered", manager),
        ("goods_receipt.recorded", facility),
        ("purchase_order.received", facility),
        ("indent.closed", facility),
    ):
        assert expected in actions, expected
    assert {r.entity_id for r in rows if r.entity == "purchase_order"} == {po["id"]}


@pytest.mark.parametrize(
    "role",
    ["finance-staff", "management", "department-admin", "facility-staff", "faculty", "research-office", "org-admin"],
)
def test_every_role_in_the_catalogue_uses_known_keys(role):
    roles = {r["name"]: r["grants"] for r in _contract("permissions.yaml")["roles"]}
    assert set(roles[role]) <= set(PERMISSION_KEYS)
