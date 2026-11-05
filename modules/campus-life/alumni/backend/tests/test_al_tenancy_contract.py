"""The cross-tenant leak test (GET /me/mentoring included, for a student id that exists in two organisations), reads and
writes across organisations, the Alembic chain against the models, drift between code and contract, event payloads
against events.yaml, and the audit trail."""

import re
import tempfile
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from al_support import BASE, NOW, Org, add_alumnus, alumnus_body, assigned, mentor, scheduled, session_body
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from eos_alumni.api.router import router
from eos_alumni.application import service
from eos_alumni.application.access import PERMISSION_KEYS
from eos_alumni.domain import rules
from eos_alumni.infrastructure.models import PREFIX, TABLES, AuditEntry
from eos_core.db import SessionLocal, new_id
from eos_core.events import OutboxEvent
from eos_core.tenant import platform_scope
from eos_testing import assert_no_cross_tenant_leak
from sqlalchemy import create_engine, inspect, select

MODULE = Path(__file__).resolve().parents[2]


def _contract(name: str) -> dict:
    return yaml.safe_load((MODULE / "contracts" / name).read_text(encoding="utf-8"))


def seed(client, org):
    """One of everything: an archived alumnus, a mentor with an active assignment for `student` and a session."""
    gone = add_alumnus(client, org, full_name="Archived")
    client.post(f"{BASE}/directory/{gone['id']}/archive", headers=org.coord)
    m = mentor(client, org)
    x = assigned(client, org, m)
    s = scheduled(client, org, x, NOW + timedelta(days=1))
    return m, x, s


def test_no_cross_tenant_leak(client):
    shared_student = new_id()
    a, b = Org(ids={"student": shared_student}), Org(ids={"student": shared_student})
    m_a, x_a, s_a = seed(client, a)
    m_b, x_b, s_b = seed(client, b)
    for path in (
        "/directory",
        "/directory?status=archived",
        "/mentoring/assignments",
        f"/mentoring/assignments?student_id={shared_student}",
    ):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", a.token("coord"), b.token("coord"))
    # the same student id in two organisations: each caller sees only their own organisation's assignment
    me_a = client.get(f"{BASE}/me/mentoring", headers=a.student).json()
    me_b = client.get(f"{BASE}/me/mentoring", headers=b.student).json()
    assert me_a["assignment"]["id"] == x_a["id"] and me_a["assignment"]["mentor"]["id"] == m_a["id"]
    assert me_b["assignment"]["id"] == x_b["id"] and me_b["assignment"]["mentor"]["id"] == m_b["id"]
    assert [s["id"] for s in me_a["upcoming_sessions"]] == [s_a["id"]]
    assert [s["id"] for s in me_b["upcoming_sessions"]] == [s_b["id"]]
    # ending B's assignment leaves A's student with their mentor, and the reverse
    client.post(f"{BASE}/mentoring/assignments/{x_b['id']}/end", headers=b.coord)
    assert client.get(f"{BASE}/me/mentoring", headers=b.student).json()["assignment"] is None
    assert client.get(f"{BASE}/me/mentoring", headers=a.student).json()["assignment"]["id"] == x_a["id"]
    # a student with an active mentor in A can be assigned in B too: one active mentor per organisation
    m_b2 = mentor(client, b)
    assert assigned(client, b, m_b2)["student_id"] == shared_student
    filtered = client.get(
        f"{BASE}/mentoring/assignments", params={"student_id": shared_student, "status": "active"}, headers=a.coord
    ).json()
    assert [x["id"] for x in filtered["items"]] == [x_a["id"]]
    # reads across organisations are 404
    for path in (
        f"/directory/{m_a['id']}",
        f"/mentoring/assignments/{x_a['id']}",
        f"/mentoring/assignments/{x_a['id']}/sessions",
    ):
        assert client.get(f"{BASE}{path}", headers=b.coord).status_code == 404, path
    # writes across organisations are 404 and change nothing
    attempts = [
        ("put", f"/directory/{m_a['id']}", alumnus_body(full_name="Stolen", is_mentor=False)),
        ("post", f"/directory/{m_a['id']}/archive", None),
        ("post", f"/directory/{m_a['id']}/restore", None),
        ("post", "/mentoring/assignments", {"mentor_id": m_a["id"], "student_id": b.ids["student2"]}),
        ("post", f"/mentoring/assignments/{x_a['id']}/end", None),
        ("post", f"/mentoring/assignments/{x_a['id']}/sessions", session_body(NOW)),
        ("put", f"/mentoring/sessions/{s_a['id']}", session_body(NOW + timedelta(days=4))),
        ("post", f"/mentoring/sessions/{s_a['id']}/complete", {"notes": "x"}),
        ("post", f"/mentoring/sessions/{s_a['id']}/cancel", None),
    ]
    for method, path, body in attempts:
        r = client.request(method.upper(), f"{BASE}{path}", json=body, headers=b.coord)
        assert r.status_code == 404 and r.json()["detail"]["code"] == "not_found", (path, r.text)
    assert client.get(f"{BASE}/directory/{m_a['id']}", headers=a.coord).json() == {**m_a, "active_mentees": 1}
    got = client.get(f"{BASE}/mentoring/assignments/{x_a['id']}", headers=a.coord).json()
    assert got["status"] == "active" and got["next_session_at"] == s_a["scheduled_at"]
    sessions = client.get(f"{BASE}/mentoring/assignments/{x_a['id']}/sessions", headers=a.coord).json()
    assert [(s["id"], s["status"]) for s in sessions] == [(s_a["id"], "scheduled")]


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
        partial = {i["name"]: i for i in insp.get_indexes("alumni_mentoring_assignment")}
        assert partial["uq_alumni_assignment_active_student"]["unique"]
        assert partial["uq_alumni_assignment_active_student"]["column_names"] == ["organisation_id", "student_id"]
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


def test_permission_keys_match_the_catalogue():
    assert set(PERMISSION_KEYS) == {p["key"] for p in _contract("permissions.yaml")["permissions"]}


def test_every_contract_operation_is_served_with_its_permission_and_status():
    openapi = _contract("openapi.yaml")
    contract = {}
    for path, ops in openapi["paths"].items():
        for method, op in ops.items():
            if method in ("get", "post", "put", "delete", "patch"):
                contract[(method.upper(), path)] = op
    served = {}
    for route in router.routes:
        path = route.path
        for name in ("alumnus_id", "assignment_id", "session_id"):
            path = path.replace("{" + name + "}", "{id}")
        perms = next(d.call.permissions for d in route.dependant.dependencies if hasattr(d.call, "permissions"))
        for m in route.methods:
            served[(m, path)] = (perms, route.status_code or 200)
    assert set(served) == set(contract)
    for key, (perms, status) in served.items():
        op = contract[key]
        named = re.findall(r"Permission (alumni:[a-z-]+:[a-z-]+)", op["summary"])
        assert list(perms) == named, (key, perms, named)
        success = [int(c) for c in op["responses"] if str(c).startswith("2")]
        assert success == [status], (key, success, status)


def test_every_error_code_the_backend_raises_is_in_the_contract():
    """Reviewers read the contract for the codes a client must handle; a new code must be documented with it."""
    src = MODULE / "backend" / "src" / "eos_alumni"
    code = "\n".join((src / part).read_text(encoding="utf-8") for part in ("application/service.py", "domain/rules.py"))
    codes = set(re.findall(r'conflict\(\s*"([a-z_]+)"', code))
    codes |= set(re.findall(r'AlumniError\(\s*\d+,\s*"([a-z_]+)"', code))
    codes |= set(re.findall(r'RuleError\(\s*"([a-z_]+)"', code))
    expected = {
        "invalid_cursor",
        "alumnus_archived",
        "not_archived",
        "not_a_mentor",
        "mentor_has_active_assignments",
        "student_already_assigned",
        "assignment_not_active",
        "session_not_scheduled",
        "invalid_name",
        "invalid_graduation_year",
        "invalid_email",
        "invalid_phone",
        "invalid_url",
        "invalid_date",
        "invalid_scheduled_at",
        "invalid_duration",
    }
    assert codes == expected  # the patterns find every code, and the backend raises every documented one
    contract = (MODULE / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
    assert sorted(c for c in codes | {"not_found", "forbidden"} if f"`{c}`" not in contract) == []


def test_enums_match_the_contract():
    schemas = _contract("openapi.yaml")["components"]["schemas"]
    assert list(rules.ALUMNUS_STATUSES) == schemas["AlumnusStatus"]["enum"]
    assert list(rules.ASSIGNMENT_STATUSES) == schemas["AssignmentStatus"]["enum"]
    assert list(rules.SESSION_STATUSES) == schemas["SessionStatus"]["enum"]
    assert list(rules.SESSION_MODES) == schemas["SessionMode"]["enum"]
    assert service.MY_UPCOMING == schemas["MyMentoring"]["properties"]["upcoming_sessions"]["maxItems"]


def _shape(schemas: dict, name: str) -> tuple[set[str], set[str]]:
    """(properties, required) of a schema, allOf resolved."""
    schema = schemas[name]
    props, required = set(schema.get("properties", {})), set(schema.get("required", []))
    for part in schema.get("allOf", []):
        if "$ref" in part:
            p, r = _shape(schemas, part["$ref"].rsplit("/", 1)[-1])
        else:
            p, r = set(part.get("properties", {})), set(part.get("required", []))
        props, required = props | p, required | r
    return props, required


def _check(schemas: dict, name: str, body: dict) -> None:
    props, required = _shape(schemas, name)
    assert set(body) == props, (name, set(body) ^ props)
    assert all(body[k] is not None for k in required), (name, [k for k in required if body[k] is None])


def test_responses_have_exactly_the_contract_properties(client, org):
    schemas = _contract("openapi.yaml")["components"]["schemas"]
    m = mentor(client, org)
    x = assigned(client, org, m)
    s = scheduled(client, org, x, NOW + timedelta(days=1))
    _check(schemas, "Alumnus", m)
    _check(schemas, "Assignment", x)
    _check(schemas, "MentorCard", x["mentor"])
    _check(schemas, "Session", s)
    for page, item in (("/directory", "Alumnus"), ("/mentoring/assignments", "Assignment")):
        body = client.get(f"{BASE}{page}", headers=org.coord).json()
        assert set(body) == set(schemas[f"{item}Page"]["properties"])
        _check(schemas, item, body["items"][0])
    me = client.get(f"{BASE}/me/mentoring", headers=org.student).json()
    assert set(me) == set(schemas["MyMentoring"]["properties"])
    mine = schemas["MyMentoring"]["properties"]["assignment"]
    assert set(me["assignment"]) == set(mine["properties"])
    _check(schemas, "MentorCard", me["assignment"]["mentor"])
    _check(schemas, "MySession", me["upcoming_sessions"][0])


TYPES = {
    "uuid": lambda v: isinstance(v, str) and str(uuid.UUID(v)) == v,
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "string": lambda v: isinstance(v, str),
    "date": lambda v: isinstance(v, str) and date.fromisoformat(v).isoformat() == v,
    "datetime": lambda v: isinstance(v, str) and datetime.fromisoformat(v).utcoffset() == timedelta(0),
}


def test_published_events_carry_exactly_the_payload_of_events_yaml(client, org):
    """Every alumni.* event in the outbox, after a run through every operation, has the keys and types events.yaml
    declares and nothing else; notification may read these payloads later."""
    declared = {e["name"]: e["payload"] for e in _contract("events.yaml")["events"]}
    a = add_alumnus(client, org)
    client.post(f"{BASE}/directory/{a['id']}/archive", headers=org.coord)
    client.post(f"{BASE}/directory/{a['id']}/restore", headers=org.coord)
    x = assigned(client, org)
    s1 = scheduled(client, org, x, NOW + timedelta(days=1))
    client.put(f"{BASE}/mentoring/sessions/{s1['id']}", json=session_body(NOW + timedelta(days=2)), headers=org.coord)
    client.post(f"{BASE}/mentoring/sessions/{s1['id']}/complete", headers=org.coord)
    s2 = scheduled(client, org, x, NOW + timedelta(days=3))
    client.post(f"{BASE}/mentoring/sessions/{s2['id']}/cancel", headers=org.coord)
    scheduled(client, org, x, NOW + timedelta(days=4))
    client.post(f"{BASE}/mentoring/assignments/{x['id']}/end", headers=org.coord)
    with SessionLocal() as db, platform_scope():
        published = list(db.scalars(select(OutboxEvent).where(OutboxEvent.organisation_id == org.id)))
    assert {e.name for e in published} == set(declared)
    for e in published:
        assert set(e.payload) == set(declared[e.name]), (e.name, set(e.payload) ^ set(declared[e.name]))
        for key, kind in declared[e.name].items():
            assert TYPES[kind](e.payload[key]), (e.name, key, e.payload[key])
        assert e.payload["organisation_id"] == org.id and e.actor == org.ids["coord"]


def test_every_state_change_is_audited(client, org):
    a = add_alumnus(client, org, is_mentor=True)
    client.put(f"{BASE}/directory/{a['id']}", json=alumnus_body(is_mentor=True), headers=org.coord)
    x = assigned(client, org, a)
    s1 = scheduled(client, org, x, NOW + timedelta(days=1))
    client.put(f"{BASE}/mentoring/sessions/{s1['id']}", json=session_body(NOW + timedelta(days=1)), headers=org.coord)
    client.put(f"{BASE}/mentoring/sessions/{s1['id']}", json=session_body(NOW + timedelta(days=2)), headers=org.coord)
    client.post(f"{BASE}/mentoring/sessions/{s1['id']}/complete", headers=org.coord)
    s2 = scheduled(client, org, x, NOW + timedelta(days=3))
    client.post(f"{BASE}/mentoring/sessions/{s2['id']}/cancel", headers=org.coord)
    client.post(f"{BASE}/mentoring/assignments/{x['id']}/end", headers=org.coord)
    client.post(f"{BASE}/directory/{a['id']}/archive", headers=org.coord)
    client.post(f"{BASE}/directory/{a['id']}/restore", headers=org.coord)
    with SessionLocal() as db, platform_scope():
        rows = list(db.scalars(select(AuditEntry).where(AuditEntry.organisation_id == org.id)))
    actions = [(r.action, r.entity_id) for r in rows]
    assert {r.actor for r in rows} == {org.ids["coord"]}
    for expected in (
        ("alumnus.added", a["id"]),
        ("alumnus.updated", a["id"]),
        ("alumnus.archived", a["id"]),
        ("alumnus.restored", a["id"]),
        ("assignment.started", x["id"]),
        ("assignment.ended", x["id"]),
        ("session.scheduled", s1["id"]),
        ("session.updated", s1["id"]),
        ("session.rescheduled", s1["id"]),
        ("session.completed", s1["id"]),
        ("session.cancelled", s2["id"]),
    ):
        assert expected in actions, expected


def test_notes_and_contact_details_never_reach_events_or_the_audit_trail(client, org):
    m = mentor(client, org, notes="SECRET-ALUMNUS-NOTE")
    x = assigned(client, org, m, student_name="SECRET-STUDENT-NAME", focus="SECRET-FOCUS")
    s = scheduled(client, org, x, NOW + timedelta(days=1), topic="SECRET-TOPIC", location="SECRET-ROOM")
    client.post(f"{BASE}/mentoring/sessions/{s['id']}/complete", json={"notes": "SECRET-SESSION"}, headers=org.coord)
    s2 = scheduled(client, org, x, NOW + timedelta(days=2))
    client.post(f"{BASE}/mentoring/sessions/{s2['id']}/cancel", json={"reason": "SECRET-REASON"}, headers=org.coord)
    client.post(f"{BASE}/mentoring/assignments/{x['id']}/end", json={"reason": "SECRET-END"}, headers=org.coord)
    with SessionLocal() as db, platform_scope():
        audit = [(r.action, r.entity, r.entity_id) for r in db.scalars(select(AuditEntry))]
        payloads = [e.payload for e in db.scalars(select(OutboxEvent).where(OutboxEvent.organisation_id == org.id))]
    text = str(audit) + str(payloads)
    for secret in ("SECRET", m["email"], m["phone"], m["full_name"]):
        assert secret not in text, secret


@pytest.mark.parametrize(
    "role", [r["name"] for r in yaml.safe_load((MODULE / "contracts" / "permissions.yaml").read_text())["roles"]]
)
def test_every_role_in_the_catalogue_uses_known_keys(role):
    roles = {r["name"]: r["grants"] for r in _contract("permissions.yaml")["roles"]}
    assert set(roles[role]) <= set(PERMISSION_KEYS)


def test_the_management_layouts_hold_the_module_roles():
    """placement-officer runs the module (A4); management-student holds only alumni:self:read (A5)."""
    from eos_core.config import permissions_for

    officer = {k for k in permissions_for(["placement-officer"]) if k.startswith("alumni:")}
    student = {k for k in permissions_for(["management-student"]) if k.startswith("alumni:")}
    assert officer == set(PERMISSION_KEYS) - {"alumni:self:read"}
    assert student == {"alumni:self:read"}


def test_business_today_follows_the_clock():
    assert service.business_today() == NOW.date()
