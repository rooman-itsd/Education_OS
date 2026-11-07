"""Every route of the module is guarded by `require()` with the key the contract names, and a caller without it is refused
with 403 before anything is read or written. The expectations come from the roles' real grants
(contracts/permissions.yaml, through eos_core.permissions_for), so a change to a role or a key shows up here."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BASE,
    CONTROLLER,
    FACULTY,
    HEAD,
    STUDENT,
    VIEWER,
    all_outbox,
    assessment_body,
    audit_entries,
    cycle_body,
    grading_body,
    make_assessment,
    make_cycle,
    make_grading,
    ok,
    uid,
)
from eos_core.config import permissions_for  # noqa: E402
from eos_examinations.api.router import router  # noqa: E402

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _routes() -> list[tuple[str, str, frozenset[str]]]:
    found = []
    for route in router.routes:
        keys: set[str] = set()
        for dep in route.dependant.dependencies:
            keys |= set(getattr(dep.call, "permissions", ()))
        for method in sorted(route.methods):
            found.append((method, route.path, frozenset(keys)))
    return sorted(found, key=lambda r: (r[1], r[0]))


ROUTES = _routes()


def _call(client, method: str, path: str, headers: dict | None):
    url = BASE + "".join(uid() if part.startswith("{") else part for part in _split(path))
    kwargs = {"headers": headers or {}}
    if method in WRITE_METHODS and not path.endswith(("/activate", "/set-default")):
        kwargs["json"] = {}
    return client.request(method, url, **kwargs)


def _split(path: str) -> list[str]:
    """'/exam-cycles/{exam_cycle_id}/status' -> ['/exam-cycles/', '{exam_cycle_id}', '/status']"""
    parts, buf, depth = [], "", 0
    for ch in path:
        if ch == "{":
            if buf:
                parts.append(buf)
            buf, depth = "{", 1
        elif ch == "}" and depth:
            parts.append(buf + "}")
            buf, depth = "", 0
        else:
            buf += ch
    if buf:
        parts.append(buf)
    return parts


CONFIGURATION_ROUTES = {
    ("GET", "/grading-schemes"),
    ("POST", "/grading-schemes"),
    ("GET", "/grading-schemes/{grading_scheme_id}"),
    ("PUT", "/grading-schemes/{grading_scheme_id}"),
    ("POST", "/grading-schemes/{grading_scheme_id}/set-default"),
    ("GET", "/assessment-schemes"),
    ("POST", "/assessment-schemes"),
    ("GET", "/assessment-schemes/{assessment_scheme_id}"),
    ("PUT", "/assessment-schemes/{assessment_scheme_id}"),
    ("POST", "/assessment-schemes/{assessment_scheme_id}/activate"),
    ("GET", "/exam-cycles"),
    ("POST", "/exam-cycles"),
    ("GET", "/exam-cycles/{exam_cycle_id}"),
    ("PATCH", "/exam-cycles/{exam_cycle_id}"),
    ("POST", "/exam-cycles/{exam_cycle_id}/status"),
}


def test_every_route_of_the_module_is_guarded_by_at_least_one_key():
    assert CONFIGURATION_ROUTES <= {(m, p) for m, p, _ in ROUTES}  # the 15 configuration and exam-cycle operations
    for method, path, keys in ROUTES:
        assert keys, f"{method} {path} has no require() guard"


@pytest.mark.parametrize(("method", "path", "keys"), ROUTES, ids=[f"{m} {p}" for m, p, _ in ROUTES])
def test_no_token_is_401(client, method, path, keys):
    assert _call(client, method, path, None).status_code == 401


@pytest.mark.parametrize(("method", "path", "keys"), ROUTES, ids=[f"{m} {p}" for m, p, _ in ROUTES])
@pytest.mark.parametrize("role", [CONTROLLER, HEAD, FACULTY, VIEWER, STUDENT])
def test_a_role_is_refused_exactly_when_it_holds_none_of_the_routes_keys(client, org, role, method, path, keys):
    _, headers = org.user(role)
    response = _call(client, method, path, headers)
    allowed = bool(keys & permissions_for([role]))
    if allowed:
        assert response.status_code != 403, (role, method, path, response.text)
    else:
        assert response.status_code == 403, (role, method, path, response.status_code, response.text)
        assert response.json()["detail"]["code"] == "forbidden"
        assert response.json()["detail"]["message"].startswith("requires ")


def test_a_caller_without_a_role_holds_no_key_and_is_refused_everywhere(client, org):
    _, headers = org.user()
    for method, path, _ in ROUTES:
        assert _call(client, method, path, headers).status_code == 403, (method, path)


def test_read_keys_do_not_grant_writes_on_schemes_and_cycles(client, org, h):
    """The viewer and faculty roles read; neither may change a grading scheme, an assessment scheme or an exam cycle."""
    grading = make_grading(client, h)
    assessment = make_assessment(client, h)
    cycle = make_cycle(client, h, grading["id"])
    for role in (VIEWER, FACULTY, STUDENT):
        _, headers = org.user(role)
        for r in (
            client.post(f"{BASE}/grading-schemes", json=grading_body(), headers=headers),
            client.put(f"{BASE}/grading-schemes/{grading['id']}", json=grading_body("x"), headers=headers),
            client.post(f"{BASE}/grading-schemes/{grading['id']}/set-default", headers=headers),
            client.post(f"{BASE}/assessment-schemes", json=assessment_body(), headers=headers),
            client.put(f"{BASE}/assessment-schemes/{assessment['id']}", json=assessment_body(), headers=headers),
            client.post(f"{BASE}/assessment-schemes/{assessment['id']}/activate", headers=headers),
            client.post(f"{BASE}/exam-cycles", json=cycle_body(), headers=headers),
            client.patch(f"{BASE}/exam-cycles/{cycle['id']}", json={"name": "x"}, headers=headers),
            client.post(f"{BASE}/exam-cycles/{cycle['id']}/status", json={"status": "scheduled"}, headers=headers),
        ):
            assert r.status_code == 403, (role, r.request.method, r.request.url, r.status_code)
    # nothing changed: the refused writes reached no data, wrote no audit entry and published no event
    assert ok(client.get(f"{BASE}/exam-cycles/{cycle['id']}", headers=h))["status"] == "draft"
    assert ok(client.get(f"{BASE}/assessment-schemes/{assessment['id']}", headers=h))["status"] == "draft"
    assert [e.action for e in audit_entries(org.id)].count("exam_cycle.status_changed") == 0
    assert all_outbox(org.id) == ["examinations.exam-cycle.created"]


def test_the_department_head_writes_assessment_schemes_but_not_grading_schemes_or_cycles(client, org, h):
    _, head = org.user(HEAD)
    assert client.post(f"{BASE}/assessment-schemes", json=assessment_body(), headers=head).status_code == 201
    assert client.post(f"{BASE}/grading-schemes", json=grading_body(), headers=head).status_code == 403
    assert client.post(f"{BASE}/exam-cycles", json=cycle_body(), headers=head).status_code == 403
    assert client.get(f"{BASE}/grading-schemes", headers=head).status_code == 200  # grading-scheme:read


def test_a_permitted_caller_stays_inside_their_own_organisation(client, org, other_org, h):
    """A key grants the operation, never another organisation's data: the same permitted role gets 404, not the row."""
    theirs = make_grading(client, other_org.controller())
    mine = make_grading(client, h)
    assert client.get(f"{BASE}/grading-schemes/{theirs['id']}", headers=h).status_code == 404
    assert client.get(f"{BASE}/grading-schemes/{mine['id']}", headers=h).status_code == 200
    assert [s["id"] for s in ok(client.get(f"{BASE}/grading-schemes", headers=h))["items"]] == [mine["id"]]
