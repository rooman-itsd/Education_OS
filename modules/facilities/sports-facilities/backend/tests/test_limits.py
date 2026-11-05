"""Inputs at and past the limits of api/schemas.py: dates outside 2000..2100 are 422 instead of an overflow (500),
lists and text are capped, a status lasts at most 366 days, and concurrent hours updates cannot leave two slot sets."""

from conftest import BASE
from eos_sports_facilities.infrastructure import repository

FAR = ("9999-12-31", "0001-01-01", "1999-12-31", "2101-01-01")


def _code(r) -> str:
    return r.json()["detail"]["code"]


def test_usage_list_dates_are_bounded_and_ordered(client, org):
    for day in FAR:
        for query in (f"to={day}", f"from={day}", f"from=2026-10-01&to={day}"):
            assert client.get(f"{BASE}/usage?{query}", headers=org.admin).status_code == 422, query
    assert client.get(f"{BASE}/usage?from=2000-01-01&to=2000-12-31", headers=org.admin).status_code == 200
    assert client.get(f"{BASE}/usage?from=2100-01-01", headers=org.admin).status_code == 200
    backwards = client.get(f"{BASE}/usage?from=2026-10-29&to=2026-10-28", headers=org.admin)
    assert backwards.status_code == 400 and _code(backwards) == "invalid_period"
    long = client.get(f"{BASE}/usage?from=2026-01-01&to=2027-01-02", headers=org.admin)
    assert long.status_code == 400 and _code(long) == "period_too_long"


def test_utilisation_dates_are_bounded(client, org):
    f = org.facility()
    path = f"{BASE}/facilities/{f['id']}/utilisation"
    assert client.get(f"{path}?from=9999-12-31&to=9999-12-31", headers=org.admin).status_code == 422
    assert client.get(f"{path}?from=0001-01-01&to=0001-01-01", headers=org.admin).status_code == 422


def test_usage_times_are_bounded(client, org):
    f = org.facility()

    def post(used_from: str, used_to: str):
        body = {"facility_id": f["id"], "used_from": used_from, "used_to": used_to, "purpose": "training"}
        return client.post(f"{BASE}/usage", json=body, headers=org.admin)

    assert post("0001-01-01T00:00:00+05:30", "2026-10-28T07:00:00+05:30").status_code == 422
    assert post("2026-10-28T06:00:00+05:30", "9999-12-31T23:59:59-05:00").status_code == 422
    assert post("1999-12-31T23:00:00+00:00", "2000-01-01T01:00:00+00:00").status_code == 422
    assert post("2100-12-31T20:00:00+00:00", "2101-01-01T00:00:01+00:00").status_code == 422
    assert post("2000-01-01T00:00:00+00:00", "2000-01-01T01:00:00+00:00").status_code == 201


def test_status_until_is_bounded(client, org):
    f = org.facility()
    path = f"{BASE}/facilities/{f['id']}/status"

    def put(until: str):
        return client.put(path, json={"status": "closed", "until": until}, headers=org.admin)

    assert put("9999-12-31T23:00:00-05:00").status_code == 422
    assert put("0001-01-01T00:00:00+05:30").status_code == 422
    too_far = put("2027-11-01T00:00:00+00:00")  # the clock is 29 Oct 2026; 366 days ends 30 Oct 2027
    assert too_far.status_code == 400 and _code(too_far) == "until_too_far"
    assert put("2027-10-29T00:00:00+00:00").status_code == 200


def test_lists_and_text_are_capped(client, org):
    def create(**changes):
        body = {"name": "Court", "facility_type": "court", "sports": ["Tennis"], "indoor": False, **changes}
        return client.post(f"{BASE}/facilities", json=body, headers=org.admin)

    assert create(sports=[f"Sport {i}" for i in range(51)]).status_code == 422
    assert create(sports=["x" * 81]).status_code == 422
    assert create(description="x" * 5001).status_code == 422
    f = create(sports=[f"Sport {i}" for i in range(50)], description="x" * 5000)
    assert f.status_code == 201, f.text
    fid = f.json()["id"]
    patch = f"{BASE}/facilities/{fid}"
    assert client.patch(patch, json={"sports": ["s"] * 51}, headers=org.admin).status_code == 422
    assert client.patch(patch, json={"description": "x" * 5001}, headers=org.admin).status_code == 422
    spaces = f"{BASE}/facilities/{fid}/spaces"
    assert client.post(spaces, json={"name": "A", "sports": ["s"] * 51}, headers=org.admin).status_code == 422
    space = org.space(fid, "A")
    space_path = f"{spaces}/{space['id']}"
    assert client.patch(space_path, json={"sports": ["s"] * 51}, headers=org.admin).status_code == 422

    hours = f"{BASE}/facilities/{fid}/hours"
    slots = [{"day_of_week": i % 7, "opens_at": f"{i // 7:02d}:00", "closes_at": f"{i // 7:02d}:30"} for i in range(51)]
    assert client.put(hours, json={"slots": slots}, headers=org.admin).status_code == 422
    assert client.put(hours, json={"slots": slots[:50]}, headers=org.admin).status_code == 200


def test_hours_keep_an_opening_time_with_a_new_closing_time(client, org):
    f = org.facility()
    path = f"{BASE}/facilities/{f['id']}/hours"
    client.put(path, json={"slots": [{"day_of_week": 0, "opens_at": "06:00", "closes_at": "09:00"}]}, headers=org.admin)
    r = client.put(
        path, json={"slots": [{"day_of_week": 0, "opens_at": "06:00", "closes_at": "10:00"}]}, headers=org.admin
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"slots": [{"day_of_week": 0, "opens_at": "06:00", "closes_at": "10:00"}]}


def test_concurrent_hours_update_is_409_not_two_slot_sets(client, org, monkeypatch):
    f = org.facility()
    path = f"{BASE}/facilities/{f['id']}/hours"
    first = [{"day_of_week": 0, "opens_at": "06:00", "closes_at": "09:00"}]
    assert client.put(path, json={"slots": first}, headers=org.admin).status_code == 200
    # A second PUT that read the slots before the first one committed sees none, and inserts its own set too.
    monkeypatch.setattr(repository, "slots", lambda db, facility_id: [])
    second = [{"day_of_week": 0, "opens_at": "06:00", "closes_at": "08:00"}]
    r = client.put(path, json={"slots": second}, headers=org.admin)
    assert r.status_code == 409 and _code(r) == "hours_conflict"
    monkeypatch.undo()
    assert client.get(path, headers=org.admin).json() == {"slots": first}


def test_an_invalid_token_does_not_echo_the_library_message(client):
    r = client.get(f"{BASE}/facilities", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401
    assert r.json()["detail"] == {"code": "unauthorised", "message": "invalid token"}
