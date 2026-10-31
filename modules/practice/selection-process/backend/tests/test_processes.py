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

