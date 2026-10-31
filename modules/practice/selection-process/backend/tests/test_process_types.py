"""Process types test suite."""

from conftest import BASE

COORDINATOR = "selection-process-coordinator"
PANELIST = "selection-process-panelist"


def test_process_type_crud_and_conflicts(client, org):
    _, coord = org.user(COORDINATOR)
    _, panel = org.user(PANELIST)

    # Panelist can list but not create
    res = client.get(f"{BASE}/process-types", headers=panel)
    assert res.status_code == 200
    assert res.json() == []

    # Coordinator creates type
    create_res = client.post(
        f"{BASE}/process-types",
        json={"name": "Audition", "description": "Music & Drama auditions"},
        headers=coord,
    )
    assert create_res.status_code == 201
    ptype = create_res.json()
    assert ptype["name"] == "Audition"
    assert ptype["process_count"] == 0

    # Duplicate name raises 409
    dup_res = client.post(
        f"{BASE}/process-types",
        json={"name": "Audition"},
        headers=coord,
    )
    assert dup_res.status_code == 409

    # Update type
    patch_res = client.patch(
        f"{BASE}/process-types/{ptype['id']}",
        json={"name": "Audition Round 2026"},
        headers=coord,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Audition Round 2026"

    # Delete unused type
    del_res = client.delete(f"{BASE}/process-types/{ptype['id']}", headers=coord)
    assert del_res.status_code == 204

