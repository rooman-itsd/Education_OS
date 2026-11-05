"""Cross-tenant leak test (module standard rule 11): one organisation never sees another's rows."""

from conftest import BASE, COORDINATOR, LEAD, MEMBER, days, make_production
from eos_testing import assert_no_cross_tenant_leak


def seed(client, org) -> dict:
    """One organisation with a scheduled production, a part somebody holds and a preparation task."""
    user_id, coordinator = org.user(COORDINATOR, LEAD)
    production = make_production(client, coordinator, starts_at=days(10), ends_at=days(10.2))
    role = client.post(
        f"{BASE}/productions/{production['id']}/roles",
        json={"user_id": user_id, "role_name": "Viola"},
        headers=coordinator,
    ).json()
    # A second production, still in planning, so the in-preparation widget has a row for this tenant too.
    planned = make_production(client, coordinator, title="Next season")
    task = client.post(
        f"{BASE}/productions/{planned['id']}/tasks", json={"title": "Hire lights"}, headers=coordinator
    ).json()
    return {
        "planned": planned,
        "token": coordinator["Authorization"].split(" ", 1)[1],
        "headers": coordinator,
        "user_id": user_id,
        "production": production,
        "role": role,
        "task": task,
    }


def test_no_cross_tenant_leak(client, org, other_org):
    a, b = seed(client, org), seed(client, other_org)
    for path in ("/productions", "/productions?status=scheduled"):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", a["token"], b["token"])

    # The widget rows carry no organisation_id, so their ids are compared directly.
    for path in ("/calendar", "/upcoming", "/my-roles", "/in-preparation"):
        ids_a = {
            row.get("id") or row.get("role_id")
            for row in client.get(f"{BASE}{path}", headers=a["headers"]).json()["items"]
        }
        ids_b = {
            row.get("id") or row.get("role_id")
            for row in client.get(f"{BASE}{path}", headers=b["headers"]).json()["items"]
        }
        assert ids_a and ids_b, path
        assert not (ids_a & ids_b), path


def test_one_organisation_cannot_reach_anothers_rows_by_id(client, org, other_org):
    a, b = seed(client, org), seed(client, other_org)
    pid, rid, tid = a["production"]["id"], a["role"]["id"], a["task"]["id"]
    them = b["headers"]

    assert client.get(f"{BASE}/productions/{pid}", headers=them).status_code == 404
    assert client.get(f"{BASE}/productions/{pid}/roles", headers=them).status_code == 404
    assert client.get(f"{BASE}/productions/{pid}/tasks", headers=them).status_code == 404
    assert client.patch(f"{BASE}/productions/{pid}", json={"title": "Taken"}, headers=them).status_code == 404
    assert client.post(f"{BASE}/productions/{pid}/cancel", json={}, headers=them).status_code == 404
    assert client.post(f"{BASE}/productions/{pid}/complete", headers=them).status_code == 404
    assert (
        client.post(
            f"{BASE}/productions/{pid}/schedule", json={"starts_at": days(2), "ends_at": days(3)}, headers=them
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{BASE}/productions/{pid}/roles", json={"user_id": "x", "role_name": "Viola"}, headers=them
        ).status_code
        == 404
    )
    assert client.post(f"{BASE}/productions/{pid}/tasks", json={"title": "Theirs"}, headers=them).status_code == 404
    assert client.request("DELETE", f"{BASE}/roles/{rid}", json={}, headers=them).status_code == 404
    assert client.post(f"{BASE}/tasks/{tid}/complete", headers=them).status_code == 404
    # And the production is untouched.
    assert client.get(f"{BASE}/productions/{pid}", headers=a["headers"]).json()["status"] == "scheduled"


def test_a_client_token_is_never_shared_across_organisations(client, org, other_org):
    _, one = org.user(COORDINATOR)
    _, two = other_org.user(COORDINATOR)
    body = {"title": "Same token", "kind": "other", "client_token": "t-1"}
    first = client.post(f"{BASE}/productions", json=body, headers=one)
    second = client.post(f"{BASE}/productions", json=body, headers=two)
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert second.json()["organisation_id"] == other_org.id


def test_a_part_in_another_organisation_cannot_be_answered(client, org, other_org):
    a = seed(client, org)
    _, outsider = other_org.user(MEMBER)
    r = client.post(f"{BASE}/roles/{a['role']['id']}/respond", json={"decision": "accept"}, headers=outsider)
    assert r.status_code == 404  # not 403: its existence is not confirmed to another tenant
