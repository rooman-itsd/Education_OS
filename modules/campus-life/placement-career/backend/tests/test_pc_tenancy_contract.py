"""The cross-tenant leak test, reads and writes across organisations, the Alembic chain, drift between code and contract
(routes, permissions, error codes, enums, response shapes), event payloads against events.yaml, and the audit trail."""

import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

import pytest
import yaml
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from eos_core.config import permissions_for
from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_placement_career.api.router import router
from eos_placement_career.application import access, common
from eos_placement_career.domain import rules
from eos_placement_career.infrastructure.models import PREFIX, TABLES, AuditEntry
from eos_testing import assert_no_cross_tenant_leak
from pc_support import BASE, TODAY, applied, company, day, drive, move, ok, opening, outbox
from sqlalchemy import create_engine, inspect, select

MODULE = Path(__file__).resolve().parents[2]


def _contract(name: str) -> dict:
    return yaml.safe_load((MODULE / "contracts" / name).read_text(encoding="utf-8"))


def seed(client, org) -> dict:
    """One of everything: a company, a scheduled drive with an open opening, an opening on its own, an application
    with an offer accepted and one still applied."""
    co = company(client, org)
    d = drive(client, org, co)
    o = opening(client, org, dr=d)
    alone = opening(client, org, co=co)
    a = applied(client, org, o)
    for step in ("shortlisted", "in_process", "offered", "accepted"):
        ok(move(client, org, a, step, offer={"ctc_per_annum": "800000"}))
    b = applied(client, org, alone, who="student2")
    return {"company": co, "drive": d, "opening": o, "alone": alone, "accepted": a, "applied": b}


# ---------------------------------------------------------------- tenancy


def test_no_cross_tenant_leak(client, org, other_org):
    a = seed(client, org)
    b = seed(client, other_org)
    for path, who in (
        ("/companies", "officer"),
        ("/drives", "officer"),
        ("/drives", "student"),
        ("/openings", "officer"),
        ("/openings", "viewer"),
        ("/applications", "officer"),
        ("/me/applications", "student"),
    ):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", org.token(who), other_org.token(who))
    mine_a = {o["id"] for o in ok(client.get(f"{BASE}/me/openings", headers=org.student))["items"]}
    mine_b = {o["id"] for o in ok(client.get(f"{BASE}/me/openings", headers=other_org.student))["items"]}
    assert mine_a == {a["opening"]["id"], a["alone"]["id"]} and mine_b == {b["opening"]["id"], b["alone"]["id"]}
    summary = ok(client.get(f"{BASE}/reports/openings-summary", headers=org.officer))
    assert summary["students_placed"] == 1 and summary["openings"]["open"] == 2
    assert {o["id"] for o in summary["closing_soon"]} == mine_a
    upcoming = ok(client.get(f"{BASE}/reports/drives-upcoming", headers=org.officer))
    assert [d["id"] for d in upcoming["drives"]] == [a["drive"]["id"]] and upcoming["next_30_days"] == 1


def test_reads_and_writes_across_organisations_are_404(client, org, other_org):
    a = seed(client, org)
    them = other_org
    for path, who in (
        (f"/companies/{a['company']['id']}", "officer"),
        (f"/drives/{a['drive']['id']}", "officer"),
        (f"/openings/{a['opening']['id']}", "officer"),
        (f"/applications/{a['accepted']['id']}", "officer"),
    ):
        assert client.get(f"{BASE}{path}", headers=them.headers[who]).status_code == 404, path
    theirs = company(client, them)
    attempts = [
        ("put", f"/companies/{a['company']['id']}", {"name": "Stolen"}, "officer"),
        ("post", "/drives", {"company_id": a["company"]["id"], "title": "x", "scheduled_on": day(10)}, "officer"),
        (
            "put",
            f"/drives/{a['drive']['id']}",
            {"company_id": theirs["id"], "title": "x", "scheduled_on": day(10)},
            "officer",
        ),
        ("post", f"/drives/{a['drive']['id']}/schedule", None, "officer"),
        ("post", f"/drives/{a['drive']['id']}/complete", None, "officer"),
        ("post", f"/drives/{a['drive']['id']}/cancel", {"reason": "x"}, "officer"),
        (
            "post",
            "/openings",
            {"company_id": theirs["id"], "drive_id": a["drive"]["id"], "title": "x", "applications_close_on": day(5)},
            "officer",
        ),
        (
            "put",
            f"/openings/{a['alone']['id']}",
            {"company_id": theirs["id"], "title": "x", "applications_close_on": day(5)},
            "officer",
        ),
        ("post", f"/openings/{a['alone']['id']}/publish", None, "officer"),
        ("post", f"/openings/{a['alone']['id']}/close", None, "officer"),
        ("post", f"/openings/{a['alone']['id']}/cancel", {"reason": "x"}, "officer"),
        ("post", f"/applications/{a['applied']['id']}/status", {"status": "shortlisted"}, "officer"),
        ("post", "/me/applications", {"opening_id": a["alone"]["id"], "declares_eligible": True}, "student"),
        ("post", f"/me/applications/{a['applied']['id']}/withdraw", None, "student2"),
    ]
    for method, path, body, who in attempts:
        r = getattr(client, method)(f"{BASE}{path}", json=body, headers=them.headers[who])
        assert r.status_code == 404 and r.json()["detail"]["code"] == "not_found", (path, r.status_code, r.text)
    assert ok(client.get(f"{BASE}/companies/{a['company']['id']}", headers=org.officer))["name"] == a["company"]["name"]
    assert ok(client.get(f"{BASE}/drives/{a['drive']['id']}", headers=org.officer))["status"] == "scheduled"
    assert ok(client.get(f"{BASE}/openings/{a['alone']['id']}", headers=org.officer))["status"] == "open"
    assert ok(client.get(f"{BASE}/applications/{a['applied']['id']}", headers=org.officer))["status"] == "applied"


def test_a_token_without_an_organisation_is_refused(client):
    from pc_support import auth, token

    r = client.get(f"{BASE}/companies", headers=auth(token("u1", None, ["placement-officer"])))
    assert r.status_code == 403 and r.json()["detail"]["code"] == "forbidden"


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


def test_the_migration_lists_every_table_and_enables_rls_on_each():
    source = next((MODULE / "db" / "migrations" / "versions").glob("*_initial.py")).read_text(encoding="utf-8")
    for t in TABLES:
        assert f'_enable_rls("{t.name}")' in source, t.name


# ---------------------------------------------------------------- contract drift


def test_permission_keys_match_the_catalogue():
    assert set(access.PERMISSION_KEYS) == {p["key"] for p in _contract("permissions.yaml")["permissions"]}


def test_every_role_in_the_catalogue_uses_known_keys():
    for role in _contract("permissions.yaml")["roles"]:
        assert set(role["grants"]) <= set(access.PERMISSION_KEYS), role["name"]


def test_the_layouts_hold_the_module_roles_the_prd_names():
    officer = {k for k in permissions_for(["placement-officer"]) if k.startswith("placement-career:")}
    assert officer == set(access.PERMISSION_KEYS) - {access.SELF_READ, access.SELF_APPLY}
    for role in ("industry-coordinator", "practicum-coordinator"):
        assert officer <= permissions_for([role]), role
    viewer = {k for k in permissions_for(["industry-liaison"]) if k.startswith("placement-career:")}
    assert viewer == {access.COMPANY_READ, access.OPENING_READ, access.REPORT_READ}
    for role in ("student", "management-student", "engineering-student"):
        learner = {k for k in permissions_for([role]) if k.startswith("placement-career:")}
        assert learner == {access.OPENING_READ, access.SELF_READ, access.SELF_APPLY}, role


def test_every_contract_operation_is_served_with_its_permission():
    openapi = _contract("openapi.yaml")
    contract = {}
    for path, ops in openapi["paths"].items():
        for method, op in ops.items():
            if method in ("get", "post", "put", "delete", "patch"):
                contract[(method.upper(), path)] = op["summary"]
    served = {}
    for route in router.routes:
        path = re.sub(r"\{[a-z_]+_id\}", "{id}", route.path)
        perms = next(d.call.permissions for d in route.dependant.dependencies if hasattr(d.call, "permissions"))
        for m in route.methods:
            served[(m, path)] = perms
    assert set(served) == set(contract)
    for key, perms in served.items():
        assert len(perms) == 1 and perms[0] in contract[key], (key, perms)
        named = set(re.findall(r"placement-career:[a-z]+:[a-z]+", contract[key]))
        assert set(perms) <= named, (key, perms, named)


def _raised_codes() -> set[str]:
    src = MODULE / "backend" / "src" / "eos_placement_career"
    code = "\n".join(p.read_text(encoding="utf-8") for p in (src / "application").glob("*.py"))
    code += (src / "domain" / "rules.py").read_text(encoding="utf-8")
    codes = set(re.findall(r'(?:invalid|conflict)\(\s*"([a-z_]+)"', code))
    codes |= set(re.findall(r'PlacementError\(\s*\d+,\s*"([a-z_]+)"', code))
    codes |= set(re.findall(r'duplicate_is_409\(\s*"([a-z_]+)"', code))
    codes |= set(re.findall(r'RuleError\(\s*"([a-z_]+)"', code))
    if "not_found(" in code:
        codes.add("not_found")
    return codes


def test_error_codes_match_the_contract_both_ways():
    """Every code the backend raises is documented, and every documented code is raised."""
    description = _contract("openapi.yaml")["info"]["description"]
    documented = set(re.findall(r"`([a-z_]+)`", description)) - {"forbidden"}
    raised = _raised_codes()
    assert sorted(raised - documented) == []
    assert sorted(documented - raised) == []


def test_enums_match_the_contract():
    schemas = _contract("openapi.yaml")["components"]["schemas"]
    assert list(rules.DRIVE_STATUSES) == schemas["DriveStatus"]["enum"]
    assert list(rules.OPENING_STATUSES) == schemas["OpeningStatus"]["enum"]
    assert list(rules.APPLICATION_STATUSES) == schemas["ApplicationStatus"]["enum"]
    assert list(rules.STEPS) == schemas["StatusChange"]["properties"]["status"]["enum"]
    assert list(rules.APPLICATION_STATUSES) == list(schemas["CountsByApplicationStatus"]["properties"])


def _props(schemas: dict, name: str) -> set[str]:
    schema = schemas[name]
    out: set[str] = set()
    for part in schema.get("allOf", [schema]):
        if "$ref" in part:
            out |= _props(schemas, part["$ref"].rsplit("/", 1)[1])
        out |= set(part.get("properties", {}))
    return out


def test_responses_carry_exactly_the_contract_properties(client, org):
    schemas = _contract("openapi.yaml")["components"]["schemas"]
    s = seed(client, org)
    company_ = ok(client.get(f"{BASE}/companies/{s['company']['id']}", headers=org.officer))
    assert set(company_) == _props(schemas, "Company")
    assert set(ok(client.get(f"{BASE}/companies", headers=org.officer))) == _props(schemas, "CompanyPage")
    drive_ = ok(client.get(f"{BASE}/drives/{s['drive']['id']}", headers=org.officer))
    assert set(drive_) == _props(schemas, "Drive")  # openings on GET /drives/{id} only
    assert set(drive_["company"]) == _props(schemas, "CompanySummary")
    assert set(drive_["eligibility"]) == _props(schemas, "Eligibility")
    assert set(drive_["openings"][0]) == _props(schemas, "OpeningSummary")
    listed = ok(client.get(f"{BASE}/drives", headers=org.officer))["items"][0]
    assert set(listed) == _props(schemas, "Drive") - {"openings"}
    opening_ = ok(client.get(f"{BASE}/openings/{s['opening']['id']}", headers=org.officer))
    assert set(opening_) == _props(schemas, "Opening")
    assert set(opening_["drive"]) == set(schemas["Opening"]["allOf"][1]["properties"]["drive"]["properties"])
    application = ok(client.get(f"{BASE}/applications/{s['accepted']['id']}", headers=org.officer))
    assert set(application) == _props(schemas, "Application")
    assert set(application["declared"]) == _props(schemas, "Declaration")
    assert set(application["offer"]) == _props(schemas, "Offer")
    assert set(application["history"][0]) == _props(schemas, "HistoryEntry")
    row = ok(client.get(f"{BASE}/applications", headers=org.officer))["items"][0]
    assert set(row) == _props(schemas, "Application") - {"history"}
    mine = ok(client.get(f"{BASE}/me/applications", headers=org.student))["items"][0]
    assert set(mine) == _props(schemas, "MyApplication")
    my_opening = next(
        o for o in ok(client.get(f"{BASE}/me/openings", headers=org.student2))["items"] if o["my_application"]
    )
    assert set(my_opening) == _props(schemas, "MyOpening")
    assert set(my_opening["my_application"]) == {"id", "status"}
    upcoming = ok(client.get(f"{BASE}/reports/drives-upcoming", headers=org.officer))
    assert set(upcoming) == _props(schemas, "DrivesUpcomingReport")
    item = schemas["DrivesUpcomingReport"]["properties"]["drives"]["items"]["properties"]
    assert set(upcoming["drives"][0]) == set(item)
    summary = ok(client.get(f"{BASE}/reports/openings-summary", headers=org.officer))
    assert set(summary) == _props(schemas, "OpeningsSummaryReport")
    report = schemas["OpeningsSummaryReport"]["properties"]
    assert set(summary["openings"]) == set(report["openings"]["properties"])
    assert set(summary["closing_soon"][0]) == set(report["closing_soon"]["items"]["properties"])


# ---------------------------------------------------------------- events


def _is_uuid(value) -> bool:
    try:
        UUID(str(value))
    except ValueError:
        return False
    return True


def _is_date(value) -> bool:
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return True


CHECK = {"uuid": _is_uuid, "date": _is_date, "string": lambda v: isinstance(v, str) and v != ""}


def test_published_events_carry_exactly_the_payload_of_events_yaml(client, org, clock):
    """A full run publishes every event of events.yaml once at least; every payload has exactly the declared keys,
    each of the declared type ("?" allows null), and the envelope's organisation and actor."""
    declared = {e["name"]: e["payload"] for e in _contract("events.yaml")["events"]}
    s = seed(client, org)
    d = s["drive"]
    body = {"company_id": d["company_id"], "title": d["title"], "scheduled_on": day(11), "ends_on": day(12)}
    ok(client.put(f"{BASE}/drives/{d['id']}", json=body, headers=org.officer))  # rescheduled
    ok(client.post(f"{BASE}/openings/{s['alone']['id']}/close", headers=org.officer))  # closed
    rejected = applied(client, org, s["opening"], who="student2")
    ok(move(client, org, rejected, "rejected", reason="Profile does not match"))
    declined = applied(client, org, s["opening"], who="student3")
    for step in ("shortlisted", "in_process", "offered", "declined"):
        ok(move(client, org, declined, step))
    withdrawn = applied(client, org, opening(client, org), who="student3")
    ok(client.post(f"{BASE}/me/applications/{withdrawn['id']}/withdraw", headers=org.student3))
    gone = drive(client, org)
    opening(client, org, dr=gone)
    ok(client.post(f"{BASE}/drives/{gone['id']}/cancel", json={"reason": "Company postponed"}, headers=org.officer))
    clock.advance(days=12)
    ok(client.post(f"{BASE}/drives/{d['id']}/complete", headers=org.officer))
    published = outbox(org.id)
    assert {e.name for e in published} == set(declared)
    for e in published:
        assert e.organisation_id == org.id and e.payload["organisation_id"] == org.id
        assert e.actor in org.ids.values()
        assert set(e.payload) == set(declared[e.name]), (e.name, set(e.payload) ^ set(declared[e.name]))
        for key, kind in declared[e.name].items():
            value = e.payload[key]
            if kind.endswith("?") and value is None:
                continue
            assert CHECK[kind.rstrip("?")](value), (e.name, key, value)


def test_no_names_declarations_offers_or_contacts_in_events(client, org):
    """P9: payloads carry ids, dates and the cancel reason only."""
    co = company(client, org, name="SECRET-COMPANY", contact_email="secret-contact@x.example", contact_name="SECRET-HR")
    o = opening(client, org, co=co, ctc_per_annum="987654.32")
    a = applied(client, org, o, declared={"programme": "SECRET-PROGRAMME", "cgpa": 9.87})
    for step in ("shortlisted", "in_process"):
        ok(move(client, org, a, step))
    ok(move(client, org, a, "offered", offer={"ctc_per_annum": "123456.78", "notes": "SECRET-NOTE"}))
    payloads = str([e.payload for e in outbox(org.id)])
    for secret in ("SECRET", "secret", "987654", "123456", "9.87", "Asha Rao"):
        assert secret not in payloads, secret


# ---------------------------------------------------------------- audit


def test_every_state_change_is_audited(client, org, clock):
    s = seed(client, org)
    co = s["company"]
    ok(client.put(f"{BASE}/companies/{co['id']}", json={"name": co["name"], "active": False}, headers=org.officer))
    ok(client.put(f"{BASE}/companies/{co['id']}", json={"name": co["name"], "active": True}, headers=org.officer))
    d = s["drive"]
    ok(
        client.put(
            f"{BASE}/drives/{d['id']}",
            json={"company_id": co["id"], "title": "x", "scheduled_on": day(11)},
            headers=org.officer,
        )
    )
    ok(
        client.put(
            f"{BASE}/openings/{s['alone']['id']}",
            json={"company_id": co["id"], "title": "y", "applications_close_on": day(5)},
            headers=org.officer,
        )
    )
    ok(client.post(f"{BASE}/openings/{s['alone']['id']}/close", headers=org.officer))
    ok(client.post(f"{BASE}/me/applications/{s['applied']['id']}/withdraw", headers=org.student2))
    r = applied(client, org, s["opening"], who="student3")
    ok(move(client, org, r, "rejected", reason="x"))
    c1 = opening(client, org, co=co, publish=False)
    ok(client.post(f"{BASE}/openings/{c1['id']}/cancel", json={"reason": "x"}, headers=org.officer))
    gone = drive(client, org, schedule=False)
    ok(client.post(f"{BASE}/drives/{gone['id']}/cancel", json={"reason": "x"}, headers=org.officer))
    clock.advance(days=12)
    ok(client.post(f"{BASE}/drives/{d['id']}/complete", headers=org.officer))
    with SessionLocal() as db, platform_scope():
        rows = list(db.scalars(select(AuditEntry).where(AuditEntry.organisation_id == org.id)))
    actions = {(row.action, row.actor) for row in rows}
    officer, student, student2 = (org.ids[x] for x in ("officer", "student", "student2"))
    for expected in (
        ("company.created", officer),
        ("company.deactivated", officer),
        ("company.reactivated", officer),
        ("drive.created", officer),
        ("drive.updated", officer),
        ("drive.scheduled", officer),
        ("drive.rescheduled", officer),
        ("drive.completed", officer),
        ("drive.cancelled", officer),
        ("opening.created", officer),
        ("opening.updated", officer),
        ("opening.published", officer),
        ("opening.closed", officer),
        ("opening.cancelled", officer),
        ("application.submitted", student),
        ("application.shortlisted", officer),
        ("application.in_process", officer),
        ("application.offered", officer),
        ("application.accepted", officer),
        ("application.rejected", officer),
        ("application.withdrawn", student2),
    ):
        assert expected in actions, expected
    assert all(isinstance(row.occurred_at, datetime) for row in rows)


def test_business_today_follows_the_clock(clock):
    assert common.business_today() == TODAY
    clock.now = clock.now.replace(hour=18, minute=31)  # 00:01 on 4 November in Asia/Kolkata
    assert common.business_today().isoformat() == "2026-11-04"


@pytest.mark.parametrize("module", ["domain/rules.py"])
def test_the_domain_imports_no_framework(module):
    source = (MODULE / "backend" / "src" / "eos_placement_career" / module).read_text(encoding="utf-8")
    assert not re.search(r"^(from|import) (fastapi|sqlalchemy|eos_core)", source, re.M)
