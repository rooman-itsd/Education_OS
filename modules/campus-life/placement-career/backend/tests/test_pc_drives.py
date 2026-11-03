"""Drives (stories O2, O3, S2): draft -> scheduled -> completed, or cancelled; rescheduling; visibility; every error
code of /drives."""

import pytest
from pc_support import BASE, apply, code, company, day, drive, ok, opening, outbox


def test_plan_schedule_and_complete_a_drive(client, org, clock):
    co = company(client, org)
    d = drive(client, org, co, schedule=False, rounds=[" Aptitude ", "", "HR"], ends_on=day(11))
    assert d["status"] == "draft" and d["company"] == {
        "id": co["id"],
        "name": co["name"],
        "industry": co["industry"],
        "website": co["website"],
    }
    assert d["rounds"] == ["Aptitude", "HR"] and d["ends_on"] == day(11) and "openings" not in d
    assert d["eligibility"] == {
        "programmes": ["B.Tech"],
        "graduating_years": [2027],
        "min_cgpa": 6.5,
        "max_active_backlogs": None,
        "notes": None,
    }
    d = ok(client.post(f"{BASE}/drives/{d['id']}/schedule", headers=org.officer))
    assert d["status"] == "scheduled"
    [ev] = outbox(org.id, "placement-career.drive.scheduled")
    assert ev.payload == {
        "organisation_id": org.id,
        "drive_id": d["id"],
        "company_id": co["id"],
        "scheduled_on": day(10),
        "registration_closes_on": day(7),
    }
    assert ev.actor == org.ids["officer"]
    assert code(client.post(f"{BASE}/drives/{d['id']}/complete", headers=org.officer), 422) == "invalid_date"
    clock.advance(days=10)
    d = ok(client.post(f"{BASE}/drives/{d['id']}/complete", headers=org.officer))
    assert d["status"] == "completed"
    [ev] = outbox(org.id, "placement-career.drive.completed")
    assert ev.payload == {
        "organisation_id": org.id,
        "drive_id": d["id"],
        "company_id": co["id"],
        "scheduled_on": day(10),
    }
    assert code(client.post(f"{BASE}/drives/{d['id']}/complete", headers=org.officer), 409) == "not_scheduled"
    assert code(client.post(f"{BASE}/drives/{d['id']}/schedule", headers=org.officer), 409) == "not_draft"
    body = {"company_id": co["id"], "title": "x", "scheduled_on": day(20)}
    assert code(client.put(f"{BASE}/drives/{d['id']}", json=body, headers=org.officer), 409) == "not_editable"
    r = client.post(f"{BASE}/drives/{d['id']}/cancel", json={"reason": "x"}, headers=org.officer)
    assert code(r, 409) == "not_cancellable"


def test_get_drive_lists_the_openings_the_caller_may_see(client, org):
    d = drive(client, org)
    o1 = opening(client, org, dr=d, applications_close_on=day(3))
    o2 = opening(client, org, dr=d, publish=False)
    officer = ok(client.get(f"{BASE}/drives/{d['id']}", headers=org.officer))
    student = ok(client.get(f"{BASE}/drives/{d['id']}", headers=org.student))
    assert [o["id"] for o in officer["openings"]] == [o1["id"], o2["id"]] and officer["openings_count"] == 2
    assert [o["id"] for o in student["openings"]] == [o1["id"]] and student["openings_count"] == 1
    assert student["openings"][0] == {
        "id": o1["id"],
        "title": o1["title"],
        "status": "open",
        "ctc_per_annum": "650000.00",
        "applications_close_on": day(3),
    }


def test_draft_and_cancelled_drives_are_visible_only_to_managers(client, org):
    scheduled = drive(client, org)
    draft = drive(client, org, schedule=False)
    cancelled = drive(client, org, schedule=False)
    ok(client.post(f"{BASE}/drives/{cancelled['id']}/cancel", json={"reason": "Postponed"}, headers=org.officer))
    officer = {d["id"] for d in ok(client.get(f"{BASE}/drives", headers=org.officer))["items"]}
    assert {scheduled["id"], draft["id"], cancelled["id"]} <= officer
    for who in ("student", "student2", "viewer"):
        seen = {d["id"] for d in ok(client.get(f"{BASE}/drives", headers=org.headers[who]))["items"]}
        assert seen == {scheduled["id"]}, who
        for hidden in (draft, cancelled):
            assert code(client.get(f"{BASE}/drives/{hidden['id']}", headers=org.headers[who]), 404) == "not_found"
        r = client.get(f"{BASE}/drives", params={"status": "draft"}, headers=org.headers[who])
        assert ok(r)["items"] == []


def test_list_filters_and_order(client, org):
    a, b = company(client, org), company(client, org)
    late = drive(client, org, a, scheduled_on=day(20), registration_closes_on=None)
    soon = drive(client, org, b, scheduled_on=day(2), registration_closes_on=None)
    mid = drive(client, org, a, scheduled_on=day(9), registration_closes_on=None, schedule=False)
    ids = [d["id"] for d in ok(client.get(f"{BASE}/drives", headers=org.officer))["items"]]
    assert ids == [soon["id"], mid["id"], late["id"]]
    by_company = ok(client.get(f"{BASE}/drives", params={"company_id": a["id"]}, headers=org.officer))["items"]
    assert [d["id"] for d in by_company] == [mid["id"], late["id"]]
    window = ok(client.get(f"{BASE}/drives", params={"from": day(3), "to": day(20)}, headers=org.officer))["items"]
    assert [d["id"] for d in window] == [mid["id"], late["id"]]
    status = ok(client.get(f"{BASE}/drives", params={"status": "draft"}, headers=org.officer))["items"]
    assert [d["id"] for d in status] == [mid["id"]]
    assert client.get(f"{BASE}/drives", params={"status": "bogus"}, headers=org.officer).status_code == 422
    page = ok(client.get(f"{BASE}/drives", params={"limit": 2}, headers=org.officer))
    rest = ok(client.get(f"{BASE}/drives", params={"limit": 2, "cursor": page["next_cursor"]}, headers=org.officer))
    assert [d["id"] for d in page["items"] + rest["items"]] == ids and rest["next_cursor"] is None
    assert code(client.get(f"{BASE}/drives", params={"cursor": "x"}, headers=org.officer), 400) == "invalid_cursor"


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"title": " "}, "invalid_title"),
        ({"scheduled_on": day(-1)}, "invalid_date"),
        ({"ends_on": day(9)}, "invalid_date"),
        ({"registration_closes_on": day(11)}, "invalid_date"),
        ({"eligibility": {"min_cgpa": 10.5}}, "invalid_eligibility"),
        ({"eligibility": {"min_cgpa": -1}}, "invalid_eligibility"),
        ({"eligibility": {"max_active_backlogs": -1}}, "invalid_eligibility"),
        ({"eligibility": {"programmes": ["B.Tech", " "]}}, "invalid_eligibility"),
    ],
)
def test_invalid_drive_values(client, org, fields, expected):
    co = company(client, org)
    body = {"company_id": co["id"], "title": "Drive", "scheduled_on": day(10), **fields}
    assert code(client.post(f"{BASE}/drives", json=body, headers=org.officer), 422) == expected
    d = drive(client, org, co)
    if fields.get("scheduled_on") != day(-1):
        assert code(client.put(f"{BASE}/drives/{d['id']}", json=body, headers=org.officer), 422) == expected


def test_drive_company_must_exist_and_be_active(client, org, other_org):
    body = {"company_id": "nope", "title": "Drive", "scheduled_on": day(10)}
    assert code(client.post(f"{BASE}/drives", json=body, headers=org.officer), 404) == "not_found"
    theirs = company(client, other_org)
    r = client.post(f"{BASE}/drives", json={**body, "company_id": theirs["id"]}, headers=org.officer)
    assert code(r, 404) == "not_found"
    co = company(client, org)
    d = drive(client, org, co, schedule=False)
    ok(client.put(f"{BASE}/companies/{co['id']}", json={"name": co["name"], "active": False}, headers=org.officer))
    r = client.post(f"{BASE}/drives", json={**body, "company_id": co["id"]}, headers=org.officer)
    assert code(r, 409) == "company_inactive"
    assert code(client.post(f"{BASE}/drives/{d['id']}/schedule", headers=org.officer), 409) == "company_inactive"
    # an existing drive of an inactive company can still be edited; moving it to an inactive company cannot
    edit = {"company_id": co["id"], "title": "Renamed", "scheduled_on": day(10)}
    assert ok(client.put(f"{BASE}/drives/{d['id']}", json=edit, headers=org.officer))["title"] == "Renamed"
    other = drive(client, org, schedule=False)
    r = client.put(f"{BASE}/drives/{other['id']}", json=edit, headers=org.officer)
    assert code(r, 409) == "company_inactive"
    r = client.put(f"{BASE}/drives/{other['id']}", json={**edit, "company_id": "nope"}, headers=org.officer)
    assert code(r, 404) == "not_found"


def test_scheduling_a_drive_whose_date_passed_is_refused(client, org, clock):
    d = drive(client, org, schedule=False, scheduled_on=day(1), registration_closes_on=None)
    clock.advance(days=2)
    assert code(client.post(f"{BASE}/drives/{d['id']}/schedule", headers=org.officer), 422) == "invalid_date"


def test_reschedule_publishes_only_for_a_scheduled_drive_whose_dates_change(client, org, clock):
    co = company(client, org)
    d = drive(client, org, co, schedule=False)
    body = {
        "company_id": co["id"],
        "title": "Campus drive",
        "scheduled_on": day(12),
        "registration_closes_on": day(7),
    }
    ok(client.put(f"{BASE}/drives/{d['id']}", json=body, headers=org.officer))
    assert outbox(org.id, "placement-career.drive.rescheduled") == []  # a draft is not announced yet
    ok(client.post(f"{BASE}/drives/{d['id']}/schedule", headers=org.officer))
    ok(client.put(f"{BASE}/drives/{d['id']}", json={**body, "venue": "Hall B"}, headers=org.officer))
    assert outbox(org.id, "placement-career.drive.rescheduled") == []  # same dates
    moved = ok(client.put(f"{BASE}/drives/{d['id']}", json={**body, "ends_on": day(13)}, headers=org.officer))
    assert moved["ends_on"] == day(13) and moved["status"] == "scheduled"
    [ev] = outbox(org.id, "placement-career.drive.rescheduled")
    assert ev.payload == {"organisation_id": org.id, "drive_id": d["id"], "scheduled_on": day(12), "ends_on": day(13)}
    # once the date has passed it can still be corrected, as long as the date itself does not change
    clock.advance(days=20)
    fixed = ok(
        client.put(f"{BASE}/drives/{d['id']}", json={**body, "ends_on": day(13), "title": "Fixed"}, headers=org.officer)
    )
    assert fixed["title"] == "Fixed"
    r = client.put(f"{BASE}/drives/{d['id']}", json={**body, "scheduled_on": day(15)}, headers=org.officer)
    assert code(r, 422) == "invalid_date"


def test_drive_with_openings_keeps_its_company_and_its_date_after_their_last_day(client, org):
    co = company(client, org)
    d = drive(client, org, co)
    opening(client, org, dr=d, applications_close_on=day(8))
    other = company(client, org)
    body = {"company_id": other["id"], "title": "Campus drive", "scheduled_on": day(10)}
    assert code(client.put(f"{BASE}/drives/{d['id']}", json=body, headers=org.officer), 422) == "company_mismatch"
    body = {"company_id": co["id"], "title": "Campus drive", "scheduled_on": day(7)}
    assert code(client.put(f"{BASE}/drives/{d['id']}", json=body, headers=org.officer), 422) == "close_date_after_drive"
    body["scheduled_on"] = day(8)
    assert ok(client.put(f"{BASE}/drives/{d['id']}", json=body, headers=org.officer))["scheduled_on"] == day(8)
    empty = drive(client, org, co, schedule=False)
    moved = ok(
        client.put(f"{BASE}/drives/{empty['id']}", json={**body, "company_id": other["id"]}, headers=org.officer)
    )
    assert moved["company_id"] == other["id"]


def test_cancel_a_drive_cancels_its_draft_and_open_openings(client, org):
    d = drive(client, org)
    open_one = opening(client, org, dr=d)
    draft_one = opening(client, org, dr=d, publish=False)
    closed_one = opening(client, org, dr=d)
    ok(client.post(f"{BASE}/openings/{closed_one['id']}/close", headers=org.officer))
    assert code(client.post(f"{BASE}/drives/{d['id']}/cancel", json={"reason": " "}, headers=org.officer), 422) == (
        "reason_required"
    )
    assert code(client.post(f"{BASE}/drives/{d['id']}/cancel", headers=org.officer), 422) == "reason_required"
    out = ok(client.post(f"{BASE}/drives/{d['id']}/cancel", json={"reason": "Company postponed"}, headers=org.officer))
    assert out["status"] == "cancelled" and out["cancel_reason"] == "Company postponed"
    statuses = {
        o["id"]: o["status"]
        for o in ok(client.get(f"{BASE}/openings", params={"drive_id": d["id"]}, headers=org.officer))["items"]
    }
    assert statuses == {open_one["id"]: "cancelled", draft_one["id"]: "cancelled", closed_one["id"]: "closed"}
    [ev] = outbox(org.id, "placement-career.drive.cancelled")
    assert ev.payload == {
        "organisation_id": org.id,
        "drive_id": d["id"],
        "company_id": d["company_id"],
        "reason": "Company postponed",
    }
    cancelled = outbox(org.id, "placement-career.opening.cancelled")
    assert [e.payload for e in cancelled] == [
        {"organisation_id": org.id, "opening_id": open_one["id"], "reason": "Company postponed"}
    ]


def test_drive_with_an_application_cannot_be_cancelled_even_withdrawn(client, org):
    d = drive(client, org)
    o = opening(client, org, dr=d)
    a = ok(apply(client, org, o), 201)
    ok(client.post(f"{BASE}/me/applications/{a['id']}/withdraw", headers=org.student))
    r = client.post(f"{BASE}/drives/{d['id']}/cancel", json={"reason": "x"}, headers=org.officer)
    assert code(r, 409) == "has_applications"


def test_drive_permissions(client, org):
    d = drive(client, org)
    body = {"company_id": d["company_id"], "title": "x", "scheduled_on": day(10)}
    for who in ("viewer", "student", "nobody"):
        h = org.headers[who]
        assert code(client.post(f"{BASE}/drives", json=body, headers=h), 403) == "forbidden"
        assert code(client.put(f"{BASE}/drives/{d['id']}", json=body, headers=h), 403) == "forbidden"
        for action in ("schedule", "complete", "cancel"):
            assert code(client.post(f"{BASE}/drives/{d['id']}/{action}", json={"reason": "x"}, headers=h), 403) == (
                "forbidden"
            )
    assert code(client.get(f"{BASE}/drives", headers=org.nobody), 403) == "forbidden"
    assert code(client.get(f"{BASE}/drives/{d['id']}", headers=org.nobody), 403) == "forbidden"
    assert ok(client.post(f"{BASE}/drives", json=body, headers=org.coordinator), 201)["status"] == "draft"


def test_missing_drive_is_404_for_every_operation(client, org):
    co = company(client, org)
    body = {"company_id": co["id"], "title": "x", "scheduled_on": day(10)}
    assert code(client.get(f"{BASE}/drives/nope", headers=org.officer), 404) == "not_found"
    assert code(client.put(f"{BASE}/drives/nope", json=body, headers=org.officer), 404) == "not_found"
    for action in ("schedule", "complete", "cancel"):
        assert code(client.post(f"{BASE}/drives/nope/{action}", json={"reason": "x"}, headers=org.officer), 404) == (
            "not_found"
        )
