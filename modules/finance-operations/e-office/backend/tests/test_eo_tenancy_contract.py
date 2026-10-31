"""The cross-tenant leak test, reads and writes across organisations, the Alembic chain, drift between code and contract,
event payloads against events.yaml, and the audit trail."""

import re
import tempfile
from pathlib import Path

import pytest
import yaml
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from eo_support import BASE, TODAY, approved_file, attach, category, decide, forward, note, open_file, receipt
from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_core.tenant import platform_scope
from eos_e_office.api.router import router
from eos_e_office.application import service
from eos_e_office.application.access import PERMISSION_KEYS
from eos_e_office.domain import rules
from eos_e_office.infrastructure.models import PREFIX, TABLES, AuditEntry
from eos_testing import assert_no_cross_tenant_leak
from sqlalchemy import create_engine, inspect, select

MODULE = Path(__file__).resolve().parents[2]


def seed(client, org):
    """One of everything, so every list has a row: a file held by hr (also forwarded by hr to the department admin
    and back), a receipt sent to hr, a pending dispatch."""
    f, letter = approved_file(client, org)
    r = receipt(client, org, to="hr")
    d = client.post(
        f"{BASE}/dispatches",
        json={"file_id": f["id"], "attachment_id": letter["id"], "addressee": "The Director"},
        headers=org.hr,
    ).json()
    return f, r, d


def test_no_cross_tenant_leak(client, org, other_org):
    f_a, r_a, d_a = seed(client, org)
    f_b, _, _ = seed(client, other_org)
    for path, who in (
        ("/categories", "hr"),
        ("/files", "hr"),
        ("/files", "manager"),
        ("/me/inbox", "hr"),
        ("/me/sent", "hr"),
        ("/me/receipts", "hr"),
        ("/receipts", "hr"),
        ("/dispatches", "hr"),
    ):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", org.token(who), other_org.token(who))
    inbox_a = client.get(f"{BASE}/me/inbox", headers=org.hr).json()
    assert [x["id"] for x in inbox_a["items"]] == [f_a["id"]] and inbox_a["unattached_receipts"] == 1
    report = client.get(f"{BASE}/reports/pendency", headers=org.dept).json()
    assert report["open_files"] == 1
    # reads across organisations are 404, even for a holder of the same role
    b = other_org
    for path, who in (
        (f"/files/{f_a['id']}", "hr"),
        (f"/files/{f_a['id']}", "manager"),
        (f"/files/{f_a['id']}/movements", "hr"),
        (f"/receipts/{r_a['id']}", "hr"),
    ):
        assert client.get(f"{BASE}{path}", headers=b.headers[who]).status_code == 404, path
    # writes across organisations are 404 and change nothing
    cat_a = client.get(f"{BASE}/categories", headers=org.hr).json()[0]
    attempts = [
        ("put", f"/categories/{cat_a['id']}", {"code": "STOLEN", "name": "x"}, "admin"),
        ("post", f"/files/{f_a['id']}/notes", {"text": "x"}, "hr"),
        ("post", f"/files/{f_a['id']}/attachments", {"document_id": "d", "title": "t"}, "hr"),
        ("post", f"/files/{f_a['id']}/forward", {"to_user_id": b.ids["hr"]}, "hr"),
        ("post", f"/files/{f_a['id']}/decision", {"decision": "rejected", "remark": "x"}, "dept"),
        ("post", f"/files/{f_a['id']}/close", {"remark": "x"}, "hr"),
        ("post", f"/files/{f_a['id']}/reopen", {"remark": "x"}, "hr"),
        ("post", f"/receipts/{r_a['id']}/attach", {"file_id": f_b["id"]}, "hr"),
        ("post", f"/dispatches/{d_a['id']}/mark-sent", {"mode": "post", "sent_on": TODAY}, "hr"),
        ("post", "/files", {"subject": "x", "category_id": cat_a["id"]}, "hr"),
        (
            "post",
            "/dispatches",
            {"file_id": f_a["id"], "attachment_id": d_a["attachment_id"], "addressee": "x"},
            "hr",
        ),
    ]
    for method, path, body, who in attempts:
        r = getattr(client, method)(f"{BASE}{path}", json=body, headers=b.headers[who])
        assert r.status_code in (404, 422), (path, r.status_code, r.text)
        if path == "/files":
            assert r.json()["detail"]["code"] == "unknown_category"
    got = client.get(f"{BASE}/files/{f_a['id']}", headers=org.hr).json()
    assert got["status"] == "open" and got["holder"]["user_id"] == org.ids["hr"] and got["last_decision"] == "approved"
    assert client.get(f"{BASE}/receipts/{r_a['id']}", headers=org.hr).json()["status"] == "registered"
    assert client.get(f"{BASE}/dispatches", headers=org.hr).json()["items"][0]["status"] == "pending"
    assert client.get(f"{BASE}/categories", headers=org.hr).json()[0]["code"] == cat_a["code"]


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
            assert t.name.startswith(PREFIX)
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
        for name in ("category_id", "file_id", "receipt_id", "dispatch_id"):
            path = path.replace("{" + name + "}", "{id}")
        perms = next(d.call.permissions for d in route.dependant.dependencies if hasattr(d.call, "permissions"))
        for m in route.methods:
            served[(m, path)] = perms
    assert set(served) == set(contract)
    for key, perms in served.items():
        assert perms and all(perm in contract[key] for perm in perms), (key, perms)


def test_every_error_code_the_backend_raises_is_in_the_contract():
    """Reviewers read the contract for the codes a client must handle; a new code must be documented with it."""
    src = MODULE / "backend" / "src" / "eos_e_office"
    code = "\n".join(
        (src / part).read_text(encoding="utf-8")
        for part in ("application/service.py", "application/reports.py", "domain/rules.py")
    )
    codes = set(re.findall(r'(?:invalid|conflict)\(\s*"([a-z_]+)"', code))
    codes |= set(re.findall(r'EOfficeError\(\s*\d+,\s*"([a-z_]+)"', code))
    codes |= set(re.findall(r'_duplicate_is_409\(\s*"([a-z_]+)"', code))
    codes |= set(re.findall(r'RuleError\(\s*"([a-z_]+)"', code))
    codes |= {f"invalid_{f}" for f in re.findall(r'_required\([^,]+,\s*"([a-z_]+)"\)', code)}
    assert len(codes) > 25  # the patterns still find the codes
    contract = (MODULE / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
    assert sorted(c for c in codes if f"`{c}`" not in contract) == []


def test_enums_match_the_contract():
    schemas = _contract("openapi.yaml")["components"]["schemas"]
    assert list(rules.FILE_STATUSES) == schemas["FileStatus"]["enum"]
    assert list(rules.PRIORITIES) == schemas["Priority"]["enum"]
    assert list(rules.MODES) == schemas["Mode"]["enum"]
    assert list(rules.DECISIONS) == schemas["DecisionInput"]["properties"]["decision"]["enum"]
    assert list(rules.NOTE_KINDS) == schemas["Note"]["properties"]["kind"]["enum"]
    assert list(rules.MOVEMENT_KINDS) == schemas["Movement"]["properties"]["kind"]["enum"]
    assert list(rules.ATTACHMENT_KINDS) == schemas["AttachmentInput"]["properties"]["kind"]["enum"]
    assert list(rules.RECEIPT_STATUSES) == schemas["Receipt"]["allOf"][1]["properties"]["status"]["enum"]
    assert list(rules.DISPATCH_STATUSES) == schemas["Dispatch"]["allOf"][1]["properties"]["status"]["enum"]
    buckets = schemas["PendencyReport"]["properties"]["by_age"]["items"]["properties"]["bucket"]["enum"]
    assert [b[0] for b in rules.AGE_BUCKETS] == buckets


def test_the_inbox_answers_the_contract_the_widget_reads(client, org):
    """GET /me/inbox backs the e-office.files-pending widget: every Inbox and FileSummary property is present."""
    schemas = _contract("openapi.yaml")["components"]["schemas"]
    open_file(client, org)
    inbox = client.get(f"{BASE}/me/inbox", headers=org.hr).json()
    assert set(inbox) == set(schemas["Inbox"]["properties"])
    assert set(inbox["items"][0]) == set(schemas["FileSummary"]["properties"])


def test_published_events_carry_exactly_the_payload_of_events_yaml(client, org, clock):
    """Every e-office.* event in the outbox, after a full run, has the keys events.yaml declares: notification reads
    these payloads."""
    declared = {e["name"]: set(e["payload"]) for e in _contract("events.yaml")["events"]}
    f, _, d = seed(client, org)
    client.post(f"{BASE}/dispatches/{d['id']}/mark-sent", json={"mode": "post", "sent_on": TODAY}, headers=org.hr)
    client.post(f"{BASE}/files/{f['id']}/close", json={"remark": "done"}, headers=org.hr)
    late = open_file(client, org)
    clock.advance(days=10)
    from types import SimpleNamespace

    from eos_e_office.application import consumers

    with SessionLocal() as db, platform_scope():
        consumers.on_job_due(
            db, SimpleNamespace(organisation_id=None, payload={"job": "e-office.flag-overdue", "run_id": "r"})
        )
        db.commit()
        published = list(db.scalars(select(OutboxEvent).where(OutboxEvent.organisation_id == org.id)))
        finished = list(db.scalars(select(OutboxEvent).where(OutboxEvent.name == "e-office.job.finished")))
    assert late["id"] in {e.payload.get("file_id") for e in published}
    assert {e.name for e in published} == set(declared) - {"e-office.job.finished"}
    for e in published + finished:
        assert e.name in declared, e.name
        assert set(e.payload) == declared[e.name], (e.name, set(e.payload) ^ declared[e.name])


def test_every_state_change_is_audited(client, org):
    cat = category(client, org)
    f = open_file(client, org, cat=cat)
    note(client, org, f, "hr")
    attach(client, org, f, "hr")
    forward(client, org, f, "hr", "dept")
    decide(client, org, f, "dept")
    client.post(f"{BASE}/files/{f['id']}/close", json={"remark": "done"}, headers=org.dept)
    client.post(f"{BASE}/files/{f['id']}/reopen", json={"remark": "again"}, headers=org.hr)
    r = receipt(client, org, to="hr")
    client.post(f"{BASE}/receipts/{r['id']}/attach", json={"file_id": f["id"]}, headers=org.hr)
    with SessionLocal() as db, platform_scope():
        rows = list(db.scalars(select(AuditEntry).where(AuditEntry.organisation_id == org.id)))
    actions = {(r.action, r.actor) for r in rows}
    hr, dept, admin = (org.ids[x] for x in ("hr", "dept", "admin"))
    for expected in (
        ("category.created", admin),
        ("file.created", hr),
        ("file.noted", hr),
        ("file.attached", hr),
        ("file.forwarded", hr),
        ("file.approved", dept),
        ("file.closed", dept),
        ("file.reopened", hr),
        ("receipt.registered", hr),
        ("receipt.attached", hr),
    ):
        assert expected in actions, expected
    assert {r.entity_id for r in rows if r.entity == "file"} == {f["id"]}


def test_note_text_never_reaches_the_audit_trail_or_events(client, org):
    f = open_file(client, org, first_note="CONFIDENTIAL-PHRASE")
    note(client, org, f, "hr", "CONFIDENTIAL-PHRASE again")
    forward(client, org, f, "hr", "dept", remark="CONFIDENTIAL-PHRASE")
    decide(client, org, f, "dept", remark="CONFIDENTIAL-PHRASE")
    with SessionLocal() as db, platform_scope():
        audit = [(r.action, r.entity, r.entity_id) for r in db.scalars(select(AuditEntry))]
        payloads = [e.payload for e in db.scalars(select(OutboxEvent).where(OutboxEvent.organisation_id == org.id))]
    assert "CONFIDENTIAL-PHRASE" not in str(audit) + str(payloads)


@pytest.mark.parametrize(
    "role", [r["name"] for r in yaml.safe_load((MODULE / "contracts" / "permissions.yaml").read_text())["roles"]]
)
def test_every_role_in_the_catalogue_uses_known_keys(role):
    roles = {r["name"]: r["grants"] for r in _contract("permissions.yaml")["roles"]}
    assert set(roles[role]) <= set(PERMISSION_KEYS)


def test_business_today_follows_the_clock(clock):
    assert service.business_today().isoformat() == TODAY
