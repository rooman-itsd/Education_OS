"""Every operation answers 401 without a valid token and 403 to a caller whose roles hold none of the permissions the
contract names; callers that hold one get past the guard (whatever the request then says)."""

import pytest
from conftest import BASE
from eos_core.db import new_id

ALL = {"coordinator", "contributor", "viewer"}
COORDINATOR = {"coordinator"}
READ = {"coordinator", "viewer"}
FRAMEWORK_READ = ALL
SUBMIT = {"contributor"}

ID = "{id}"
UUID = new_id()
INPUTS = {
    "framework": {"code": "X", "name": "X"},
    "metric": {"code": "X", "title": "X", "kind": "qualitative"},
    "cycle": {"framework_id": UUID, "name": "X", "period_start": "2025-04-01", "period_end": "2026-03-31"},
    "assign": {"assignments": [{"metric_id": UUID, "owner_id": UUID, "due_on": "2026-12-01"}]},
    "evidence": {"title": "X", "kind": "link", "url": "https://example.edu"},
    "action": {"title": "X", "owner_id": UUID, "due_on": "2026-12-01"},
}

# (method, path as in the contract, body, roles that hold a permission the contract names)
OPERATIONS = [
    ("GET", "/frameworks", None, FRAMEWORK_READ),
    ("POST", "/frameworks", INPUTS["framework"], COORDINATOR),
    ("PATCH", "/frameworks/{id}", {"name": "X"}, COORDINATOR),
    ("GET", "/frameworks/{id}/metrics", None, FRAMEWORK_READ),
    ("POST", "/frameworks/{id}/metrics", INPUTS["metric"], COORDINATOR),
    ("PATCH", "/metrics/{id}", {"title": "X"}, COORDINATOR),
    ("GET", "/cycles", None, READ),
    ("POST", "/cycles", INPUTS["cycle"], COORDINATOR),
    ("GET", "/cycles/{id}", None, READ),
    ("PATCH", "/cycles/{id}", {"name": "X"}, COORDINATOR),
    ("POST", "/cycles/{id}/status", {"status": "collecting"}, COORDINATOR),
    ("POST", "/cycles/{id}/assignments", INPUTS["assign"], COORDINATOR),
    ("GET", "/responses", None, ALL),
    ("GET", "/responses/{id}", None, ALL),
    ("PUT", "/responses/{id}", {"narrative": "X"}, SUBMIT),
    ("POST", "/responses/{id}/submit", None, SUBMIT),
    ("POST", "/responses/{id}/review", {"decision": "accept"}, COORDINATOR),
    ("POST", "/responses/{id}/evidence", INPUTS["evidence"], SUBMIT),
    ("DELETE", "/responses/{id}/evidence/" + UUID, None, SUBMIT),
    ("GET", "/action-items", None, ALL),
    ("POST", "/action-items", INPUTS["action"], COORDINATOR),
    ("PATCH", "/action-items/{id}", {"status": "in_progress"}, {"coordinator", "contributor"}),
    ("GET", "/stats/action-items", None, READ),
]


def test_the_table_lists_every_operation_of_the_contract():
    from pathlib import Path

    import yaml

    spec = yaml.safe_load((Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml").read_text())
    declared = {
        (m.upper(), p)
        for p, item in spec["paths"].items()
        for m in item
        if m in {"get", "post", "put", "patch", "delete"}
    }
    listed = {(m, p.replace("/evidence/" + UUID, "/evidence/{evidence_id}")) for m, p, _, _ in OPERATIONS}
    assert listed == declared


@pytest.fixture
def callers(org):
    return {
        "coordinator": org.user("iqac-accreditation-coordinator")[1],
        "contributor": org.user("iqac-accreditation-contributor")[1],
        "viewer": org.user("iqac-accreditation-viewer")[1],
        "nobody": org.user("student")[1],  # a platform role that holds no key of this module
    }


def call(client, method: str, path: str, body, headers: dict | None):
    return client.request(method, BASE + path.replace(ID, UUID), json=body, headers=headers or {})


@pytest.mark.parametrize(
    ("method", "path", "body", "allowed"), OPERATIONS, ids=[f"{m} {p}" for m, p, _, _ in OPERATIONS]
)
def test_each_operation_checks_the_token_and_the_permission(client, callers, method, path, body, allowed):
    assert call(client, method, path, body, None).status_code == 401
    assert call(client, method, path, body, {"Authorization": "Bearer nope"}).status_code == 401
    assert call(client, method, path, body, {"Authorization": "Basic abc"}).status_code == 401
    for role, headers in callers.items():
        status = call(client, method, path, body, headers).status_code
        if role in allowed:
            assert status not in (401, 403), (role, status)
        else:
            assert status == 403, (role, status)


def test_a_token_without_an_organisation_is_refused(client):
    from eos_core.security import create_token

    token = create_token(user_id=new_id(), organisation_id=None, roles=["iqac-accreditation-coordinator"])
    r = client.get(f"{BASE}/frameworks", headers={"Authorization": f"Bearer {token}"})
    assert (r.status_code, r.json()["detail"]["code"]) == (403, "forbidden")


def test_a_refusal_names_the_code_and_the_missing_permission(client, callers):
    r = client.get(f"{BASE}/stats/action-items", headers=callers["contributor"])
    assert r.status_code == 403
    assert r.json()["detail"] == {"code": "forbidden", "message": "requires iqac-accreditation:stats:read"}
    r = client.get(f"{BASE}/stats/action-items")
    assert (r.status_code, r.json()["detail"]["code"]) == (401, "unauthenticated")
