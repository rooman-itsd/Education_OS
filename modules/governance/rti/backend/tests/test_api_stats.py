"""The deadline list behind the widget rti.nearing-deadline (GET /stats/nearing-deadline) and the profile roles of
the dashboards that show it."""

import pytest
from conftest import Desk, days


def stats(desk: Desk, headers: dict | None = None) -> dict:
    return desk.ok(desk.get("/stats/nearing-deadline", headers or desk.viewer))


def test_counts_overdue_and_due_soon_with_the_soonest_listed_first(desk):
    late = desk.request(received_on=days(-40))  # due 10 days ago
    just_late = desk.request(received_on=days(-31))  # due yesterday
    today = desk.request(received_on=days(-30))  # due today: not yet overdue
    edge = desk.assigned(received_on=days(-23))  # due in exactly 7 days: inside the window
    beyond = desk.request(received_on=days(-22))  # due in 8 days: outside
    desk.request(received_on=days(0))  # due in 30 days
    s = stats(desk)
    assert (s["within_days"], s["overdue"], s["due_soon"]) == (7, 2, 2)
    assert [i["request_id"] for i in s["items"]] == [late["id"], just_late["id"], today["id"], edge["id"]]
    assert beyond["id"] not in {i["request_id"] for i in s["items"]}
    first, second, third, fourth = s["items"]
    assert (first["overdue"], second["overdue"], third["overdue"], fourth["overdue"]) == (True, True, False, False)
    assert (first["number"], first["status"]) == (late["number"], "received") and fourth["status"] == "assigned"
    assert first["due_at"] == "2026-10-26T18:29:59+00:00" and third["due_at"] == "2026-11-05T18:29:59+00:00"
    assert [i["due_at"] for i in s["items"]] == sorted(i["due_at"] for i in s["items"])


def test_a_request_that_was_answered_or_transferred_leaves_the_list(desk):
    answered = desk.assigned(received_on=days(-40))
    moved = desk.request(received_on=days(-40))
    desk.request(received_on=days(-40))
    assert stats(desk)["overdue"] == 3
    desk.respond(answered["id"])
    desk.ok(
        desk.post(
            f"/requests/{moved['id']}/transfer",
            {"authority_name": "Council", "transferred_on": days(0), "reason": "Wrong body."},
        )
    )
    assert stats(desk)["overdue"] == 1


def test_an_appeal_is_listed_with_its_own_deadline(desk, settings):
    settings(appeal_decide_days=5)
    r = desk.appealed()  # filed today, decision due in 5 days
    s = stats(desk)
    assert (s["due_soon"], s["overdue"]) == (1, 0)
    (item,) = s["items"]
    assert (item["request_id"], item["status"], item["overdue"]) == (r["id"], "appealed", False)
    assert item["due_at"] == "2026-11-10T18:29:59+00:00"
    assert desk.ok(desk.get(f"/requests/{r['id']}"))["appeal"]["due_at"] == item["due_at"]


def test_an_appeal_decision_that_is_late_is_overdue(desk, settings, clock):
    from datetime import UTC, datetime

    settings(appeal_decide_days=5)
    r = desk.appealed()
    clock.set(datetime(2026, 11, 10, 18, 30, tzinfo=UTC))  # the 11th in India: the 10th was the last day
    assert stats(desk)["overdue"] == 1
    assert desk.ok(desk.get(f"/requests/{r['id']}"))["overdue"] is True
    assert [i["id"] for i in desk.ok(desk.get("/requests?overdue=true"))["items"]] == [r["id"]]


def test_the_list_holds_the_ten_soonest_but_the_counts_cover_all(desk):
    for n in range(12):
        desk.request(received_on=days(-40 - n))
    s = stats(desk)
    assert s["overdue"] == 12 and len(s["items"]) == 10
    assert s["items"][0]["due_at"] < s["items"][-1]["due_at"]


def test_the_window_is_the_setting(desk, settings):
    desk.request(received_on=days(-20))  # due in 10 days
    assert stats(desk)["due_soon"] == 0
    settings(nearing_deadline_days=10)
    s = stats(desk)
    assert (s["within_days"], s["due_soon"]) == (10, 1)


def test_without_timeline_settings_nothing_is_due(desk, settings):
    settings.unset("response_days", "appeal_decide_days")
    desk.request(received_on=days(-400))
    assert stats(desk) == {"within_days": 7, "due_soon": 0, "overdue": 0, "items": []}


def test_the_widget_carries_no_applicant_data_or_request_content(desk):
    desk.request(received_on=days(-40))
    for item in stats(desk)["items"]:
        assert set(item) == {"request_id", "number", "status", "due_at", "overdue"}


@pytest.mark.parametrize("role", ["governance", "rti-officer", "rti-appellate-authority", "rti-viewer"])
def test_the_roles_that_see_the_widget_read_it(client, org, clock, settings, role):
    """The Governance layout (platform/identity/config/dashboards/governance.yaml) lists rti.nearing-deadline and grants
    its profile role rti-officer through module_roles, so `governance` reads the endpoint; the module roles that hold
    rti:stats:read do too. The other profile roles the PRD proposes (management, org-admin, department-admin, faculty)
    are not mapped by any layout yet; that is a platform/identity change, not this module's."""
    settings(response_days=30)
    d = Desk(client, org)
    d.request(received_on=days(-40))
    _, headers = org.user(role)
    got = d.get("/stats/nearing-deadline", headers)
    assert got.status_code == 200, role
    assert got.json()["overdue"] == 1


@pytest.mark.parametrize("role", ["rti-custodian", "student"])
def test_roles_without_the_permission_are_refused(client, org, clock, role):
    _, headers = org.user(role)
    assert Desk(client, org).get("/stats/nearing-deadline", headers).status_code == 403
