"""Processes and panels lifecycle test suite."""

from conftest import BASE

COORDINATOR = "selection-process-coordinator"
PANELIST = "selection-process-panelist"


def test_process_lifecycle_and_stages(client, org):
    _, coord = org.user(COORDINATOR)
    t = client.post(f"{BASE}/process-types", json={"name": "Jury"}, headers=coord).json()

    # Create process with stages
    p_res = client.post(
        f"{BASE}/processes",
        json={
            "type_id": t["id"],
            "title": "Spring 2026 Jury",
            "academic_year": "2025-2026",
            "stages": [
                {"name": "Preliminary", "sequence": 1},
                {"name": "Final", "sequence": 2},
            ],
        },
        headers=coord,
    )
    assert p_res.status_code == 201
    proc = p_res.json()
    assert proc["status"] == "draft"
    assert len(proc["stages"]) == 2

    # Replace stages while draft
    stages_res = client.put(
        f"{BASE}/processes/{proc['id']}/stages",
        json=[
            {"name": "Round 1", "sequence": 1},
            {"name": "Semi-Final", "sequence": 2},
            {"name": "Grand Final", "sequence": 3},
        ],
        headers=coord,
    )
    assert stages_res.status_code == 200
    assert len(stages_res.json()) == 3

    # Create panel
    uid, _ = org.user(PANELIST)
    panel_res = client.post(
        f"{BASE}/processes/{proc['id']}/panels",
        json={"name": "Main Jury", "member_person_ids": [uid]},
        headers=coord,
    )
    assert panel_res.status_code == 201
    panel = panel_res.json()
    assert panel["name"] == "Main Jury"

    # Open process
    open_res = client.post(f"{BASE}/processes/{proc['id']}/open", headers=coord)
    assert open_res.status_code == 200
    assert open_res.json()["status"] == "open"

    # Cannot replace stages once open (must be draft)
    fail_stages = client.put(
        f"{BASE}/processes/{proc['id']}/stages",
        json=[{"name": "Attempt", "sequence": 1}],
        headers=coord,
    )
    assert fail_stages.status_code == 409
    body = fail_stages.json()
    detail = body.get("detail", body)
    assert detail["code"] == "process_not_draft"

    # Close process
    close_res = client.post(f"{BASE}/processes/{proc['id']}/close", headers=coord)
    assert close_res.status_code == 200
    assert close_res.json()["status"] == "closed"


def test_applicant_process_and_panel_privacy(client, org):
    _, coord = org.user(COORDINATOR)
    judge_id, _ = org.user(PANELIST)
    _, applicant_h = org.user("applicant")

    t = client.post(f"{BASE}/process-types", json={"name": "Audition Types"}, headers=coord).json()

    # Coordinator creates a draft process with a panel containing judge_id
    p = client.post(
        f"{BASE}/processes",
        json={
            "type_id": t["id"],
            "title": "Secret Draft Audition",
            "stages": [{"name": "Round 1", "sequence": 1}],
        },
        headers=coord,
    ).json()

    client.post(
        f"{BASE}/processes/{p['id']}/panels",
        json={"name": "Audition Judges", "member_person_ids": [judge_id]},
        headers=coord,
    )

    # 1. Applicant listing processes: draft process is excluded
    list_res = client.get(f"{BASE}/processes", headers=applicant_h)
    assert list_res.status_code == 200
    p_ids = [item["id"] for item in list_res.json()["items"]]
    assert p["id"] not in p_ids

    # 2. Applicant getting draft process directly -> 404 Not Found
    get_draft_res = client.get(f"{BASE}/processes/{p['id']}", headers=applicant_h)
    assert get_draft_res.status_code == 404

    # 3. Applicant listing panels of a draft process -> 404 Not Found
    panels_draft_res = client.get(f"{BASE}/processes/{p['id']}/panels", headers=applicant_h)
    assert panels_draft_res.status_code == 404

    # Coordinator opens the process
    client.post(f"{BASE}/processes/{p['id']}/open", headers=coord)

    # 4. Once open, applicant lists processes -> sees open process, but panels are omitted (empty list)
    open_list_res = client.get(f"{BASE}/processes", headers=applicant_h)
    assert open_list_res.status_code == 200
    open_p = next(item for item in open_list_res.json()["items"] if item["id"] == p["id"])
    assert open_p["panels"] == []

    # 5. Once open, applicant gets process directly -> sees process, but panels are omitted (empty list)
    get_open_res = client.get(f"{BASE}/processes/{p['id']}", headers=applicant_h)
    assert get_open_res.status_code == 200
    assert get_open_res.json()["panels"] == []

    # 6. Once open, applicant calls GET /processes/{id}/panels -> returns [] (judge identities omitted)
    panels_open_res = client.get(f"{BASE}/processes/{p['id']}/panels", headers=applicant_h)
    assert panels_open_res.status_code == 200
    assert panels_open_res.json() == []

    # 7. Coordinator can see the panels and judge IDs
    coord_get_res = client.get(f"{BASE}/processes/{p['id']}", headers=coord)
    assert coord_get_res.status_code == 200
    assert len(coord_get_res.json()["panels"]) == 1
    assert coord_get_res.json()["panels"][0]["member_person_ids"] == [judge_id]
