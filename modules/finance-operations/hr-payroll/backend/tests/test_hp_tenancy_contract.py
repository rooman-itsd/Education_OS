"""The cross-tenant leak test, reads and writes across organisations, the Alembic chain, drift between code and contract,
event payloads against events.yaml, the scheduler declaration and the audit trail."""

import re
import tempfile
from datetime import UTC, datetime
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
from eos_hr_payroll.api.router import router
from eos_hr_payroll.application import common, consumers, jobs
from eos_hr_payroll.application.access import PERMISSION_KEYS
from eos_hr_payroll.domain import rules
from eos_hr_payroll.infrastructure.models import PREFIX, TABLES, AuditEntry
from eos_testing import assert_no_cross_tenant_leak
from hp_support import BASE, apply, approved_run, decide, employee, leave_type, salary
from sqlalchemy import create_engine, inspect, select

MODULE = Path(__file__).resolve().parents[2]


def seed(client, org):
    """One of everything, so every list has a row."""
    e = employee(client, org)
    salary(client, org, e)
    t = leave_type(client, org)
    req = apply(client, org, "faculty", t, "2026-11-02", "2026-11-02").json()
    run = approved_run(client, org)
    appraisal = client.post(f"{BASE}/appraisals", json={"cycle": "2026-27", "employee_ids": [e["id"]]}, headers=org.hr)
    return e, t, req, run, appraisal.json()[0]


def test_no_cross_tenant_leak(client, org, other_org):
    e_a, t_a, req_a, run_a, appraisal_a = seed(client, org)
    seed(client, other_org)
    for path, who in (
        ("/employees", "hr"),
        ("/leave-types", "hr"),
        ("/leave-requests", "hr"),
        ("/payroll-runs", "hr"),
        ("/payroll-runs/current", "hr"),
        (f"/payroll-runs/{run_a['id']}/payslips", "hr"),
        ("/appraisals", "hr"),
        ("/me", "faculty"),
        ("/me/leave-requests", "faculty"),
        ("/me/payslips", "faculty"),
        ("/me/appraisals", "faculty"),
    ):
        if "/payslips" in path and not path.startswith("/me"):
            ra = client.get(f"{BASE}{path}", headers=org.hr).json()["items"]
            assert ra and {x["organisation_id"] for x in ra} == {org.id}
            continue
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", org.token(who), other_org.token(who))
    report_a = client.get(f"{BASE}/reports/joinings-and-exits?from=2020-01-01", headers=org.hr).json()
    assert report_a["headcount"] == 1 and report_a["recent_joinings"][0]["employee_id"] == e_a["id"]
    # reads across organisations are 404
    b = other_org
    for path, who in (
        (f"/employees/{e_a['id']}", "hr"),
        (f"/employees/{e_a['id']}/salary", "hr"),
        (f"/employees/{e_a['id']}/service-records", "hr"),
        (f"/payroll-runs/{run_a['id']}", "hr"),
        (f"/payroll-runs/{run_a['id']}/payslips", "hr"),
        (f"/appraisals/{appraisal_a['id']}", "hr"),
    ):
        assert client.get(f"{BASE}{path}", headers=b.headers[who]).status_code == 404, path
    # writes across organisations are 404 and change nothing
    attempts = [
        (
            "put",
            f"/employees/{e_a['id']}",
            {"employee_code": "X", "name": "x", "joined_on": "2024-01-01", "employment_type": "permanent"},
            "hr",
        ),
        ("post", f"/employees/{e_a['id']}/exit", {"kind": "termination", "last_working_day": "2026-10-28"}, "hr"),
        (
            "put",
            f"/employees/{e_a['id']}/salary",
            {"effective_from": "2026-11-01", "lines": [{"code": "B", "kind": "earning", "amount": "1"}]},
            "hr",
        ),
        (
            "post",
            f"/employees/{e_a['id']}/service-records",
            {"kind": "award", "effective_on": "2026-10-01", "title": "x"},
            "hr",
        ),
        ("put", f"/leave-types/{t_a['id']}", {"code": "Z", "name": "z", "days_per_year": 1}, "hr"),
        ("post", f"/leave-requests/{req_a['id']}/decision", {"decision": "rejected"}, "hr"),
        ("post", f"/leave-requests/{req_a['id']}/cancel", None, "faculty"),
        ("post", "/leave-requests", {"leave_type_id": t_a["id"], "from": "2026-11-20", "to": "2026-11-20"}, "faculty"),
        ("post", f"/payroll-runs/{run_a['id']}/mark-paid", {"paid_on": "2026-10-28"}, "finance"),
        ("put", f"/appraisals/{appraisal_a['id']}", {"rating": 1}, "manager"),
        ("post", "/appraisals", {"cycle": "x", "employee_ids": [e_a["id"]]}, "hr"),
    ]
    for method, path, body, who in attempts:
        r = getattr(client, method)(f"{BASE}{path}", json=body, headers=b.headers[who])
        assert r.status_code == 404, (path, r.status_code, r.text)
    assert client.get(f"{BASE}/employees/{e_a['id']}", headers=org.hr).json()["status"] == "active"
    assert client.get(f"{BASE}/payroll-runs/{run_a['id']}", headers=org.hr).json()["status"] == "approved"
    assert client.get(f"{BASE}/leave-requests?status=pending", headers=org.hr).json()["pending_total"] == 1


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


def test_the_migration_applies_the_tenant_policy_to_every_table():
    text = next((MODULE / "db" / "migrations" / "versions").glob("*_0001_initial.py")).read_text(encoding="utf-8")
    for t in TABLES:
        assert f'_enable_rls("{t.name}")' in text, t.name


def _contract(name: str) -> dict:
    return yaml.safe_load((MODULE / "contracts" / name).read_text(encoding="utf-8"))


def test_permission_keys_match_the_catalogue():
    assert set(PERMISSION_KEYS) == {p["key"] for p in _contract("permissions.yaml")["permissions"]}


@pytest.mark.parametrize(
    "role",
    [
        r["name"]
        for r in yaml.safe_load(
            (Path(__file__).resolve().parents[2] / "contracts" / "permissions.yaml").read_text(encoding="utf-8")
        )["roles"]
    ],
)
def test_every_role_in_the_catalogue_uses_known_keys(role):
    roles = {r["name"]: r["grants"] for r in _contract("permissions.yaml")["roles"]}
    assert set(roles[role]) <= set(PERMISSION_KEYS)


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
        for name in ("employee_id", "leave_type_id", "request_id", "run_id", "appraisal_id"):
            path = path.replace("{" + name + "}", "{id}")
        perms = next(d.call.permissions for d in route.dependant.dependencies if hasattr(d.call, "permissions"))
        for m in route.methods:
            served[(m, path)] = perms
    assert set(served) == set(contract)
    for key, perms in served.items():
        assert perms and all(perm in contract[key] for perm in perms), (key, perms)


def test_every_error_code_the_backend_raises_is_in_the_contract():
    """Reviewers read the contract for the codes a client must handle; a new code must be documented with it."""
    src = MODULE / "backend" / "src" / "eos_hr_payroll"
    code = "\n".join(p.read_text(encoding="utf-8") for p in (src / "application").glob("*.py"))
    domain = (src / "domain" / "rules.py").read_text(encoding="utf-8")
    codes = set(re.findall(r'(?:invalid|conflict)\(\s*"([a-z_]+)"', code))
    codes |= set(re.findall(r'HrPayrollError\(\s*\d+,\s*"([a-z_]+)"', code))
    codes |= set(re.findall(r'duplicate_is_409\(\s*"([a-z_]+)"', code))
    codes |= set(re.findall(r'RuleError\(\s*"([a-z_]+)"', domain))
    assert len(codes) > 50  # the patterns still find the codes
    contract = (MODULE / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
    assert sorted(c for c in codes if f"`{c}`" not in contract) == []


def test_enums_match_the_contract():
    schemas = _contract("openapi.yaml")["components"]["schemas"]
    assert list(rules.EMPLOYEE_STATUSES) == schemas["EmployeeStatus"]["enum"]
    assert list(rules.LEAVE_STATUSES) == schemas["LeaveStatus"]["enum"]
    assert list(rules.PAYROLL_RUN_STATUSES) == schemas["PayrollRun"]["properties"]["status"]["enum"]
    assert list(rules.EMPLOYMENT_TYPES) == schemas["EmployeeInput"]["properties"]["employment_type"]["enum"]
    assert list(rules.STAFF_CATEGORIES) == schemas["EmployeeInput"]["properties"]["staff_category"]["enum"]
    assert list(rules.EXIT_KINDS) == schemas["ExitInput"]["properties"]["kind"]["enum"]
    assert list(rules.SERVICE_RECORD_KINDS) == schemas["ServiceRecordInput"]["properties"]["kind"]["enum"]
    assert list(rules.PAY_LINE_KINDS) == schemas["PayLine"]["properties"]["kind"]["enum"]
    assert list(rules.HALF_DAYS) == schemas["LeaveRequestInput"]["properties"]["half_day"]["enum"]
    assert list(rules.APPRAISAL_STATUSES) == schemas["Appraisal"]["allOf"][1]["properties"]["status"]["enum"]


def test_published_events_carry_exactly_the_payload_of_events_yaml(client, org, monkeypatch):
    """Every hr-payroll.* event in the outbox, after a full run, has the keys events.yaml declares: identity,
    notification and budget-grants read these payloads. None carries an amount of an individual's pay."""
    declared = {e["name"]: set(e["payload"]) for e in _contract("events.yaml")["events"]}
    e, t, req, run, appraisal = seed(client, org)
    body = {k: e[k] for k in ("employee_code", "name", "joined_on", "employment_type")}
    client.put(f"{BASE}/employees/{e['id']}", json={**body, "designation": "Professor"}, headers=org.hr)
    decide(client, org, req["id"])
    client.post(f"{BASE}/leave-requests/{req['id']}/cancel", headers=org.faculty)
    other = apply(client, org, "faculty", t, "2026-11-10", "2026-11-10")
    assert other.status_code == 201, other.text
    other = other.json()
    decide(client, org, other["id"], "rejected")
    client.post(f"{BASE}/payroll-runs/{run['id']}/mark-paid", json={"paid_on": "2026-10-28"}, headers=org.finance)
    url = f"{BASE}/appraisals/{appraisal['id']}"
    client.put(url, json={"self_review": "fine", "submit": True}, headers=org.faculty)
    client.put(url, json={"rating": 3, "submit": True}, headers=org.manager)
    # October is paid, so the exit is on its last day (an exit inside it is refused); it is recorded on 1 November
    monkeypatch.setattr(common, "clock", lambda: datetime(2026, 11, 1, 6, 0, tzinfo=UTC))
    r = client.post(
        f"{BASE}/employees/{e['id']}/exit",
        json={"kind": "resignation", "last_working_day": "2026-10-31"},
        headers=org.hr,
    )
    assert r.status_code == 200, r.text
    with SessionLocal() as db, platform_scope():
        published = list(db.scalars(select(OutboxEvent).where(OutboxEvent.organisation_id == org.id)))
    names = {x.name for x in published}
    assert names == set(declared) - {"hr-payroll.job.finished"}
    for x in published:
        assert set(x.payload) == declared[x.name], (x.name, set(x.payload) ^ declared[x.name])
        assert not {"gross", "net", "lines", "amount", "salary"} & set(x.payload)


def test_the_scheduler_job_and_consumers_are_declared():
    assert set(jobs.JOBS) == {consumers.JOB}
    job = jobs.JOBS[consumers.JOB]
    assert job["scope"] == "platform" and job["idempotent"] is True and job["default_cron"]
    manifest = yaml.safe_load((MODULE / "module.yaml").read_text(encoding="utf-8"))
    assert set(consumers.CONSUMERS) == set(manifest["consumes_events"])
    pyproject = (MODULE / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    assert 'hr-payroll = "eos_hr_payroll.application.jobs:JOBS"' in pyproject
    assert 'hr-payroll = "eos_hr_payroll.application.consumers:CONSUMERS"' in pyproject


def test_every_state_change_is_audited_without_personal_values(client, org):
    e, t, req, run, appraisal = seed(client, org)
    with SessionLocal() as db, platform_scope():
        rows = list(db.scalars(select(AuditEntry).where(AuditEntry.organisation_id == org.id)))
    actions = {(r.action, r.actor) for r in rows}
    hr, finance, faculty = (org.ids[x] for x in ("hr", "finance", "faculty"))
    for expected in (
        ("employee.joined", hr),
        ("service_record.added", hr),
        ("salary.set", hr),
        ("leave_type.created", hr),
        ("leave_request.submitted", faculty),
        ("payroll_run.started", hr),
        ("payroll_run.submitted", hr),
        ("payroll_run.approved", finance),
        ("appraisal.opened", hr),
    ):
        assert expected in actions, expected
    assert {r.entity_id for r in rows if r.entity == "payroll_run"} == {run["id"]}
    columns = {c.name for c in AuditEntry.__table__.columns}
    assert columns == {"id", "organisation_id", "actor", "action", "entity", "entity_id", "occurred_at"}
