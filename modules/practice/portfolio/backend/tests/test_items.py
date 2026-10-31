"""Items CRUD, media attachments, and submission lifecycle tests."""

from conftest import BASE

MANAGER = "portfolio-manager"
LEARNER = "portfolio-learner"


def _make_type(client, mgr, name: str = "Artwork", requires_review: bool = True, reviewers: list[str] | None = None):
    return client.post(
        f"{BASE}/item-types",
        json={
            "name": name,
            "description": "Desc",
            "requires_review": requires_review,
            "reviewer_person_ids": reviewers or [],
        },
        headers=mgr,
    ).json()


def test_item_crud_and_lifecycle(client, org):
    _, mgr = org.user(MANAGER)
    itype = _make_type(client, mgr, "Oil Painting")

    uid, learner = org.user(LEARNER)

    # 1. Create item
    res = client.post(
        f"{BASE}/items",
        json={
            "type_id": itype["id"],
            "title": "Sunset over hills",
            "description": "Oil on canvas 40x50",
            "tags": ["landscape", "oil"],
            "attributes": {"medium": "oil"},
        },
        headers=learner,
    )
    assert res.status_code == 201, res.text
    item = res.json()
    assert item["title"] == "Sunset over hills"
    assert item["status"] == "draft"
    assert item["owner_person_id"] == uid
    assert "edit" in item["can"]
    assert "submit" in item["can"]

    item_id = item["id"]

    # 2. Attach media
    m_res = client.post(
        f"{BASE}/items/{item_id}/media",
        json={"document_id": "doc-uuid-123", "caption": "Primary photo", "sort_order": 1},
        headers=learner,
    )
    assert m_res.status_code == 201
    media = m_res.json()
    assert media["document_id"] == "doc-uuid-123"

    # List media
    list_m = client.get(f"{BASE}/items/{item_id}/media", headers=learner)
    assert list_m.status_code == 200
    assert len(list_m.json()) == 1

    # 3. Edit item
    patch_res = client.patch(
        f"{BASE}/items/{item_id}",
        json={"type_id": itype["id"], "title": "Golden Sunset"},
        headers=learner,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Golden Sunset"

    # 4. Submit item
    sub_res = client.post(f"{BASE}/items/{item_id}/submit", headers=learner)
    assert sub_res.status_code == 200
    submitted = sub_res.json()
    assert submitted["status"] == "submitted"
    assert submitted["submitted_at"] is not None
    assert "withdraw" in submitted["can"]
    assert "edit" not in submitted["can"]

    # 5. Editing while submitted should return 409
    bad_edit = client.patch(
        f"{BASE}/items/{item_id}",
        json={"type_id": itype["id"], "title": "Illegal Edit"},
        headers=learner,
    )
    assert bad_edit.status_code == 409
    body = bad_edit.json()
    detail = body.get("detail", body)
    assert detail["code"] == "not_editable"

    # 6. Withdraw item back to draft
    w_res = client.post(f"{BASE}/items/{item_id}/withdraw", headers=learner)
    assert w_res.status_code == 200
    withdrawn = w_res.json()
    assert withdrawn["status"] == "draft"
    assert "edit" in withdrawn["can"]

    # 7. Resubmit
    resub_res = client.post(f"{BASE}/items/{item_id}/submit", headers=learner)
    assert resub_res.status_code == 200
    assert resub_res.json()["status"] == "submitted"


def test_type_without_review_approves_immediately(client, org):
    _, mgr = org.user(MANAGER)
    itype = _make_type(client, mgr, "Self-Study Note", requires_review=False)

    _, learner = org.user(LEARNER)
    item = client.post(
        f"{BASE}/items",
        json={"type_id": itype["id"], "title": "Weekly summary"},
        headers=learner,
    ).json()

    sub = client.post(f"{BASE}/items/{item['id']}/submit", headers=learner).json()
    assert sub["status"] == "approved"
    assert sub["decided_at"] is not None
