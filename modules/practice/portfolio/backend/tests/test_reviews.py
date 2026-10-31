"""Review lifecycle and reviewer authorization tests."""

from conftest import BASE

MANAGER = "portfolio-manager"
LEARNER = "portfolio-learner"
REVIEWER = "portfolio-reviewer"


def test_review_lifecycle(client, org):
    _, mgr = org.user(MANAGER)
    rev_id, reviewer_headers = org.user(REVIEWER)
    _, unassigned_rev = org.user(REVIEWER)

    # 1. Create type with designated reviewer
    itype = client.post(
        f"{BASE}/item-types",
        json={"name": "Sculpture Project", "requires_review": True, "reviewer_person_ids": [rev_id]},
        headers=mgr,
    ).json()

    # 2. Learner creates & submits item
    _, learner = org.user(LEARNER)
    item = client.post(
        f"{BASE}/items",
        json={"type_id": itype["id"], "title": "Bronze Figure"},
        headers=learner,
    ).json()
    item_id = item["id"]

    # Trying to review a draft fails with 409
    bad_rev = client.post(
        f"{BASE}/items/{item_id}/reviews",
        json={"decision": "approved", "comments": "Premature"},
        headers=reviewer_headers,
    )
    assert bad_rev.status_code == 409
    body = bad_rev.json()
    detail = body.get("detail", body)
    assert detail["code"] == "not_under_review"

    # Submit
    client.post(f"{BASE}/items/{item_id}/submit", headers=learner)

    # Unassigned reviewer tries to review -> 403
    unauth = client.post(
        f"{BASE}/items/{item_id}/reviews",
        json={"decision": "approved", "comments": "Not allowed"},
        headers=unassigned_rev,
    )
    assert unauth.status_code == 403

    # Assigned reviewer requests changes
    rev_res = client.post(
        f"{BASE}/items/{item_id}/reviews",
        json={"decision": "changes_requested", "score": 6.5, "comments": "Add more angle views"},
        headers=reviewer_headers,
    )
    assert rev_res.status_code == 201
    rev_data = rev_res.json()
    assert rev_data["decision"] == "changes_requested"
    assert rev_data["score"] == 6.5

    # Check item status is changes_requested
    item_after = client.get(f"{BASE}/items/{item_id}", headers=learner).json()
    assert item_after["status"] == "changes_requested"
    assert "edit" in item_after["can"]
    assert "submit" in item_after["can"]

    # Learner edits and resubmits
    client.patch(
        f"{BASE}/items/{item_id}", json={"type_id": itype["id"], "title": "Bronze Figure - Final"}, headers=learner
    )
    client.post(f"{BASE}/items/{item_id}/submit", headers=learner)

    # Reviewer approves
    app_res = client.post(
        f"{BASE}/items/{item_id}/reviews",
        json={"decision": "approved", "score": 9.0, "comments": "Excellent improvement"},
        headers=reviewer_headers,
    )
    assert app_res.status_code == 201

    final_item = client.get(f"{BASE}/items/{item_id}", headers=learner).json()
    assert final_item["status"] == "approved"
    assert len(final_item["reviews"]) == 2
