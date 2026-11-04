"""Job openings (stories O4, O5, S1, S2): draft -> open -> closed, or cancelled; in a drive or on their own;
visibility and the CTC; every error code of /openings."""

import pytest
from pc_support import BASE, apply, code, company, day, drive, ok, opening, outbox


def test_post_publish_and_close_an_opening_on_its_own(client, org):
    co = company(client, org)
    o = opening(client, org, co=co, publish=False, positions=None, ctc_per_annum="1200000")
    assert o["status"] == "draft" and o["drive_id"] is None and o["drive"] is None and o["published_at"] is None
    assert o["ctc_per_annum"] == "1200000.00" and o["positions"] is None and o["applications_count"] == 0
    assert o["eligibility"] == {
        "programmes": [],
        "graduating_years": [],
        "min_cgpa": 7.0,
        "max_active_backlogs": 0,
        "notes": None,
    }
    o = ok(client.post(f"{BASE}/openings/{o['id']}/publish", headers=org.officer))
    assert o["status"] == "open" and o["published_at"].startswith("2026-11-03T06:00")
    [ev] = outbox(org.id, "placement-career.opening.published")
    assert ev.payload == {
        "organisation_id": org.id,
        "opening_id": o["id"],
        "company_id": co["id"],
        "drive_id": None,
        "applications_close_on": day(5),
    }
    assert code(client.post(f"{BASE}/openings/{o['id']}/publish", headers=org.officer), 409) == "not_draft"
    o = ok(client.post(f"{BASE}/openings/{o['id']}/close", headers=org.officer))
    assert o["status"] == "closed"
    [ev] = outbox(org.id, "placement-career.opening.closed")
    assert ev.payload == {"organisation_id": org.id, "opening_id": o["id"]}
    assert code(client.post(f"{BASE}/openings/{o['id']}/close", headers=org.officer), 409) == "not_open"
    body = {"company_id": co["id"], "title": "x", "applications_close_on": day(5)}
    assert code(client.put(f"{BASE}/openings/{o['id']}", json=body, headers=org.officer), 409) == "not_editable"
    r = client.post(f"{BASE}/openings/{o['id']}/cancel", json={"reason": "x"}, headers=org.officer)
    assert code(r, 409) == "not_cancellable"


def test_opening_in_a_drive_shows_the_drive_and_waits_for_it(client, org):
    d = drive(client, org, schedule=False)
    o = opening(client, org, dr=d, publish=False)
    assert o["drive"] == {
        "id": d["id"],
        "title": d["title"],
        "scheduled_on": day(10),
        "venue": "Main auditorium",
        "eligibility": d["eligibility"],
    }
    assert code(client.post(f"{BASE}/openings/{o['id']}/publish", headers=org.officer), 409) == "drive_not_scheduled"
    ok(client.post(f"{BASE}/drives/{d['id']}/schedule", headers=org.officer))
    published = ok(client.post(f"{BASE}/openings/{o['id']}/publish", headers=org.officer))
    assert published["status"] == "open"
    assert outbox(org.id, "placement-career.opening.published")[0].payload["drive_id"] == d["id"]


def test_opening_rules_against_its_drive(client, org):
    d = drive(client, org)
    other = company(client, org)
    body = {"company_id": other["id"], "drive_id": d["id"], "title": "Analyst", "applications_close_on": day(5)}
    assert code(client.post(f"{BASE}/openings", json=body, headers=org.officer), 422) == "company_mismatch"
    body = {**body, "company_id": d["company_id"], "applications_close_on": day(11)}
    assert code(client.post(f"{BASE}/openings", json=body, headers=org.officer), 422) == "close_date_after_drive"
    body["applications_close_on"] = day(10)  # on the drive date itself is fine
    ok(client.post(f"{BASE}/openings", json=body, headers=org.officer), 201)
    body["drive_id"] = "nope"
    assert code(client.post(f"{BASE}/openings", json=body, headers=org.officer), 404) == "not_found"
    done = drive(client, org, schedule=False)
    ok(client.post(f"{BASE}/drives/{done['id']}/cancel", json={"reason": "x"}, headers=org.officer))
    body = {**body, "company_id": done["company_id"], "drive_id": done["id"], "applications_close_on": day(5)}
    assert code(client.post(f"{BASE}/openings", json=body, headers=org.officer), 409) == "drive_not_open_for_openings"


def test_completed_drive_takes_no_new_openings(client, org, clock):
    d = drive(client, org)
    clock.advance(days=10)
    ok(client.post(f"{BASE}/drives/{d['id']}/complete", headers=org.officer))
    body = {"company_id": d["company_id"], "drive_id": d["id"], "title": "Late", "applications_close_on": day(10)}
    assert code(client.post(f"{BASE}/openings", json=body, headers=org.officer), 409) == "drive_not_open_for_openings"


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"title": ""}, "invalid_title"),
        ({"ctc_per_annum": "-5"}, "invalid_amount"),
        ({"ctc_per_annum": "12.345"}, "invalid_amount"),
        ({"ctc_per_annum": "abc"}, "invalid_amount"),
        ({"ctc_per_annum": 500000}, "invalid_amount"),
        ({"ctc_per_annum": "1" * 13}, "invalid_amount"),
        ({"positions": 0}, "invalid_positions"),
        # caps the code enforces: an integer too large for the column is 422, never a 500
        ({"positions": 10001}, "invalid_positions"),
        ({"positions": 3_000_000_000}, "invalid_positions"),
        ({"positions": 2**64}, "invalid_positions"),
        ({"eligibility": {"graduating_years": [2027, 1899]}}, "invalid_eligibility"),
        ({"eligibility": {"graduating_years": [2101]}}, "invalid_eligibility"),
        ({"eligibility": {"graduating_years": [3_000_000_000]}}, "invalid_eligibility"),
        ({"eligibility": {"graduating_years": [2**64]}}, "invalid_eligibility"),
        ({"eligibility": {"max_active_backlogs": 101}}, "invalid_eligibility"),
        ({"eligibility": {"max_active_backlogs": 2**64}}, "invalid_eligibility"),
        ({"applications_close_on": day(-1)}, "invalid_date"),
        ({"eligibility": {"max_active_backlogs": -2}}, "invalid_eligibility"),
    ],
)
def test_invalid_opening_values(client, org, fields, expected):
    co = company(client, org)
    body = {"company_id": co["id"], "title": "Analyst", "applications_close_on": day(5), **fields}
    assert code(client.post(f"{BASE}/openings", json=body, headers=org.officer), 422) == expected
    o = opening(client, org, co=co)
    assert code(client.put(f"{BASE}/openings/{o['id']}", json=body, headers=org.officer), 422) == expected


def test_largest_values_the_caps_allow(client, org):
    eligibility = {"graduating_years": [1900, 2100], "max_active_backlogs": 100}
    o = opening(client, org, positions=10000, eligibility=eligibility)
    assert o["positions"] == 10000
    assert o["eligibility"]["graduating_years"] == [1900, 2100] and o["eligibility"]["max_active_backlogs"] == 100


def test_edit_cannot_move_an_opening_into_a_cancelled_drive(client, org):
    """update_opening locks the drive before the opening and checks its status after the lock: a drive cancelled
    (with its openings) is never a destination, so no open opening is left in it."""
    co = company(client, org)
    o = opening(client, org, co=co)
    d = drive(client, org, co)
    sibling = opening(client, org, dr=d)
    ok(client.post(f"{BASE}/drives/{d['id']}/cancel", json={"reason": "Company withdrew"}, headers=org.officer))
    body = {"company_id": co["id"], "drive_id": d["id"], "title": "Analyst", "applications_close_on": day(5)}
    r = client.put(f"{BASE}/openings/{o['id']}", json=body, headers=org.officer)
    assert code(r, 409) == "drive_not_open_for_openings"
    assert ok(client.get(f"{BASE}/openings/{o['id']}", headers=org.officer))["drive_id"] is None
    assert ok(client.get(f"{BASE}/openings/{sibling['id']}", headers=org.officer))["status"] == "cancelled"


def test_edit_cannot_move_the_last_day_past_the_drive_date(client, org):
    """The drive's date is read under its lock, so a drive moved earlier at the same time is seen as moved."""
    d = drive(client, org)
    o = opening(client, org, dr=d, applications_close_on=day(8))
    later = ok(client.put(f"{BASE}/drives/{d['id']}", json={**d, "scheduled_on": day(9)}, headers=org.officer))
    assert later["scheduled_on"] == day(9)
    body = {"company_id": d["company_id"], "drive_id": d["id"], "title": "Analyst", "applications_close_on": day(10)}
    r = client.put(f"{BASE}/openings/{o['id']}", json=body, headers=org.officer)
    assert code(r, 422) == "close_date_after_drive"
    body["applications_close_on"] = day(9)  # on the drive date itself is fine
    edited = ok(client.put(f"{BASE}/openings/{o['id']}", json=body, headers=org.officer))
    assert edited["applications_close_on"] == day(9)
    r = client.put(f"{BASE}/drives/{d['id']}", json={**d, "scheduled_on": day(8)}, headers=org.officer)
    assert code(r, 422) == "close_date_after_drive"


def test_opening_company_must_exist_and_be_active(client, org):
    body = {"company_id": "nope", "title": "Analyst", "applications_close_on": day(5)}
    assert code(client.post(f"{BASE}/openings", json=body, headers=org.officer), 404) == "not_found"
    co = company(client, org)
    draft = opening(client, org, co=co, publish=False)
    live = opening(client, org, co=co)
    ok(client.put(f"{BASE}/companies/{co['id']}", json={"name": co["name"], "active": False}, headers=org.officer))
    body["company_id"] = co["id"]
    assert code(client.post(f"{BASE}/openings", json=body, headers=org.officer), 409) == "company_inactive"
    assert code(client.post(f"{BASE}/openings/{draft['id']}/publish", headers=org.officer), 409) == "company_inactive"
    # existing openings continue: still editable, closable and open to students
    assert ok(client.put(f"{BASE}/openings/{live['id']}", json=body, headers=org.officer))["title"] == "Analyst"
    other = opening(client, org)
    r = client.put(f"{BASE}/openings/{other['id']}", json=body, headers=org.officer)
    assert code(r, 409) == "company_inactive"
    assert ok(apply(client, org, live), 201)["status"] == "applied"


def test_edit_an_open_opening(client, org, clock):
    co = company(client, org)
    o = opening(client, org, co=co)
    body = {
        "company_id": co["id"],
        "title": "Senior analyst",
        "applications_close_on": day(5),
        "ctc_per_annum": "700000.5",
        "positions": 2,
    }
    edited = ok(client.put(f"{BASE}/openings/{o['id']}", json=body, headers=org.officer))
    assert (edited["title"], edited["ctc_per_annum"], edited["positions"], edited["status"]) == (
        "Senior analyst",
        "700000.50",
        2,
        "open",
    )
    clock.advance(days=7)  # past its last day: it can still be corrected while the date does not change
    assert ok(client.put(f"{BASE}/openings/{o['id']}", json={**body, "location": "Pune"}, headers=org.officer))
    r = client.put(f"{BASE}/openings/{o['id']}", json={**body, "applications_close_on": day(6)}, headers=org.officer)
    assert code(r, 422) == "invalid_date"
    assert code(client.post(f"{BASE}/openings", json=body, headers=org.officer), 422) == "invalid_date"


def test_company_and_drive_do_not_change_once_it_has_applications(client, org):
    d = drive(client, org)
    o = opening(client, org, dr=d)
    ok(apply(client, org, o), 201)
    other = company(client, org)
    base = {"company_id": d["company_id"], "drive_id": d["id"], "title": "x", "applications_close_on": day(5)}
    r = client.put(
        f"{BASE}/openings/{o['id']}", json={**base, "company_id": other["id"], "drive_id": None}, headers=org.officer
    )
    assert code(r, 409) == "has_applications"
    r = client.put(f"{BASE}/openings/{o['id']}", json={**base, "drive_id": None}, headers=org.officer)
    assert code(r, 409) == "has_applications"
    assert ok(client.put(f"{BASE}/openings/{o['id']}", json=base, headers=org.officer))["title"] == "x"


def test_move_an_opening_between_drives(client, org):
    co = company(client, org)
    alone = opening(client, org, co=co)
    d = drive(client, org, co)
    draft_drive = drive(client, org, co, schedule=False)
    body = {"company_id": co["id"], "title": "Analyst", "applications_close_on": day(5)}
    r = client.put(f"{BASE}/openings/{alone['id']}", json={**body, "drive_id": draft_drive["id"]}, headers=org.officer)
    assert code(r, 409) == "drive_not_scheduled"  # an open opening moves only into a scheduled drive
    moved = ok(client.put(f"{BASE}/openings/{alone['id']}", json={**body, "drive_id": d["id"]}, headers=org.officer))
    assert moved["drive_id"] == d["id"] and moved["drive"]["id"] == d["id"]
    r = client.put(f"{BASE}/openings/{alone['id']}", json={**body, "drive_id": "nope"}, headers=org.officer)
    assert code(r, 404) == "not_found"
    r = client.put(f"{BASE}/openings/{alone['id']}", json={**body, "company_id": "nope"}, headers=org.officer)
    assert code(r, 404) == "not_found"
    gone = drive(client, org, co, schedule=False)
    ok(client.post(f"{BASE}/drives/{gone['id']}/cancel", json={"reason": "x"}, headers=org.officer))
    r = client.put(f"{BASE}/openings/{alone['id']}", json={**body, "drive_id": gone["id"]}, headers=org.officer)
    assert code(r, 409) == "drive_not_open_for_openings"
    out = ok(client.put(f"{BASE}/openings/{alone['id']}", json={**body, "drive_id": None}, headers=org.officer))
    assert out["drive_id"] is None


def test_publishing_after_the_last_day_is_refused(client, org, clock):
    o = opening(client, org, publish=False, applications_close_on=day(1))
    clock.advance(days=2)
    assert code(client.post(f"{BASE}/openings/{o['id']}/publish", headers=org.officer), 422) == "invalid_date"


def test_cancel_an_opening(client, org):
    draft = opening(client, org, publish=False)
    out = ok(
        client.post(
            f"{BASE}/openings/{draft['id']}/cancel", json={"reason": "Withdrawn by company"}, headers=org.officer
        )
    )
    assert out["status"] == "cancelled" and out["cancel_reason"] == "Withdrawn by company"
    assert outbox(org.id, "placement-career.opening.cancelled") == []  # a draft was never announced
    live = opening(client, org)
    assert code(client.post(f"{BASE}/openings/{live['id']}/cancel", json={}, headers=org.officer), 422) == (
        "reason_required"
    )
    ok(client.post(f"{BASE}/openings/{live['id']}/cancel", json={"reason": "Filled"}, headers=org.officer))
    [ev] = outbox(org.id, "placement-career.opening.cancelled")
    assert ev.payload == {"organisation_id": org.id, "opening_id": live["id"], "reason": "Filled"}
    taken = opening(client, org)
    a = ok(apply(client, org, taken), 201)
    ok(client.post(f"{BASE}/me/applications/{a['id']}/withdraw", headers=org.student))
    r = client.post(f"{BASE}/openings/{taken['id']}/cancel", json={"reason": "x"}, headers=org.officer)
    assert code(r, 409) == "has_applications"


def test_visibility_and_applications_count(client, org):
    co = company(client, org)
    live = opening(client, org, co=co)
    draft = opening(client, org, co=co, publish=False)
    cancelled = opening(client, org, co=co, publish=False)
    ok(client.post(f"{BASE}/openings/{cancelled['id']}/cancel", json={"reason": "x"}, headers=org.officer))
    ok(apply(client, org, live), 201)
    officer = ok(client.get(f"{BASE}/openings", headers=org.officer))["items"]
    assert [o["id"] for o in officer] == [cancelled["id"], draft["id"], live["id"]]  # newest first
    assert officer[2]["applications_count"] == 1
    for who in ("viewer", "student", "student2"):
        items = ok(client.get(f"{BASE}/openings", headers=org.headers[who]))["items"]
        assert [o["id"] for o in items] == [live["id"]], who
        assert items[0]["ctc_per_annum"] == "650000.00" and items[0]["applications_count"] is None
        assert "contact_email" not in items[0]["company"]
        for hidden in (draft, cancelled):
            assert code(client.get(f"{BASE}/openings/{hidden['id']}", headers=org.headers[who]), 404) == "not_found"
    assert ok(client.get(f"{BASE}/openings/{live['id']}", headers=org.student))["id"] == live["id"]


def test_opening_filters_and_pages(client, org):
    co, other = company(client, org), company(client, org)
    d = drive(client, org, co)
    in_drive = opening(client, org, dr=d)
    alone = opening(client, org, co=co)
    elsewhere = opening(client, org, co=other, publish=False)

    def ids(**params):
        return [o["id"] for o in ok(client.get(f"{BASE}/openings", params=params, headers=org.officer))["items"]]

    assert ids(drive_id=d["id"]) == [in_drive["id"]]
    assert ids(company_id=co["id"]) == [alone["id"], in_drive["id"]]
    assert ids(without_drive=True) == [elsewhere["id"], alone["id"]]
    assert ids(without_drive=False) == [in_drive["id"]]
    assert ids(status="draft") == [elsewhere["id"]]
    first = ok(client.get(f"{BASE}/openings", params={"limit": 2}, headers=org.officer))
    rest = ok(client.get(f"{BASE}/openings", params={"limit": 2, "cursor": first["next_cursor"]}, headers=org.officer))
    assert [o["id"] for o in first["items"] + rest["items"]] == ids() and rest["next_cursor"] is None
    assert code(client.get(f"{BASE}/openings", params={"cursor": "-3"}, headers=org.officer), 400) == "invalid_cursor"


def test_opening_permissions(client, org):
    o = opening(client, org)
    body = {"company_id": o["company_id"], "title": "x", "applications_close_on": day(5)}
    for who in ("viewer", "student", "nobody"):
        h = org.headers[who]
        assert code(client.post(f"{BASE}/openings", json=body, headers=h), 403) == "forbidden"
        assert code(client.put(f"{BASE}/openings/{o['id']}", json=body, headers=h), 403) == "forbidden"
        for action in ("publish", "close", "cancel"):
            r = client.post(f"{BASE}/openings/{o['id']}/{action}", json={"reason": "x"}, headers=h)
            assert code(r, 403) == "forbidden"
    assert code(client.get(f"{BASE}/openings", headers=org.nobody), 403) == "forbidden"
    assert code(client.get(f"{BASE}/openings/{o['id']}", headers=org.nobody), 403) == "forbidden"


def test_missing_opening_is_404_for_every_operation(client, org):
    co = company(client, org)
    body = {"company_id": co["id"], "title": "x", "applications_close_on": day(5)}
    assert code(client.get(f"{BASE}/openings/nope", headers=org.officer), 404) == "not_found"
    assert code(client.put(f"{BASE}/openings/nope", json=body, headers=org.officer), 404) == "not_found"
    for action in ("publish", "close", "cancel"):
        r = client.post(f"{BASE}/openings/nope/{action}", json={"reason": "x"}, headers=org.officer)
        assert code(r, 404) == "not_found"
