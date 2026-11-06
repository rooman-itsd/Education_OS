"""The caller's own records and the widget endpoints (docs/user-stories.md ME and WI)."""

from conftest import TODAY
from eos_field_training.infrastructure.models import new_id


def test_my_placements_order_and_past(prog):
    c = prog
    trainee_id, me, active = c.active()
    later = c.new_opening(title="January rotation", starts_on="2027-01-04", ends_on="2027-02-26")
    upcoming = c.ok(c.post("/placements", {"opening_id": later["id"], "trainee_id": trainee_id}, c.coordinator), 201)
    spring = c.new_opening(title="Spring rotation", starts_on="2027-03-01", ends_on="2027-03-31")
    requested = c.ok(c.post(f"/openings/{spring['id']}/apply", None, me), 201)
    summer = c.new_opening(title="Summer rotation", starts_on="2027-05-01", ends_on="2027-05-31")
    gone = c.ok(c.post(f"/openings/{summer['id']}/apply", None, me), 201)
    c.ok(c.post(f"/placements/{gone['id']}/withdraw", {"reason": "Changed plans"}, me))
    ids = lambda r: [p["id"] for p in c.ok(r)]  # noqa: E731
    assert ids(c.get("/me/placements", me)) == [active["id"], upcoming["id"], requested["id"]]
    assert ids(c.get("/me/placements?include_past=true", me)) == [
        active["id"],
        upcoming["id"],
        requested["id"],
        gone["id"],
    ]
    _, someone = c.trainee()
    assert c.ok(c.get("/me/placements", someone)) == []


def test_my_placement_is_visible_to_me_only(prog):
    c = prog
    _, me, p = c.active()
    c.ok(c.log(p, me), 201)
    _, someone = c.trainee()
    for path in (f"/placements/{p['id']}", f"/placements/{p['id']}/logs", f"/placements/{p['id']}/assessments"):
        assert c.get(path, me).status_code == 200, path
        assert c.get(path, someone).status_code == 404, path
    assert c.get(f"/me/hours?placement_id={p['id']}", someone).status_code == 404


def test_my_hours(prog):
    c = prog
    _, me = c.trainee()
    empty = c.ok(c.get("/me/hours", me))
    assert empty == {
        "placement_id": None,
        "required_hours": 0.0,
        "verified_hours": 0.0,
        "pending_hours": 0.0,
        "returned_hours": 0.0,
        "by_date": [],
    }
    trainee_id, me, p = c.active()
    a = c.ok(c.log(p, me, hours=6), 201)
    c.ok(c.log(p, me, hours=2.5), 201)
    b = c.ok(c.log(p, me, hours=3, date="2026-11-02"), 201)
    c.ok(c.post(f"/logs/{a['id']}/verify", None, c.supervisor))
    c.ok(c.post(f"/logs/{b['id']}/return", {"reason": "More detail"}, c.supervisor))
    h = c.ok(c.get("/me/hours", me))
    assert h["placement_id"] == p["id"] and h["required_hours"] == 40
    assert (h["verified_hours"], h["pending_hours"], h["returned_hours"]) == (6, 2.5, 3)
    assert len(h["by_date"]) == 14 and h["by_date"][0]["date"] == "2026-10-21" and h["by_date"][-1]["date"] == TODAY
    assert h["by_date"][-1] == {"date": TODAY, "verified_hours": 6.0, "pending_hours": 2.5}
    assert h["by_date"][-2] == {"date": "2026-11-02", "verified_hours": 0.0, "pending_hours": 0.0}
    assert c.ok(c.get(f"/me/hours?placement_id={p['id']}", me))["verified_hours"] == 6
    assert c.get("/me/hours?placement_id=abc", me).status_code == 422
    assert c.get(f"/me/hours?placement_id={new_id()}", me).status_code == 404


def test_my_hours_falls_back_to_the_most_recent(prog):
    c = prog
    _, me, p = c.active()
    c.ok(c.post(f"/placements/{p['id']}/withdraw", {"reason": "Left the course"}, c.coordinator))
    assert c.ok(c.get("/me/hours", me))["placement_id"] == p["id"]


def test_trainees_to_assess(prog):
    c = prog
    # Ends within 7 days: final due. Ends later with entries awaiting: listed after it. Nothing to do: not listed.
    soon = c.new_opening(title="Short", starts_on="2026-11-02", ends_on="2026-11-09")
    _, me_a, due = c.active(soon)
    _, me_b, busy = c.active()
    _, _, quiet = c.active(c.new_opening(title="Quiet"))
    for _ in range(2):
        c.ok(c.log(busy, me_b, hours=2), 201)
    rows = c.ok(c.get("/me/trainees", c.supervisor))
    assert [(r["placement"]["id"], r["entries_awaiting"], r["final_assessment_due"]) for r in rows] == [
        (due["id"], 0, True),
        (busy["id"], 2, False),
    ]
    assert quiet["id"] not in {r["placement"]["id"] for r in rows}
    assert len(c.ok(c.get("/me/trainees?limit=1", c.supervisor))) == 1
    assert c.get("/me/trainees?limit=0", c.supervisor).status_code == 422
    # Recording the final takes it off the list; another supervisor sees none of these.
    c.ok(c.post(f"/placements/{due['id']}/assessments", {"stage": "final", "outcome": "Pass"}, c.supervisor), 201)
    assert [r["placement"]["id"] for r in c.ok(c.get("/me/trainees", c.supervisor))] == [busy["id"]]
    _, other_sup = c.org.user("field-training-supervisor")
    assert c.ok(c.get("/me/trainees", other_sup)) == []
