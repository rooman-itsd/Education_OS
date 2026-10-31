"""Candidate registration and withdrawal test suite."""

import uuid

from conftest import BASE

COORDINATOR = "selection-process-coordinator"
PANELIST = "selection-process-panelist"


def test_candidate_registration_and_duplicate_protection(client, org):
    _, coord = org.user(COORDINATOR)
    t = client.post(f"{BASE}/process-types", json={"name": "Drama Audition"}, headers=coord).json()

    # Create draft process with stages
    p = client.post(
        f"{BASE}/processes",
        json={
            "type_id": t["id"],
            "title": "Hamlet Casting",
            "stages": [
                {"name": "Monologue", "sequence": 1},
                {"name": "Callbacks", "sequence": 2},
            ],
        },
        headers=coord,
    ).json()

    actor_person_id = str(uuid.uuid4())

    # Cannot register candidate when process is still draft
    reg_draft = client.post(
        f"{BASE}/processes/{p['id']}/candidates",
        json={"person_id": actor_person_id},
        headers=coord,
    )
    assert reg_draft.status_code == 409
    body = reg_draft.json()
    detail = body.get("detail", body)
    assert detail["code"] == "process_not_open"

    # Open the process
    client.post(f"{BASE}/processes/{p['id']}/open", headers=coord)

    # Successfully register candidate
    reg_res = client.post(
        f"{BASE}/processes/{p['id']}/candidates",
        json={"person_id": actor_person_id},
        headers=coord,
    )
    assert reg_res.status_code == 201
    cand = reg_res.json()
    assert cand["status"] == "registered"
    assert cand["person_id"] == actor_person_id
    assert cand["current_stage_id"] is not None

    # Duplicate registration of the same person on the same process must return 409 Conflict
    dup_res = client.post(
        f"{BASE}/processes/{p['id']}/candidates",
        json={"person_id": actor_person_id},
        headers=coord,
    )
    assert dup_res.status_code == 409
    body = dup_res.json()
    detail = body.get("detail", body)
    assert detail["code"] == "duplicate_candidate"

    # Candidate can withdraw
    with_res = client.post(f"{BASE}/candidates/{cand['id']}/withdraw", headers=coord)
    assert with_res.status_code == 200
    assert with_res.json()["status"] == "withdrawn"

    # Cannot withdraw again after final outcome
    again = client.post(f"{BASE}/candidates/{cand['id']}/withdraw", headers=coord)
    assert again.status_code == 409
    body = again.json()
    detail = body.get("detail", body)
    assert detail["code"] == "candidate_finalized"


def test_candidate_listing_scopes(client, org):
    _, coord = org.user(COORDINATOR)
    t = client.post(f"{BASE}/process-types", json={"name": "Moot Court"}, headers=coord).json()

    p = client.post(
        f"{BASE}/processes",
        json={
            "type_id": t["id"],
            "title": "Moot Trials",
            "stages": [{"name": "Oral Submissions", "sequence": 1}],
        },
        headers=coord,
    ).json()
    client.post(f"{BASE}/processes/{p['id']}/open", headers=coord)

    cand1_uid, cand1_headers = org.user("selection-process-panelist")
    cand2_uid, _ = org.user("selection-process-panelist")

    # Register both
    client.post(f"{BASE}/processes/{p['id']}/candidates", json={"person_id": cand1_uid}, headers=coord)
    client.post(f"{BASE}/processes/{p['id']}/candidates", json={"person_id": cand2_uid}, headers=coord)

    # scope=mine for cand1
    mine_res = client.get(f"{BASE}/processes/{p['id']}/candidates?scope=mine", headers=cand1_headers)
    assert mine_res.status_code == 200
    mine_items = mine_res.json()["items"]
    assert len(mine_items) == 1
    assert mine_items[0]["person_id"] == cand1_uid

    # scope=managed for coordinator sees all
    all_res = client.get(f"{BASE}/processes/{p['id']}/candidates?scope=managed", headers=coord)
    assert all_res.status_code == 200
    assert len(all_res.json()["items"]) == 2


def test_candidate_access_and_decision_privacy(client, org):
    _, coord = org.user(COORDINATOR)
    t = client.post(f"{BASE}/process-types", json={"name": "Acting Auditions"}, headers=coord).json()

    p = client.post(
        f"{BASE}/processes",
        json={
            "type_id": t["id"],
            "title": "King Lear Auditions",
            "stages": [{"name": "Round 1", "sequence": 1}],
        },
        headers=coord,
    ).json()
    client.post(f"{BASE}/processes/{p['id']}/open", headers=coord)

    judge_id, judge_h = org.user(PANELIST)
    client.post(
        f"{BASE}/processes/{p['id']}/panels",
        json={"name": "Drama Panel", "member_person_ids": [judge_id]},
        headers=coord,
    )

    cand1_id, cand1_h = org.user("actor")
    cand2_id, cand2_h = org.user("actor")

    c1 = client.post(f"{BASE}/processes/{p['id']}/candidates", json={"person_id": cand1_id}, headers=coord).json()
    c2 = client.post(f"{BASE}/processes/{p['id']}/candidates", json={"person_id": cand2_id}, headers=coord).json()

    # Judge records decision for candidate 1
    dec_res = client.post(
        f"{BASE}/candidates/{c1['id']}/decisions",
        json={"outcome": "advance", "score": 95.0, "comments": "Exceptional projection"},
        headers=judge_h,
    )
    assert dec_res.status_code == 201

    # Candidate 2 tries to view Candidate 1 -> 404 Not Found
    c2_sees_c1 = client.get(f"{BASE}/candidates/{c1['id']}", headers=cand2_h)
    assert c2_sees_c1.status_code == 404

    # Candidate 2 tries to list Candidate 1's decisions -> 404 Not Found
    c2_sees_c1_decs = client.get(f"{BASE}/candidates/{c1['id']}/decisions", headers=cand2_h)
    assert c2_sees_c1_decs.status_code == 404

    # Candidate 1 views their own record -> 200 OK, but judge's decisions/scores/comments are hidden
    c1_self = client.get(f"{BASE}/candidates/{c1['id']}", headers=cand1_h)
    assert c1_self.status_code == 200
    assert c1_self.json()["decisions"] == []

    # Candidate 1 views their own decisions endpoint -> 200 OK, but empty list (other judges' decisions hidden)
    c1_self_decs = client.get(f"{BASE}/candidates/{c1['id']}/decisions", headers=cand1_h)
    assert c1_self_decs.status_code == 200
    assert c1_self_decs.json() == []

    # Judge and Coordinator can see Candidate 1's decisions with full scores and comments
    judge_view = client.get(f"{BASE}/candidates/{c1['id']}", headers=judge_h).json()
    assert len(judge_view["decisions"]) == 1
    assert judge_view["decisions"][0]["score"] == 95.0
    assert judge_view["decisions"][0]["comments"] == "Exceptional projection"

    judge_decs = client.get(f"{BASE}/candidates/{c1['id']}/decisions", headers=judge_h).json()
    assert len(judge_decs) == 1
    assert judge_decs[0]["score"] == 95.0
