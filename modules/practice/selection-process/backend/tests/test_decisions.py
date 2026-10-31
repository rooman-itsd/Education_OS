"""Decisions, multi-panelist uniqueness, and progression test suite."""

from conftest import BASE

COORDINATOR = "selection-process-coordinator"
PANELIST = "selection-process-panelist"


def test_multi_panelist_decisions_and_stage_progression(client, org):
    _, coord = org.user(COORDINATOR)
    t = client.post(f"{BASE}/process-types", json={"name": "Music Recital"}, headers=coord).json()

    p = client.post(
        f"{BASE}/processes",
        json={
            "type_id": t["id"],
            "title": "Violin Chair Audition",
            "stages": [
                {"name": "Preliminary Round", "sequence": 1},
                {"name": "Final Showcase", "sequence": 2},
            ],
        },
        headers=coord,
    ).json()

    stage1_id = p["stages"][0]["id"]
    stage2_id = p["stages"][1]["id"]

    judge1_id, judge1_headers = org.user(PANELIST)
    judge2_id, judge2_headers = org.user(PANELIST)

    # Create panel including both judges
    client.post(
        f"{BASE}/processes/{p['id']}/panels",
        json={"name": "Violin Faculty", "member_person_ids": [judge1_id, judge2_id]},
        headers=coord,
    )

    client.post(f"{BASE}/processes/{p['id']}/open", headers=coord)

    student_id, _ = org.user(PANELIST)
    cand = client.post(
        f"{BASE}/processes/{p['id']}/candidates",
        json={"person_id": student_id},
        headers=coord,
    ).json()

    assert cand["current_stage_id"] == stage1_id
    assert cand["status"] == "registered"

    # Judge 1 records decision on stage 1: hold
    dec1_res = client.post(
        f"{BASE}/candidates/{cand['id']}/decisions",
        json={"outcome": "hold", "score": 85.5, "comments": "Good tone, need more vibrato"},
        headers=judge1_headers,
    )
    assert dec1_res.status_code == 201

    # Judge 1 tries to record another decision on stage 1 -> 409 already_decided
    dup_dec = client.post(
        f"{BASE}/candidates/{cand['id']}/decisions",
        json={"outcome": "advance"},
        headers=judge1_headers,
    )
    assert dup_dec.status_code == 409
    body = dup_dec.json()
    detail = body.get("detail", body)
    assert detail["code"] == "already_decided"

    # Judge 2 CAN record decision on stage 1 (multi-panelist): advance to stage 2
    dec2_res = client.post(
        f"{BASE}/candidates/{cand['id']}/decisions",
        json={"outcome": "advance", "score": 92.0, "comments": "Ready for finals"},
        headers=judge2_headers,
    )
    assert dec2_res.status_code == 201

    # Candidate should now be advanced to stage 2!
    updated_cand = client.get(f"{BASE}/candidates/{cand['id']}", headers=coord).json()
    assert updated_cand["current_stage_id"] == stage2_id
    assert updated_cand["status"] == "in_progress"
    assert len(updated_cand["decisions"]) == 2

    # In stage 2 (the final stage), Judge 1 advances candidate -> candidate becomes selected!
    final_dec = client.post(
        f"{BASE}/candidates/{cand['id']}/decisions",
        json={"outcome": "advance", "score": 98.0, "comments": "Outstanding final performance"},
        headers=judge1_headers,
    )
    assert final_dec.status_code == 201

    selected_cand = client.get(f"{BASE}/candidates/{cand['id']}", headers=coord).json()
    assert selected_cand["status"] == "selected"
    assert selected_cand["decided_at"] is not None

    # Cannot record any more decisions after final outcome -> 409 candidate_finalized
    after_final = client.post(
        f"{BASE}/candidates/{cand['id']}/decisions",
        json={"outcome": "reject"},
        headers=judge2_headers,
    )
    assert after_final.status_code == 409
    body = after_final.json()
    detail = body.get("detail", body)
    assert detail["code"] == "candidate_finalized"


def test_direct_finalize_outcome(client, org):
    _, coord = org.user(COORDINATOR)
    t = client.post(f"{BASE}/process-types", json={"name": "Fellowship"}, headers=coord).json()

    p = client.post(
        f"{BASE}/processes",
        json={
            "type_id": t["id"],
            "title": "Postdoc Allocation",
            "stages": [{"name": "Review", "sequence": 1}],
        },
        headers=coord,
    ).json()
    client.post(f"{BASE}/processes/{p['id']}/open", headers=coord)

    applicant_id, _ = org.user(PANELIST)
    cand = client.post(
        f"{BASE}/processes/{p['id']}/candidates",
        json={"person_id": applicant_id},
        headers=coord,
    ).json()

    # Coordinator directly finalizes candidate to waitlisted
    fin_res = client.post(
        f"{BASE}/candidates/{cand['id']}/finalize",
        json={"outcome": "waitlisted", "comments": "High quality, placed on reserve list"},
        headers=coord,
    )
    assert fin_res.status_code == 200
    assert fin_res.json()["status"] == "waitlisted"
    assert fin_res.json()["decided_at"] is not None

    # Cannot finalize again
    fin_again = client.post(
        f"{BASE}/candidates/{cand['id']}/finalize",
        json={"outcome": "selected"},
        headers=coord,
    )
    assert fin_again.status_code == 409
    body = fin_again.json()
    detail = body.get("detail", body)
    assert detail["code"] == "candidate_finalized"


def test_unassigned_panelist_cannot_record_decision(client, org):
    _, coord = org.user(COORDINATOR)
    t = client.post(f"{BASE}/process-types", json={"name": "Drama Audition"}, headers=coord).json()

    p = client.post(
        f"{BASE}/processes",
        json={
            "type_id": t["id"],
            "title": "Macbeth Casting",
            "stages": [
                {"name": "Stage 1", "sequence": 1},
                {"name": "Stage 2", "sequence": 2},
            ],
        },
        headers=coord,
    ).json()

    stage1_id = p["stages"][0]["id"]
    stage2_id = p["stages"][1]["id"]

    panelist_stage1_id, panelist_stage1_h = org.user(PANELIST)
    panelist_stage2_id, panelist_stage2_h = org.user(PANELIST)
    unassigned_panelist_id, unassigned_panelist_h = org.user(PANELIST)

    # Panel 1 is for Stage 1 only
    client.post(
        f"{BASE}/processes/{p['id']}/panels",
        json={"name": "Panel Stage 1", "stage_id": stage1_id, "member_person_ids": [panelist_stage1_id]},
        headers=coord,
    )
    # Panel 2 is for Stage 2 only
    client.post(
        f"{BASE}/processes/{p['id']}/panels",
        json={"name": "Panel Stage 2", "stage_id": stage2_id, "member_person_ids": [panelist_stage2_id]},
        headers=coord,
    )

    client.post(f"{BASE}/processes/{p['id']}/open", headers=coord)

    candidate_user_id, _ = org.user("actor")
    cand = client.post(
        f"{BASE}/processes/{p['id']}/candidates",
        json={"person_id": candidate_user_id},
        headers=coord,
    ).json()
    assert cand["current_stage_id"] == stage1_id

    # Panelist for Stage 2 tries to record decision on Stage 1 -> 403 Forbidden
    res_other_panel = client.post(
        f"{BASE}/candidates/{cand['id']}/decisions",
        json={"outcome": "advance", "score": 90.0},
        headers=panelist_stage2_h,
    )
    assert res_other_panel.status_code == 403

    # Unassigned panelist tries to record decision -> 403 Forbidden
    res_unassigned = client.post(
        f"{BASE}/candidates/{cand['id']}/decisions",
        json={"outcome": "advance", "score": 90.0},
        headers=unassigned_panelist_h,
    )
    assert res_unassigned.status_code == 403

    # Assigned panelist for Stage 1 can record decision -> 201 Created
    res_assigned = client.post(
        f"{BASE}/candidates/{cand['id']}/decisions",
        json={"outcome": "advance", "score": 95.0},
        headers=panelist_stage1_h,
    )
    assert res_assigned.status_code == 201


def test_self_judging_forbidden(client, org):
    _, coord = org.user(COORDINATOR)
    t = client.post(f"{BASE}/process-types", json={"name": "Solo Performance"}, headers=coord).json()

    p = client.post(
        f"{BASE}/processes",
        json={
            "type_id": t["id"],
            "title": "Recital Auditions",
            "stages": [{"name": "Audition", "sequence": 1}],
        },
        headers=coord,
    ).json()

    stage_id = p["stages"][0]["id"]
    judge_id, judge_h = org.user(PANELIST)

    client.post(
        f"{BASE}/processes/{p['id']}/panels",
        json={"name": "Audition Panel", "stage_id": stage_id, "member_person_ids": [judge_id]},
        headers=coord,
    )
    client.post(f"{BASE}/processes/{p['id']}/open", headers=coord)

    # Panelist is registered as a candidate
    c_judge = client.post(
        f"{BASE}/processes/{p['id']}/candidates",
        json={"person_id": judge_id},
        headers=coord,
    ).json()

    # Panelist attempts to record decision on own candidacy -> 403 Forbidden
    res_self_dec = client.post(
        f"{BASE}/candidates/{c_judge['id']}/decisions",
        json={"outcome": "advance", "score": 100.0},
        headers=judge_h,
    )
    assert res_self_dec.status_code == 403
    assert res_self_dec.json()["detail"]["code"] == "forbidden"

    # Coordinator is registered as a candidate
    coord_id, coord_h = org.user(COORDINATOR)
    c_coord = client.post(
        f"{BASE}/processes/{p['id']}/candidates",
        json={"person_id": coord_id},
        headers=coord,
    ).json()

    # Coordinator attempts to finalize own candidacy -> 403 Forbidden
    res_self_fin = client.post(
        f"{BASE}/candidates/{c_coord['id']}/finalize",
        json={"outcome": "selected"},
        headers=coord_h,
    )
    assert res_self_fin.status_code == 403
    assert res_self_fin.json()["detail"]["code"] == "forbidden"
