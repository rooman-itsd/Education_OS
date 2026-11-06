"""Slot scheduling (POST /processes/{id}/slots) and the contract's comma-separated `status` filters."""

from datetime import UTC, datetime, timedelta

from conftest import BASE

COORDINATOR = "selection-process-coordinator"
PANELIST = "selection-process-panelist"


def _open_process(client, coord, title="Jury", panelists=()):
    type_id = client.post(f"{BASE}/process-types", json={"name": f"{title} type"}, headers=coord).json()["id"]
    proc = client.post(
        f"{BASE}/processes",
        json={"type_id": type_id, "title": title, "stages": [{"name": "Round 1", "sequence": 1}]},
        headers=coord,
    ).json()
    if panelists:
        client.post(
            f"{BASE}/processes/{proc['id']}/panels",
            json={"name": "Panel", "member_person_ids": list(panelists)},
            headers=coord,
        )
    client.post(f"{BASE}/processes/{proc['id']}/open", headers=coord)
    return proc


def _slot(title="Audition", days=1, **extra):
    start = datetime.now(UTC) + timedelta(days=days)
    return {
        "title": title,
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=1)).isoformat(),
        **extra,
    }


def test_create_slot_is_listed_as_upcoming_for_its_candidate(client, org):
    _, coord = org.user(COORDINATOR)
    cand_id, cand_h = org.user("artist")
    proc = _open_process(client, coord)
    cand = client.post(f"{BASE}/processes/{proc['id']}/candidates", json={"person_id": cand_id}, headers=coord).json()
    stage_id = client.get(f"{BASE}/processes/{proc['id']}", headers=coord).json()["stages"][0]["id"]

    res = client.post(
        f"{BASE}/processes/{proc['id']}/slots",
        json=_slot("Jury Round 1", candidate_id=cand["id"], stage_id=stage_id, location="Studio 2"),
        headers=coord,
    )
    assert res.status_code == 201, res.text
    slot = res.json()
    assert (slot["title"], slot["status"], slot["location"]) == ("Jury Round 1", "scheduled", "Studio 2")

    upcoming = client.get(f"{BASE}/slots/upcoming", headers=cand_h)
    assert upcoming.status_code == 200
    assert [s["id"] for s in upcoming.json()] == [slot["id"]]


def test_slot_must_end_after_it_starts(client, org):
    _, coord = org.user(COORDINATOR)
    proc = _open_process(client, coord)
    bad = _slot()
    bad["ends_at"] = bad["starts_at"]
    res = client.post(f"{BASE}/processes/{proc['id']}/slots", json=bad, headers=coord)
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "invalid_slot"


def test_slot_stage_and_candidate_must_belong_to_the_process(client, org):
    _, coord = org.user(COORDINATOR)
    mine = _open_process(client, coord, "Mine")
    theirs = _open_process(client, coord, "Theirs")
    other_cand_id, _ = org.user("artist")
    foreign_cand = client.post(
        f"{BASE}/processes/{theirs['id']}/candidates", json={"person_id": other_cand_id}, headers=coord
    ).json()
    foreign_stage = client.get(f"{BASE}/processes/{theirs['id']}", headers=coord).json()["stages"][0]["id"]

    for extra in ({"candidate_id": foreign_cand["id"]}, {"stage_id": foreign_stage}):
        res = client.post(f"{BASE}/processes/{mine['id']}/slots", json=_slot(**extra), headers=coord)
        assert res.status_code == 422, res.text
        assert res.json()["detail"]["code"] == "invalid_slot"


def test_only_a_manager_creates_slots_and_only_in_their_organisation(client, org, other_org):
    _, coord = org.user(COORDINATOR)
    proc = _open_process(client, coord)
    _, panelist_h = org.user(PANELIST)
    assert client.post(f"{BASE}/processes/{proc['id']}/slots", json=_slot(), headers=panelist_h).status_code == 403

    _, outsider = other_org.user(COORDINATOR)
    assert client.post(f"{BASE}/processes/{proc['id']}/slots", json=_slot(), headers=outsider).status_code == 404


def test_candidate_status_filter_accepts_comma_separated_and_repeated_values(client, org):
    _, coord = org.user(COORDINATOR)
    judge_id, judge_h = org.user(PANELIST)
    proc = _open_process(client, coord, panelists=[judge_id])
    cand_id, _ = org.user("artist")
    client.post(f"{BASE}/processes/{proc['id']}/candidates", json={"person_id": cand_id}, headers=coord)
    url = f"{BASE}/processes/{proc['id']}/candidates"

    for query in (
        "scope=managed&status=registered,in_progress",  # the contract's form, as the To Judge widget sends it
        "scope=managed&status=registered&status=in_progress",
    ):
        res = client.get(f"{url}?{query}", headers=judge_h)
        assert res.status_code == 200
        assert res.json()["total"] == 1, query
    assert client.get(f"{url}?scope=managed&status=selected,rejected", headers=judge_h).json()["total"] == 0


def test_process_status_filter_accepts_comma_separated_values(client, org):
    _, coord = org.user(COORDINATOR)
    proc = _open_process(client, coord)
    res = client.get(f"{BASE}/processes?status=open,closed", headers=coord)
    assert proc["id"] in [p["id"] for p in res.json()["items"]]
    res = client.get(f"{BASE}/processes?status=draft,closed", headers=coord)
    assert proc["id"] not in [p["id"] for p in res.json()["items"]]
