"""Item types API tests."""

from conftest import BASE

MANAGER = "portfolio-manager"
LEARNER = "portfolio-learner"


def test_create_and_list_item_type(client, org):
    _, mgr = org.user(MANAGER)
    res = client.post(
        f"{BASE}/item-types",
        json={
            "name": "Artwork",
            "description": "Visual arts items",
            "requires_review": True,
            "reviewer_person_ids": [],
        },
        headers=mgr,
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["name"] == "Artwork"
    assert data["organisation_id"] == org.id
    assert data["item_count"] == 0

    _, learner = org.user(LEARNER)
    res_list = client.get(f"{BASE}/item-types", headers=learner)
    assert res_list.status_code == 200
    types = res_list.json()
    assert any(t["id"] == data["id"] for t in types)


def test_conflict_on_duplicate_name(client, org):
    _, mgr = org.user(MANAGER)
    client.post(f"{BASE}/item-types", json={"name": "Sculpture"}, headers=mgr)
    res = client.post(f"{BASE}/item-types", json={"name": "Sculpture"}, headers=mgr)
    assert res.status_code == 409
    body = res.json()
    detail = body.get("detail", body)
    assert detail["code"] == "name_in_use"


def test_update_item_type(client, org):
    _, mgr = org.user(MANAGER)
    created = client.post(f"{BASE}/item-types", json={"name": "DraftType"}, headers=mgr).json()
    res = client.patch(
        f"{BASE}/item-types/{created['id']}",
        json={"name": "UpdatedType", "description": "New description"},
        headers=mgr,
    )
    assert res.status_code == 200
    assert res.json()["name"] == "UpdatedType"
    assert res.json()["description"] == "New description"


def test_delete_item_type_prevented_if_in_use(client, org):
    _, mgr = org.user(MANAGER)
    itype = client.post(f"{BASE}/item-types", json={"name": "Film"}, headers=mgr).json()

    # Create an item with this type
    client.post(
        f"{BASE}/items",
        json={"type_id": itype["id"], "title": "Short film"},
        headers=mgr,
    )

    # Deleting type should fail with 409
    del_res = client.delete(f"{BASE}/item-types/{itype['id']}", headers=mgr)
    assert del_res.status_code == 409
    body = del_res.json()
    detail = body.get("detail", body)
    assert detail["code"] == "type_in_use"
