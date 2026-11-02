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


def test_managed_scope_filters_in_query_before_pagination(client, org):
    _, mgr = org.user(MANAGER)
    rev_id, reviewer_headers = org.user(REVIEWER)
    other_rev_id, unassigned_rev = org.user(REVIEWER)
    _, learner = org.user(LEARNER)

    # 1. Type not assigned to rev_id
    type_other = client.post(
        f"{BASE}/item-types",
        json={"name": "Type Other", "requires_review": True, "reviewer_person_ids": [other_rev_id]},
        headers=mgr,
    ).json()

    # 2. Type assigned to rev_id
    type_mine = client.post(
        f"{BASE}/item-types",
        json={"name": "Type Mine", "requires_review": True, "reviewer_person_ids": [rev_id]},
        headers=mgr,
    ).json()

    # 3. Create 5 items of type_other submitted by learner
    for i in range(5):
        it = client.post(
            f"{BASE}/items",
            json={"type_id": type_other["id"], "title": f"Other Item {i}"},
            headers=learner,
        ).json()
        client.post(f"{BASE}/items/{it['id']}/submit", headers=learner)

    # 4. Create 1 item of type_mine submitted by learner
    assigned_item = client.post(
        f"{BASE}/items",
        json={"type_id": type_mine["id"], "title": "My Assigned Item"},
        headers=learner,
    ).json()
    client.post(f"{BASE}/items/{assigned_item['id']}/submit", headers=learner)

    # 5. Query managed scope with page_size=2 (< 5 items)
    res = client.get(
        f"{BASE}/items?scope=managed&page_size=2",
        headers=reviewer_headers,
    )
    assert res.status_code == 200
    data = res.json()
    # Total must be exactly 1 (not 6!), and items must contain the assigned item on page 1
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == assigned_item["id"]

    # 6. A third reviewer with no assignments gets total 0
    _, unassigned_rev3 = org.user(REVIEWER)
    res_none = client.get(
        f"{BASE}/items?scope=managed",
        headers=unassigned_rev3,
    )
    assert res_none.status_code == 200
    assert res_none.json()["total"] == 0
    assert res_none.json()["items"] == []


def test_self_review_refused(client, org):
    _, mgr = org.user(MANAGER)
    dual_id, dual_headers = org.user(LEARNER, REVIEWER)

    # 1. Create type with dual_id as designated reviewer
    itype = client.post(
        f"{BASE}/item-types",
        json={"name": "Peer Review Type", "requires_review": True, "reviewer_person_ids": [dual_id]},
        headers=mgr,
    ).json()

    # 2. Dual role user creates and submits own item
    own_item = client.post(
        f"{BASE}/items",
        json={"type_id": itype["id"], "title": "Reviewer's Own Item"},
        headers=dual_headers,
    ).json()
    own_id = own_item["id"]
    client.post(f"{BASE}/items/{own_id}/submit", headers=dual_headers)

    # Allowed actions must not include review for owner
    item_fetched = client.get(f"{BASE}/items/{own_id}", headers=dual_headers).json()
    assert "review" not in item_fetched["can"]

    # Reviewer attempts to review own item -> 403 Forbidden with self_review
    res = client.post(
        f"{BASE}/items/{own_id}/reviews",
        json={"decision": "approved", "comments": "Self approval attempt"},
        headers=dual_headers,
    )
    assert res.status_code == 403
    body = res.json()
    detail = body.get("detail", body)
    assert detail["code"] == "self_review"

    # 3. Manager creates and submits own item
    mgr_item = client.post(
        f"{BASE}/items",
        json={"type_id": itype["id"], "title": "Manager's Own Item"},
        headers=mgr,
    ).json()
    mgr_id = mgr_item["id"]
    client.post(f"{BASE}/items/{mgr_id}/submit", headers=mgr)

    # Manager allowed actions must not include review for their own item
    mgr_fetched = client.get(f"{BASE}/items/{mgr_id}", headers=mgr).json()
    assert "review" not in mgr_fetched["can"]

    # Manager attempts to review own item -> 403 Forbidden with self_review
    mgr_rev = client.post(
        f"{BASE}/items/{mgr_id}/reviews",
        json={"decision": "approved", "comments": "Manager self review"},
        headers=mgr,
    )
    assert mgr_rev.status_code == 403
    mgr_body = mgr_rev.json()
    mgr_detail = mgr_body.get("detail", mgr_body)
    assert mgr_detail["code"] == "self_review"
