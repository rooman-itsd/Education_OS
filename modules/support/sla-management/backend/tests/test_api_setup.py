"""Calendars and policies through the HTTP API: create, read, update, deactivate, the 409s and 422s of the contract,
and values too big for their columns or for date arithmetic."""

from conftest import CATEGORY, LEAD, OFFICE_HOURS, audit, calendar_body, policy_body

MAX = 366 * 24 * 60


# ---------------------------------------------------------------- calendars


def test_create_read_list_calendar(desk):
    body = calendar_body(
        name="Office",
        time_zone="Asia/Kolkata",
        always_open=False,
        working_hours=OFFICE_HOURS,
        holidays=[{"date": "2026-12-25", "name": "Christmas"}],
    )
    cal = desk.ok(desk.post("/calendars", body))
    assert (cal["name"], cal["time_zone"], cal["active"], cal["organisation_id"]) == (
        "Office",
        "Asia/Kolkata",
        True,
        desk.org.id,
    )
    assert cal["holidays"] == [{"date": "2026-12-25", "name": "Christmas"}]
    assert cal["working_hours"][0] == {"weekday": 1, "start": "09:00", "end": "17:00"}
    assert desk.ok(desk.get(f"/calendars/{cal['id']}", desk.viewer)) == cal
    assert desk.ok(desk.get(f"/calendars/{cal['id'].upper()}", desk.viewer)) == cal
    assert [c["id"] for c in desk.ok(desk.get("/calendars?active=true", desk.viewer))] == [cal["id"]]
    assert desk.ok(desk.get("/calendars?active=false")) == []
    assert audit(desk.org.id, cal["id"]) == ["calendar.created"]


def test_bad_calendars_are_422(desk):
    for over, code in [
        ({"time_zone": "Mars/Olympus"}, "unknown_time_zone"),
        ({"always_open": False}, "working_hours_required"),
        (
            {"always_open": False, "working_hours": [{"weekday": 1, "start": "10:00", "end": "09:00"}]},
            "end_before_start",
        ),
        (
            {
                "always_open": False,
                "working_hours": [
                    {"weekday": 2, "start": "09:00", "end": "13:00"},
                    {"weekday": 2, "start": "12:59", "end": "14:00"},
                ],
            },
            "overlapping_hours",
        ),
        ({"always_open": False, "working_hours": [{"weekday": 1, "start": "09:00", "end": "24:30"}]}, "invalid_time"),
        ({"holidays": [{"date": "0001-01-01", "name": "x"}]}, "invalid_holiday"),
        ({"holidays": [{"date": "9999-12-31", "name": "x"}]}, "invalid_holiday"),
    ]:
        response = desk.post("/calendars", calendar_body(**over))
        assert (response.status_code, response.json()["detail"]["code"]) == (422, code), over
    for over in [
        {"name": "n" * 81},
        {"time_zone": "z" * 65},
        {"working_hours": [{"weekday": 8, "start": "09:00", "end": "10:00"}]},
        {"working_hours": [{"weekday": 10**11, "start": "09:00", "end": "10:00"}]},
        {"working_hours": [{"weekday": 1, "start": "9:00", "end": "10:00"}]},
        {"working_hours": [{"weekday": 1, "start": "09:00", "end": "10:00"}] * 71},
        {"holidays": [{"date": "2026-12-25", "name": "h" * 81}]},
        {"unknown": True},
    ]:
        assert desk.post("/calendars", calendar_body(**over)).status_code == 422, over


def test_update_calendar_only_changes_what_is_sent(desk):
    cal = desk.calendar()
    renamed = desk.ok(desk.patch(f"/calendars/{cal['id']}", {"name": "24x7"}))
    assert (renamed["name"], renamed["time_zone"], renamed["always_open"]) == ("24x7", "UTC", True)
    office = desk.ok(desk.patch(f"/calendars/{cal['id']}", {"always_open": False, "working_hours": OFFICE_HOURS}))
    assert office["always_open"] is False and len(office["working_hours"]) == 5
    assert desk.patch(f"/calendars/{cal['id']}", {"working_hours": []}).status_code == 422
    assert desk.patch(f"/calendars/{cal['id']}", {"time_zone": "Nowhere/City"}).status_code == 422
    assert desk.ok(desk.patch(f"/calendars/{cal['id']}", calendar_body(name="Full body")))["name"] == "Full body"


def test_a_calendar_used_by_an_active_policy_cannot_be_deactivated(desk):
    cal = desk.calendar()
    policy = desk.policy(cal["id"])
    refused = desk.patch(f"/calendars/{cal['id']}", {"active": False})
    assert (refused.status_code, refused.json()["detail"]["code"]) == (409, "calendar_in_use")
    desk.ok(desk.patch(f"/policies/{policy['id']}", {"active": False}))
    assert desk.ok(desk.patch(f"/calendars/{cal['id']}", {"active": False}))["active"] is False
    assert audit(desk.org.id, cal["id"])[-1] == "calendar.deactivated"


def test_a_calendar_change_that_makes_a_target_unreachable_is_422(desk):
    cal = desk.calendar()
    desk.policy(cal["id"], response_target_minutes=MAX, resolution_target_minutes=MAX)
    sparse = {"always_open": False, "working_hours": [{"weekday": 1, "start": "09:00", "end": "09:01"}]}
    refused = desk.patch(f"/calendars/{cal['id']}", sparse)
    assert (refused.status_code, refused.json()["detail"]["code"]) == (422, "target_unreachable")


def test_unknown_calendar_is_404(desk):
    missing = "99999999-9999-4999-8999-999999999999"
    assert desk.get(f"/calendars/{missing}").status_code == 404
    assert desk.patch(f"/calendars/{missing}", {"name": "x"}).status_code == 404
    assert desk.get("/calendars/not-a-uuid").status_code == 422


# ---------------------------------------------------------------- policies


def test_create_policy_with_defaults(desk, monkeypatch):
    cal = desk.calendar()
    monkeypatch.setenv("SLA_MANAGEMENT_DEFAULT_WARNING_PERCENT", "80")
    body = policy_body(cal["id"], category_id=CATEGORY.upper())
    del body["warning_percent"], body["escalation_levels"]
    policy = desk.ok(desk.post("/policies", body))
    assert policy["warning_percent"] == 80
    assert policy["pause_on_hold_reasons"] == ["waiting_requester", "waiting_third_party"]
    assert (policy["escalation_levels"], policy["category_id"], policy["active"]) == ([], CATEGORY, True)
    assert desk.ok(desk.get(f"/policies/{policy['id']}", desk.viewer)) == policy
    assert audit(desk.org.id, policy["id"]) == ["policy.created"]
    listed = desk.ok(desk.get(f"/policies?priority=high&category_id={CATEGORY}&active=true", desk.viewer))
    assert [p["id"] for p in listed] == [policy["id"]]
    assert desk.ok(desk.get("/policies?priority=low")) == []


def test_one_active_policy_per_priority_and_category(desk):
    cal = desk.calendar()["id"]
    every = desk.policy(cal)
    duplicate = desk.post("/policies", policy_body(cal, name="Again"))
    assert (duplicate.status_code, duplicate.json()["detail"]["code"]) == (409, "duplicate_policy")
    desk.policy(cal, category_id=CATEGORY)  # a category is another pair
    inactive = desk.policy(cal, name="Spare", active=False)  # an inactive one never counts
    refused = desk.patch(f"/policies/{inactive['id']}", {"active": True})
    assert refused.status_code == 409
    desk.ok(desk.patch(f"/policies/{every['id']}", {"active": False}))
    assert desk.ok(desk.patch(f"/policies/{inactive['id']}", {"active": True}))["active"] is True
    moved = desk.patch(f"/policies/{inactive['id']}", {"category_id": CATEGORY})
    assert moved.status_code == 409


def test_policy_rules_are_422(desk):
    cal = desk.calendar()["id"]
    inactive = desk.calendar(name="Old", active=False)["id"]
    levels = [{"level": n, "after_breach_minutes": n} for n in range(1, 5)]
    for over, code in [
        ({"response_target_minutes": 300, "resolution_target_minutes": 200}, "resolution_before_response"),
        ({"calendar_id": inactive}, "inactive_calendar"),
        ({"calendar_id": "99999999-9999-4999-8999-999999999999"}, "unknown_calendar"),
        ({"escalation_levels": levels}, "too_many_escalation_levels"),
        ({"escalation_levels": [{"level": 2, "after_breach_minutes": 0}]}, "escalation_levels_out_of_order"),
    ]:
        response = desk.post("/policies", {**policy_body(cal), **over})
        assert (response.status_code, response.json()["detail"]["code"]) == (422, code), over


def test_too_many_levels_follows_the_setting(desk, monkeypatch):
    cal = desk.calendar()["id"]
    monkeypatch.setenv("SLA_MANAGEMENT_MAX_ESCALATION_LEVELS", "1")
    assert desk.post("/policies", policy_body(cal)).status_code == 422
    monkeypatch.setenv("SLA_MANAGEMENT_MAX_ESCALATION_LEVELS", "5")
    desk.policy(cal)


def test_values_too_big_for_their_columns_are_a_422_not_a_500(desk):
    cal = desk.calendar()["id"]
    policy = desk.policy(cal, priority="low")
    for over in [
        {"response_target_minutes": MAX + 1},
        {"resolution_target_minutes": 10**11},
        {"response_target_minutes": 2**63},
        {"response_target_minutes": 0},
        {"warning_percent": 100},
        {"warning_percent": 0},
        {"name": "n" * 81},
        {"priority": "high,low"},
        {"category_id": "not-a-uuid"},
        {"pause_on_hold_reasons": ["waiting_forever"]},
        {"escalation_levels": [{"level": 1, "after_breach_minutes": MAX + 1}]},
        {"escalation_levels": [{"level": 10**11, "after_breach_minutes": 0}]},
        {"escalation_levels": [{"level": 1, "after_breach_minutes": 0, "notify_person_ids": [LEAD] * 51}]},
        {"escalation_levels": [{"level": 1, "after_breach_minutes": 0, "notify_person_ids": ["x"]}]},
    ]:
        assert desk.post("/policies", policy_body(cal, **over)).status_code == 422, over
        assert desk.patch(f"/policies/{policy['id']}", over).status_code == 422, over
    largest = desk.policy(
        cal, priority="urgent", response_target_minutes=MAX, resolution_target_minutes=MAX, warning_percent=99
    )
    assert largest["resolution_target_minutes"] == MAX


def test_a_target_the_calendar_cannot_reach_is_422(desk):
    sparse = desk.calendar(always_open=False, working_hours=[{"weekday": 1, "start": "09:00", "end": "09:01"}])
    refused = desk.post(
        "/policies", policy_body(sparse["id"], response_target_minutes=MAX, resolution_target_minutes=MAX)
    )
    assert (refused.status_code, refused.json()["detail"]["code"]) == (422, "target_unreachable")


def test_update_policy_keeps_unsent_fields(desk):
    policy = desk.policy()
    changed = desk.ok(desk.patch(f"/policies/{policy['id']}", {"response_target_minutes": 30, "category_id": None}))
    assert (changed["response_target_minutes"], changed["resolution_target_minutes"]) == (30, 240)
    assert changed["escalation_levels"] == policy["escalation_levels"]
    bad = desk.patch(f"/policies/{policy['id']}", {"response_target_minutes": 500})
    assert (bad.status_code, bad.json()["detail"]["code"]) == (422, "resolution_before_response")
    assert desk.patch("/policies/99999999-9999-4999-8999-999999999999", {"name": "x"}).status_code == 404
    assert audit(desk.org.id, policy["id"]) == ["policy.created", "policy.updated"]


def test_running_clocks_keep_their_targets_when_the_policy_changes(desk):
    policy = desk.policy()
    ticket = desk.ticket()
    desk.ok(desk.patch(f"/policies/{policy['id']}", {"response_target_minutes": 10}))
    assert desk.clocks(ticket)["response"]["target_minutes"] == 60
    assert desk.clocks(desk.ticket())["response"]["target_minutes"] == 10


def test_patch_escalation_levels_get_the_contract_defaults(desk):
    """A PATCH body carries only the keys sent; the stored levels are still whole (a probe found a 500 here)."""
    policy = desk.policy()
    changed = desk.ok(
        desk.patch(f"/policies/{policy['id']}", {"escalation_levels": [{"level": 1, "after_breach_minutes": 5}]})
    )
    assert changed["escalation_levels"] == [
        {"level": 1, "after_breach_minutes": 5, "notify_assignee": True, "notify_person_ids": []}
    ]
