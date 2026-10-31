"""Integration tests through the HTTP API, against a throwaway SQLite database (see conftest). The institution's
time zone is Asia/Kolkata (UTC+05:30)."""

from conftest import BASE, COACH, STAFF, VIEWER, audit, outbox

UUID0 = "00000000-0000-4000-8000-000000000000"


def names(org_id: str) -> list[str]:
    return [e.name for e in outbox(org_id)]


# ---------------------------------------------------------------- access


def test_needs_a_token_and_a_permission(client, org):
    assert client.get(f"{BASE}/facilities").status_code == 401
    _, nobody = org.user("some-other-role")
    r = client.get(f"{BASE}/facilities", headers=nobody)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "forbidden"


def test_each_module_role_does_what_its_grants_allow(client, org):
    f = org.facility()
    body = {"name": "Pool", "facility_type": "pool", "sports": ["Swimming"], "indoor": True}
    usage = {"facility_id": f["id"], "used_from": "2026-10-28T06:00:00+05:30", "used_to": "2026-10-28T07:00:00+05:30"}
    usage["purpose"] = "training"
    _, viewer = org.user(VIEWER)
    _, coach = org.user(COACH)
    _, staff = org.user(STAFF)
    assert client.get(f"{BASE}/facilities/{f['id']}", headers=viewer).status_code == 200
    assert client.get(f"{BASE}/usage", headers=viewer).status_code == 403
    assert client.post(f"{BASE}/usage", json=usage, headers=coach).status_code == 201
    assert client.post(f"{BASE}/facilities", json=body, headers=coach).status_code == 403
    assert (
        client.put(f"{BASE}/facilities/{f['id']}/status", json={"status": "closed"}, headers=coach).status_code == 403
    )
    assert client.post(f"{BASE}/facilities", json=body, headers=staff).status_code == 403
    assert (
        client.put(f"{BASE}/facilities/{f['id']}/status", json={"status": "closed"}, headers=staff).status_code == 200
    )


# ---------------------------------------------------------------- facilities


def test_register_a_facility(client, org):
    f = org.facility(capacity=60, surface="Synthetic (polyurethane)", location="North campus")
    assert f["status"] == "operational"
    assert f["organisation_id"] == org.id
    assert f["sports"] == ["Athletics"] and f["capacity"] == 60
    assert "status_reason" not in f and "status_until" not in f
    [event] = outbox(org.id, "sports-facilities.facility.registered")
    assert event.payload == {
        "organisation_id": org.id,
        "facility_id": f["id"],
        "name": "Synthetic athletics track",
        "facility_type": "track",
        "sports": ["Athletics"],
        "capacity": 60,
    }
    assert [a.action for a in audit(org.id)] == ["facility.created"]
    assert client.get(f"{BASE}/facilities/{f['id']}", headers=org.admin).json() == f


def test_facility_validation(client, org):
    org.facility()
    base = {"name": "Synthetic athletics track", "facility_type": "track", "sports": [], "indoor": False}
    dup = client.post(f"{BASE}/facilities", json=base, headers=org.admin)
    assert dup.status_code == 400 and dup.json()["detail"]["code"] == "duplicate_name"
    for bad in (
        {**base, "name": "x", "status": "closed"},  # status changes only through PUT /status
        {**base, "name": "x", "capacity": 0},
        {**base, "name": "x", "facility_type": "stadium"},
        {**base, "name": " "},
        {"name": "x", "facility_type": "track", "sports": []},  # indoor is required
    ):
        assert client.post(f"{BASE}/facilities", json=bad, headers=org.admin).status_code == 422, bad


def test_unknown_facility_is_404(client, org):
    for path in ("", "/spaces", "/hours", "/utilisation?from=2026-10-01&to=2026-10-02"):
        assert client.get(f"{BASE}/facilities/{UUID0}{path}", headers=org.admin).status_code == 404, path
    assert client.get(f"{BASE}/facilities/not-a-uuid", headers=org.admin).status_code == 404
    assert client.patch(f"{BASE}/facilities/{UUID0}", json={"name": "x"}, headers=org.admin).status_code == 404
    assert (
        client.put(f"{BASE}/facilities/{UUID0}/status", json={"status": "closed"}, headers=org.admin).status_code == 404
    )
    assert client.put(f"{BASE}/facilities/{UUID0}/hours", json={"slots": []}, headers=org.admin).status_code == 404
    assert client.post(f"{BASE}/facilities/{UUID0}/spaces", json={"name": "x"}, headers=org.admin).status_code == 404
    assert client.get(f"{BASE}/usage/{UUID0}", headers=org.admin).status_code == 404


def test_list_and_filter_facilities(client, org):
    track = org.facility()
    pool = org.facility("Pool", facility_type="pool", sports=["Swimming", "Water polo"], indoor=True)
    org.facility("Court A", facility_type="court", sports=["Basketball"], indoor=True)
    client.put(f"{BASE}/facilities/{pool['id']}/status", json={"status": "closed"}, headers=org.admin)

    def ids(query: str = "") -> list[str]:
        r = client.get(f"{BASE}/facilities{query}", headers=org.admin)
        assert r.status_code == 200, r.text
        return [f["name"] for f in r.json()["items"]]

    assert ids() == ["Court A", "Pool", "Synthetic athletics track"]
    assert ids("?facility_type=pool") == ["Pool"]
    assert ids("?sport=water%20polo") == ["Pool"]
    assert ids("?sport=Water") == []
    assert ids("?status=closed") == ["Pool"]
    assert ids("?status=operational&indoor=false") == [track["name"]]
    page = client.get(f"{BASE}/facilities?limit=1&offset=1", headers=org.admin).json()
    assert page["total"] == 3 and [f["name"] for f in page["items"]] == ["Pool"]
    assert client.get(f"{BASE}/facilities?limit=201", headers=org.admin).status_code == 422
    assert client.get(f"{BASE}/facilities?status=open", headers=org.admin).status_code == 422


def test_update_a_facility(client, org):
    f = org.facility(capacity=60, location="North campus")
    empty = client.patch(f"{BASE}/facilities/{f['id']}", json={}, headers=org.admin)
    assert empty.status_code == 400 and empty.json()["detail"]["code"] == "empty_update"
    assert client.patch(f"{BASE}/facilities/{f['id']}", json={"name": None}, headers=org.admin).status_code == 422
    assert client.patch(f"{BASE}/facilities/{f['id']}", json={"status": "closed"}, headers=org.admin).status_code == 422
    r = client.patch(
        f"{BASE}/facilities/{f['id']}", json={"capacity": None, "sports": ["Athletics", "Football"]}, headers=org.admin
    )
    assert r.status_code == 200, r.text
    assert "capacity" not in r.json() and r.json()["sports"] == ["Athletics", "Football"]
    assert r.json()["location"] == "North campus"
    [event] = outbox(org.id, "sports-facilities.facility.updated")
    assert event.payload == {
        "organisation_id": org.id,
        "facility_id": f["id"],
        "changed_fields": ["capacity", "sports"],
    }
    # sending the current values changes nothing and announces nothing
    same = client.patch(f"{BASE}/facilities/{f['id']}", json={"location": "North campus"}, headers=org.admin)
    assert same.status_code == 200
    assert len(outbox(org.id, "sports-facilities.facility.updated")) == 1
    org.facility("Pool", facility_type="pool")
    dup = client.patch(f"{BASE}/facilities/{f['id']}", json={"name": "Pool"}, headers=org.admin)
    assert dup.status_code == 400 and dup.json()["detail"]["code"] == "duplicate_name"


# ---------------------------------------------------------------- spaces


def test_spaces_of_a_facility(client, org):
    f = org.facility()
    other = org.facility("Pool", facility_type="pool")
    lanes = org.space(f["id"], capacity=8, sports=["Athletics"])
    assert lanes["facility_id"] == f["id"] and lanes["active"] is True
    org.space(f["id"], "Lanes 5-8")
    org.space(other["id"], "Lanes 1-4")  # names are unique per facility, not per organisation
    page = client.get(f"{BASE}/facilities/{f['id']}/spaces", headers=org.admin).json()
    assert page["total"] == 2 and [s["name"] for s in page["items"]] == ["Lanes 1-4", "Lanes 5-8"]
    dup = client.post(f"{BASE}/facilities/{f['id']}/spaces", json={"name": "Lanes 1-4"}, headers=org.admin)
    assert dup.status_code == 400 and dup.json()["detail"]["code"] == "duplicate_name"
    assert (
        client.post(f"{BASE}/facilities/{f['id']}/spaces", json={"capacity": 2}, headers=org.admin).status_code == 422
    )

    path = f"{BASE}/facilities/{f['id']}/spaces/{lanes['id']}"
    r = client.patch(path, json={"active": False, "capacity": 6}, headers=org.admin)
    assert r.status_code == 200 and r.json()["active"] is False and r.json()["capacity"] == 6
    assert client.patch(path, json={}, headers=org.admin).status_code == 400
    assert client.patch(path, json={"active": None}, headers=org.admin).status_code == 422
    wrong = f"{BASE}/facilities/{other['id']}/spaces/{lanes['id']}"
    assert client.patch(wrong, json={"active": True}, headers=org.admin).status_code == 404
    updated = [e.payload["changed_fields"] for e in outbox(org.id, "sports-facilities.facility.updated")]
    assert updated == [["spaces"]] * 4
    assert {a.action for a in audit(org.id)} >= {"space.created", "space.updated"}


# ---------------------------------------------------------------- operating hours


def test_operating_hours(client, org):
    f = org.facility()
    path = f"{BASE}/facilities/{f['id']}/hours"
    assert client.get(path, headers=org.admin).json() == {"slots": []}
    slots = [
        {"day_of_week": 5, "opens_at": "07:00", "closes_at": "12:00"},
        {"day_of_week": 0, "opens_at": "16:00", "closes_at": "21:00"},
        {"day_of_week": 0, "opens_at": "06:00", "closes_at": "09:00"},
    ]
    r = client.put(path, json={"slots": slots}, headers=org.admin)
    assert r.status_code == 200, r.text
    assert [(s["day_of_week"], s["opens_at"]) for s in r.json()["slots"]] == [(0, "06:00"), (0, "16:00"), (5, "07:00")]
    assert client.get(path, headers=org.admin).json() == r.json()
    assert client.put(path, json={"slots": slots}, headers=org.admin).status_code == 200  # unchanged: no event
    [event] = outbox(org.id, "sports-facilities.facility.updated")
    assert event.payload["changed_fields"] == ["operating_hours"]

    backwards = client.put(
        path, json={"slots": [{"day_of_week": 1, "opens_at": "21:00", "closes_at": "06:00"}]}, headers=org.admin
    )
    assert backwards.status_code == 400 and backwards.json()["detail"]["code"] == "invalid_slot"
    overlap = [
        {"day_of_week": 1, "opens_at": "06:00", "closes_at": "10:00"},
        {"day_of_week": 1, "opens_at": "09:00", "closes_at": "11:00"},
    ]
    r = client.put(path, json={"slots": overlap}, headers=org.admin)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "overlapping_slots"
    for bad in ({"day_of_week": 7, "opens_at": "06:00", "closes_at": "07:00"},
                {"day_of_week": 1, "opens_at": "6:00", "closes_at": "07:00"},
                {"day_of_week": 1, "opens_at": "06:00", "closes_at": "24:00"}):  # fmt: skip
        assert client.put(path, json={"slots": [bad]}, headers=org.admin).status_code == 422, bad
    # an empty list means open at all times
    assert client.put(path, json={"slots": []}, headers=org.admin).json() == {"slots": []}
    _, viewer = org.user(VIEWER)
    assert client.get(path, headers=viewer).status_code == 200
    assert client.put(path, json={"slots": []}, headers=viewer).status_code == 403


# ---------------------------------------------------------------- availability


def test_change_availability(client, org):
    f = org.facility()
    path = f"{BASE}/facilities/{f['id']}/status"
    body = {"status": "under_maintenance", "reason": "Resurfacing", "until": "2026-11-05T18:00:00+05:30"}
    r = client.put(path, json=body, headers=org.admin)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "under_maintenance" and r.json()["status_reason"] == "Resurfacing"
    assert r.json()["status_until"] == "2026-11-05T12:30:00+00:00"
    [event] = outbox(org.id, "sports-facilities.availability.changed")
    assert event.payload == {
        "organisation_id": org.id,
        "facility_id": f["id"],
        "status": "under_maintenance",
        "reason": "Resurfacing",
        "until": "2026-11-05T12:30:00+00:00",
    }
    assert client.put(path, json=body, headers=org.admin).status_code == 200  # the same again: no new event
    reopened = client.put(path, json={"status": "operational"}, headers=org.admin).json()
    assert reopened["status"] == "operational"
    assert "status_reason" not in reopened and "status_until" not in reopened
    assert len(outbox(org.id, "sports-facilities.availability.changed")) == 2
    assert [a.action for a in audit(org.id)].count("facility.status_changed") == 2

    past = client.put(path, json={"status": "closed", "until": "2026-10-29T08:00:00+00:00"}, headers=org.admin)
    assert past.status_code == 400 and past.json()["detail"]["code"] == "until_in_past"
    assert client.put(path, json={"status": "open"}, headers=org.admin).status_code == 422
    assert (
        client.put(path, json={"status": "closed", "until": "2026-11-05T18:00:00"}, headers=org.admin).status_code
        == 422
    )


# ---------------------------------------------------------------- usage


def test_record_usage(client, org):
    f = org.facility()
    lanes = org.space(f["id"])
    me, coach = org.user(COACH)
    body = {
        "facility_id": f["id"],
        "space_id": lanes["id"],
        "used_from": "2026-10-28T06:00:00+05:30",
        "used_to": "2026-10-28T07:30:00+05:30",
        "purpose": "training",
        "group_name": "Senior sprint squad",
        "headcount": 14,
        "booking_reference": "FB-1042",
    }
    r = client.post(f"{BASE}/usage", json=body, headers=coach)
    assert r.status_code == 201, r.text
    u = r.json()
    assert u["recorded_by"] == me and u["used_from"] == "2026-10-28T00:30:00+00:00"
    assert client.get(f"{BASE}/usage/{u['id']}", headers=coach).json() == u
    [event] = outbox(org.id, "sports-facilities.usage.recorded")
    assert event.payload == {
        "organisation_id": org.id,
        "usage_id": u["id"],
        "facility_id": f["id"],
        "space_id": lanes["id"],
        "used_from": "2026-10-28T00:30:00+00:00",
        "used_to": "2026-10-28T02:00:00+00:00",
        "purpose": "training",
        "headcount": 14,
    }
    assert "usage.recorded" in {a.action for a in audit(org.id)}


def test_usage_rules(client, org):
    f = org.facility()
    pool = org.facility("Pool", facility_type="pool")
    pool_lane = org.space(pool["id"], "Lane 1")
    base = {"facility_id": f["id"], "used_from": "2026-10-28T06:00:00Z", "used_to": "2026-10-28T07:00:00Z"}
    base["purpose"] = "competition"

    def post(**changes):
        return client.post(f"{BASE}/usage", json={**base, **changes}, headers=org.admin)

    for changes, code in (
        ({"used_to": "2026-10-28T06:00:00Z"}, "invalid_window"),
        ({"used_to": "2026-10-28T05:00:00Z"}, "invalid_window"),
        ({"space_id": pool_lane["id"]}, "space_not_in_facility"),
        ({"space_id": UUID0}, "space_not_in_facility"),
        ({"facility_id": UUID0}, "unknown_facility"),
    ):
        r = post(**changes)
        assert r.status_code == 400 and r.json()["detail"]["code"] == code, (changes, r.text)
    for changes in (
        {"facility_id": "not-a-uuid"},
        {"space_id": ""},
        {"used_from": "2026-10-28T06:00:00"},  # a time without its offset is ambiguous
        {"purpose": "party"},
        {"headcount": 0},
        {"recorded_by": UUID0},
    ):
        assert post(**changes).status_code == 422, changes
    assert outbox(org.id, "sports-facilities.usage.recorded") == []


def test_list_usage_by_local_dates_newest_first(client, org):
    f = org.facility()
    pool = org.facility("Pool", facility_type="pool")
    # 27 Oct 23:00 to 28 Oct 01:00 in Kolkata: touches both local dates
    late = org.usage(f["id"], "2026-10-27T17:30:00Z", "2026-10-27T19:30:00Z", "event")
    # 28 Oct 03:00 UTC is 28 Oct 08:30 local
    morning = org.usage(f["id"], "2026-10-28T03:00:00Z", "2026-10-28T04:00:00Z")
    # 29 Oct 00:30 local, still 28 Oct in UTC
    night = org.usage(pool["id"], "2026-10-28T19:00:00Z", "2026-10-28T20:00:00Z")

    def ids(query: str) -> list[str]:
        r = client.get(f"{BASE}/usage{query}", headers=org.admin)
        assert r.status_code == 200, r.text
        return [u["id"] for u in r.json()["items"]]

    assert ids("") == [night["id"], morning["id"], late["id"]]
    assert ids("?from=2026-10-28&to=2026-10-28") == [morning["id"], late["id"]]
    assert ids("?from=2026-10-29") == [night["id"]]
    assert ids("?to=2026-10-27") == [late["id"]]
    assert ids(f"?facility_id={f['id']}&purpose=training") == [morning["id"]]
    assert ids("?from=2026-10-29&to=2026-10-28") == []
    page = client.get(f"{BASE}/usage?limit=1&offset=2", headers=org.admin).json()
    assert page == {"items": [late], "total": 3}


# ---------------------------------------------------------------- utilisation


def test_utilisation_against_weekly_hours(client, org):
    f = org.facility()
    hours = [
        {"day_of_week": 0, "opens_at": "06:00", "closes_at": "10:00"},  # Monday
        {"day_of_week": 1, "opens_at": "06:00", "closes_at": "10:00"},  # Tuesday
    ]
    client.put(f"{BASE}/facilities/{f['id']}/hours", json={"slots": hours}, headers=org.admin)
    lanes = org.space(f["id"])
    # Monday 26 Oct, local time: two squads at once count once for the facility
    org.usage(f["id"], "2026-10-26T06:00:00+05:30", "2026-10-26T08:00:00+05:30", space_id=lanes["id"])
    org.usage(f["id"], "2026-10-26T07:00:00+05:30", "2026-10-26T08:00:00+05:30", "physical_education")
    # Tuesday 27 Oct
    org.usage(f["id"], "2026-10-27T09:00:00+05:30", "2026-10-27T10:00:00+05:30", "physical_education")
    # Sunday 25 Oct 23:00 local to Monday 01:00: only the Monday hour is inside the period
    org.usage(f["id"], "2026-10-25T23:00:00+05:30", "2026-10-26T01:00:00+05:30", "event")

    r = client.get(f"{BASE}/facilities/{f['id']}/utilisation?from=2026-10-26&to=2026-11-01", headers=org.admin)
    assert r.status_code == 200, r.text
    assert r.json() == {
        "facility_id": f["id"],
        "hours_open": 8,
        "hours_used": 4,
        "utilisation_pct": 50,
        "by_purpose": [
            {"purpose": "training", "hours": 2},
            {"purpose": "physical_education", "hours": 2},
            {"purpose": "event", "hours": 1},
        ],
    }
    # Wednesday to Friday: closed every day, so there is no percentage
    closed = client.get(f"{BASE}/facilities/{f['id']}/utilisation?from=2026-10-28&to=2026-10-30", headers=org.admin)
    assert closed.json() == {"facility_id": f["id"], "hours_open": 0, "hours_used": 0, "by_purpose": []}


def test_utilisation_without_hours_is_open_all_day_and_checks_the_period(client, org):
    f = org.facility()
    org.usage(f["id"], "2026-10-26T06:00:00+05:30", "2026-10-26T12:00:00+05:30")
    path = f"{BASE}/facilities/{f['id']}/utilisation"
    r = client.get(f"{path}?from=2026-10-26&to=2026-10-26", headers=org.admin).json()
    assert r["hours_open"] == 24 and r["hours_used"] == 6 and r["utilisation_pct"] == 25
    backwards = client.get(f"{path}?from=2026-10-27&to=2026-10-26", headers=org.admin)
    assert backwards.status_code == 400 and backwards.json()["detail"]["code"] == "invalid_period"
    year = client.get(f"{path}?from=2028-01-01&to=2028-12-31", headers=org.admin)
    assert year.status_code == 200 and year.json()["hours_open"] == 366 * 24
    long = client.get(f"{path}?from=2026-01-01&to=2027-01-02", headers=org.admin)
    assert long.status_code == 400 and long.json()["detail"]["code"] == "period_too_long"
    assert client.get(f"{path}?from=2026-10-26", headers=org.admin).status_code == 422
    _, viewer = org.user(VIEWER)
    assert client.get(f"{path}?from=2026-10-26&to=2026-10-26", headers=viewer).status_code == 403
