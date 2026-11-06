"""Which keys each role holds (eos_core.config.permissions_for, from contracts/permissions.yaml and the dashboard
layouts' module_roles), and that every endpoint refuses a caller without the key the contract names (403, nothing
changed). The academy roles are real profile roles whose layouts list this module's roles in `module_roles`."""

import pytest
from conftest import PERIOD, TODAY
from eos_core.config import permissions_for
from eos_field_training.infrastructure.models import new_id

P = "field-training:"
COORDINATOR = {
    f"{P}site:read",
    f"{P}site:manage",
    f"{P}opening:read",
    f"{P}opening:manage",
    f"{P}placement:read",
    f"{P}placement:manage",
}
SUPERVISOR = {f"{P}site:read", f"{P}supervision:read", f"{P}log:verify", f"{P}assessment:record"}
TRAINEE = {f"{P}self:read", f"{P}self:apply", f"{P}self:log"}
VIEWER = {f"{P}site:read", f"{P}opening:read", f"{P}placement:read"}


def keys(*roles: str) -> set[str]:
    return {p for p in permissions_for(list(roles)) if p.startswith(P)}


def test_module_roles_hold_exactly_their_grants():
    assert keys("field-training-coordinator") == COORDINATOR
    assert keys("field-training-supervisor") == SUPERVISOR
    assert keys("field-training-trainee") == TRAINEE
    assert keys("field-training-viewer") == VIEWER
    assert keys("student") == set() and keys("org-admin") == set() and keys("applicant") == set()


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("medical-student", TRAINEE),
        ("teacher-trainee", TRAINEE),
        ("hospital-coordinator", COORDINATOR),
        ("practicum-coordinator", COORDINATOR),
        ("clinical-supervisor", SUPERVISOR | VIEWER),
        ("mentor-teacher", SUPERVISOR),
    ],
)
def test_academy_roles_get_the_keys_their_layouts_list(role, expected):
    assert keys(role) == expected


def test_academy_role_tokens_work_end_to_end(prog):
    """A real profile-role token, not a module role: the medical-student layout gives field-training-trainee."""
    c = prog
    trainee_id, me = c.org.user("medical-student")
    p = c.ok(c.post(f"/openings/{c.opening['id']}/apply", {"statement": "Keen"}, me), 201)
    assert p["trainee_id"] == trainee_id
    c.ok(c.post(f"/placements/{p['id']}/decision", {"decision": "approved"}, c.coordinator))
    c.ok(c.post(f"/placements/{p['id']}/start", None, c.coordinator))
    c.ok(c.log(p, me), 201)
    assert [x["id"] for x in c.ok(c.get("/me/placements", me))] == [p["id"]]
    assert c.ok(c.get("/me/hours", me))["pending_hours"] == 4
    _, coordinator = c.org.user("hospital-coordinator")
    assert c.ok(c.get("/placements?status=active", coordinator))["items"][0]["id"] == p["id"]
    _, supervisor = c.org.user("clinical-supervisor")
    assert c.ok(c.get("/openings?status=open", supervisor))["items"]
    assert c.ok(c.get("/me/trainees", supervisor)) == []  # supervises nothing yet


def _calls(c, p: dict, log: dict) -> list[tuple[str, str, dict | None, set[str]]]:
    """(method, path, body, keys that may call it) for every operation in the contract."""
    pid, oid, sid, lid = p["id"], c.opening["id"], c.site["id"], log["id"]
    site = {"name": "x"}
    opening = {"site_id": sid, "title": "x", **PERIOD, "seats": 1}
    entry = {"date": TODAY, "hours": 1, "activities": "x"}
    reason = {"reason": "Because"}
    return [
        ("get", "/sites", None, {"site:read"}),
        ("post", "/sites", site, {"site:manage"}),
        ("get", f"/sites/{sid}", None, {"site:read"}),
        ("patch", f"/sites/{sid}", site, {"site:manage"}),
        ("get", "/openings", None, {"opening:read", "supervision:read", "self:apply"}),
        ("post", "/openings", opening, {"opening:manage"}),
        ("get", f"/openings/{oid}", None, {"opening:read", "supervision:read"}),
        ("patch", f"/openings/{oid}", opening, {"opening:manage"}),
        ("post", f"/openings/{oid}/publish", None, {"opening:manage"}),
        ("post", f"/openings/{oid}/close", None, {"opening:manage"}),
        ("post", f"/openings/{oid}/cancel", reason, {"opening:manage"}),
        ("post", f"/openings/{oid}/apply", None, {"self:apply"}),
        ("get", "/placements", None, {"placement:read", "supervision:read"}),
        ("post", "/placements", {"opening_id": oid, "trainee_id": new_id()}, {"placement:manage"}),
        ("get", f"/placements/{pid}", None, {"placement:read", "supervision:read", "self:read"}),
        ("patch", f"/placements/{pid}", {}, {"placement:manage"}),
        ("post", f"/placements/{pid}/decision", {"decision": "approved"}, {"placement:manage"}),
        ("post", f"/placements/{pid}/start", None, {"placement:manage"}),
        ("post", f"/placements/{pid}/complete", None, {"placement:manage"}),
        ("post", f"/placements/{pid}/withdraw", reason, {"placement:manage", "self:apply"}),
        ("get", f"/placements/{pid}/logs", None, {"placement:read", "supervision:read", "self:read"}),
        ("post", f"/placements/{pid}/logs", entry, {"self:log"}),
        ("patch", f"/logs/{lid}", entry, {"self:log"}),
        ("post", f"/logs/{lid}/verify", None, {"log:verify"}),
        ("post", f"/logs/{lid}/return", reason, {"log:verify"}),
        ("get", f"/placements/{pid}/assessments", None, {"placement:read", "supervision:read", "self:read"}),
        ("post", f"/placements/{pid}/assessments", {"stage": "mid", "outcome": "x"}, {"assessment:record"}),
        ("get", "/me/placements", None, {"self:read"}),
        ("get", "/me/hours", None, {"self:read"}),
        ("get", "/me/trainees", None, {"supervision:read"}),
    ]


def test_every_operation_refuses_a_caller_without_its_key(prog, client):
    c = prog
    _, me, p = c.active()
    log = c.ok(c.log(p, me), 201)
    calls = _calls(c, p, log)
    assert len(calls) == 30
    _, nobody = c.org.user("student")
    for role in (
        "field-training-coordinator",
        "field-training-supervisor",
        "field-training-trainee",
        "field-training-viewer",
        "student",
    ):
        held = {k.removeprefix(P) for k in keys(role)}
        _, headers = c.org.user(role)
        for method, path, body, allowed in calls:
            if held & allowed:
                continue
            kwargs = {"json": body} if body is not None else {}
            r = getattr(client, method)(f"/api/v1/field-training{path}", headers=headers, **kwargs)
            assert r.status_code == 403, (role, method, path, r.status_code)
    # Nothing changed.
    assert c.ok(c.get(f"/placements/{p['id']}", c.coordinator))["status"] == "active"
    assert c.ok(c.get(f"/openings/{c.opening['id']}", c.coordinator))["status"] == "open"
    assert c.ok(c.get(f"/placements/{p['id']}/logs", c.coordinator))[0]["status"] == "submitted"
    assert client.get("/api/v1/field-training/sites").status_code == 401
    assert c.get("/sites", nobody).status_code == 403
