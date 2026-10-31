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

