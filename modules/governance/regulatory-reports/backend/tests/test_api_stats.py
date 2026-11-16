"""The statistics behind the widgets (GET /stats/due, GET /calendar) and the profile roles of the dashboards that show
them, which read through their layouts' module_roles."""

import pytest
from conftest import Desk, days


def test_due_counts_mine_by_default_and_all_with_data_read(desk):
    desk.filing(due_on=days(-2))  # overdue, the preparer's
    desk.filing(due_on=days(7))  # due soon, the preparer's
    desk.filing(due_on=days(90))  # beyond the window
    desk.filing(due_on=days(3), owner_id=desk.preparer2_id)
    mine = desk.ok(desk.get("/stats/due", desk.preparer))
    assert (mine["scope"], mine["overdue"], mine["due_soon"], mine["due_soon_days"]) == ("mine", 1, 1, 30)
    assert [s["due_on"] for s in mine["soonest"]] == sorted(s["due_on"] for s in mine["soonest"])
    assert mine["soonest"][0]["overdue"] is True
    everyone = desk.ok(desk.get("/stats/due?scope=all", desk.viewer))
    assert (everyone["overdue"], everyone["due_soon"]) == (1, 2)
    assert desk.get("/stats/due?scope=all", desk.preparer).status_code == 403
    assert desk.get("/stats/due?scope=mine,all", desk.viewer).status_code == 422


def test_submitted_filings_leave_the_due_counts(desk):
    f = desk.filing(due_on=days(-1))
    desk.move(f["id"], "in_preparation", desk.preparer)
    desk.move(f["id"], "under_review", desk.preparer)
    desk.ok(desk.post(f"/filings/{f['id']}/submit", {"submitted_on": days(0), "submission_reference": "R-1"}))
    stats = desk.ok(desk.get("/stats/due?scope=all", desk.viewer))
    assert (stats["overdue"], stats["due_soon"]) == (0, 0)


def test_the_calendar_lists_filings_by_due_date_within_a_bounded_range(desk):
    a = desk.filing(due_on=days(20))
    b = desk.filing(due_on=days(4))
    desk.filing(due_on=days(200))
    cal = desk.ok(desk.get(f"/calendar?from={days(0)}&to={days(60)}", desk.viewer))
    assert [i["filing_id"] for i in cal["items"]] == [b["id"], a["id"]]
    assert desk.get(f"/calendar?from={days(0)}&to={days(400)}", desk.viewer).status_code == 422  # over 366 days
    assert desk.get(f"/calendar?from={days(10)}&to={days(0)}", desk.viewer).status_code == 422
    assert desk.get(f"/calendar?from={days(0)}&to={days(60)}", desk.preparer).status_code == 403  # needs data:read too


@pytest.mark.parametrize(
    ("role", "path"),
    [
        ("governance", "/stats/due?scope=all"),
        ("hospital-coordinator", "/stats/due"),
        ("research-office", "/stats/due"),
        ("management", "/calendar?from=2026-11-01&to=2026-12-31"),
    ],
)
def test_dashboard_roles_read_their_widget_through_the_layout(client, org, clock, role, path):
    d = Desk(client, org)
    d.filing(due_on=days(10))
    _, headers = org.user(role)
    assert d.get(path, headers).status_code == 200, role
