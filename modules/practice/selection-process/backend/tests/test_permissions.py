"""Permissions gate tests."""

from conftest import BASE

COORDINATOR = "selection-process-coordinator"
PANELIST = "selection-process-panelist"


def test_permission_gates(client, org):
    _, coord = org.user(COORDINATOR)
    _, panel = org.user(PANELIST)
    _, unauth = org.user("unrelated-role")

    # Unauthenticated gets 401
    assert client.get(f"{BASE}/process-types").status_code == 401

    # Unauthorized gets 403
    assert client.get(f"{BASE}/process-types", headers=unauth).status_code == 403

    # Panelist can read types and processes, but cannot create
    assert client.get(f"{BASE}/process-types", headers=panel).status_code == 200
    fail_create = client.post(
        f"{BASE}/process-types",
        json={"name": "Forbidden Type"},
        headers=panel,
    )
    assert fail_create.status_code == 403

    # Coordinator can create
    ok_create = client.post(
        f"{BASE}/process-types",
        json={"name": "Permitted Type"},
        headers=coord,
    )
    assert ok_create.status_code == 201
