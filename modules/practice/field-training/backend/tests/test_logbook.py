"""The logbook: entries, the 24-hour day, verification and return (docs/user-stories.md LB)."""

from conftest import TODAY, audit, events


def test_add_entry_publishes_without_text(prog):
    c = prog
    trainee_id, me, p = c.active()
    r = c.log(p, me, hours=6.5, reflection="Learned the intake routine")
    assert r.status_code == 201, r.text
    e = r.json()
    assert e["status"] == "submitted" and e["hours"] == 6.5 and e["date"] == TODAY and e["verified_by"] is None
    assert e["reflection"] == "Learned the intake routine" and e["submitted_at"].startswith("2026-11-03T08:00")
    assert events("field-training.log.submitted", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "log_id": e["id"],
        "placement_id": p["id"],
        "trainee_id": trainee_id,
        "supervisor_id": c.supervisor_id,
        "date": TODAY,
        "hours": 6.5,
    }
    assert "log.submitted" in audit(e["id"])
    assert c.ok(c.get(f"/placements/{p['id']}", me))["pending_hours"] == 6.5


def test_entry_validation(prog):
    c = prog
    _, me, p = c.active()
    for over in (
        {"hours": 0},
        {"hours": 24.25},
        {"hours": 1.1},
        {"activities": ""},
        {"activities": "x" * 4001},
        {"reflection": "x" * 4001},
        {"date": "03-11-2026"},
        {"patient_name": "x"},
    ):
        assert c.log(p, me, **over).status_code == 422, over
    r = c.log(p, me, date="2026-11-01")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "date_outside_placement"
    r = c.log(p, me, date="2026-11-04")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "date_in_future"


def test_day_stays_at_or_under_24_hours(prog):
    c = prog
    _, me, p = c.active()
    c.ok(c.log(p, me, hours=20), 201)
    r = c.log(p, me, hours=4.25)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "day_over_24_hours"
    c.ok(c.log(p, me, hours=4), 201)
    c.ok(c.log(p, me, hours=24, date="2026-11-02"), 201)


def test_only_active_and_own_placements_take_entries(prog):
    c = prog
    _, me, assigned = c.assigned()
    r = c.log(assigned, me)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "placement_not_active"
    _, other, active = c.active()
    assert c.log(active, me).status_code == 404


def test_verify_and_return(prog):
    c = prog
    trainee_id, me, p = c.active()
    a = c.ok(c.log(p, me, hours=8), 201)
    b = c.ok(c.log(p, me, hours=4, date="2026-11-02"), 201)
    r = c.ok(c.post(f"/logs/{a['id']}/verify", None, c.supervisor))
    assert r["status"] == "verified" and r["verified_by"] == c.supervisor_id and r["verified_at"]
    assert events("field-training.log.verified", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "log_id": a["id"],
        "placement_id": p["id"],
        "trainee_id": trainee_id,
        "hours": 8.0,
        "verified_by": c.supervisor_id,
    }
    assert c.post(f"/logs/{a['id']}/verify", None, c.supervisor).status_code == 409
    assert c.post(f"/logs/{b['id']}/return", {"reason": "no"}, c.supervisor).status_code == 422
    r = c.ok(c.post(f"/logs/{b['id']}/return", {"reason": "Add what you did in the afternoon"}, c.supervisor))
    assert r["status"] == "returned" and r["return_reason"] == "Add what you did in the afternoon"
    assert events("field-training.log.returned", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "log_id": b["id"],
        "placement_id": p["id"],
        "trainee_id": trainee_id,
    }
    assert c.post(f"/logs/{b['id']}/return", {"reason": "Again please"}, c.supervisor).status_code == 409
    placement = c.ok(c.get(f"/placements/{p['id']}", c.coordinator))
    assert placement["verified_hours"] == 8 and placement["pending_hours"] == 0
    assert [e["id"] for e in c.ok(c.get(f"/placements/{p['id']}/logs", c.supervisor))] == [a["id"], b["id"]]
    assert [e["id"] for e in c.ok(c.get(f"/placements/{p['id']}/logs?status=returned", me))] == [b["id"]]
    assert {"log.verified"} <= set(audit(a["id"])) and {"log.returned"} <= set(audit(b["id"]))


def test_edit_resubmits_returned_and_locks_verified(prog):
    c = prog
    _, me, p = c.active()
    a = c.ok(c.log(p, me, hours=8), 201)
    b = c.ok(c.log(p, me, hours=4, date="2026-11-02"), 201)
    edit = {"date": "2026-11-02", "hours": 5, "activities": "Assisted with the afternoon round too"}
    r = c.ok(c.patch(f"/logs/{b['id']}", edit, me))
    assert r["hours"] == 5 and r["status"] == "submitted"
    before = len(events("field-training.log.submitted", c.org.id))
    c.ok(c.post(f"/logs/{b['id']}/return", {"reason": "Add detail"}, c.supervisor))
    r = c.ok(c.patch(f"/logs/{b['id']}", {**edit, "hours": 6}, me))
    assert r["status"] == "submitted" and r["return_reason"] is None and r["hours"] == 6
    assert len(events("field-training.log.submitted", c.org.id)) == before + 1  # a resubmission is published
    assert "log.resubmitted" in audit(b["id"]) and "log.edited" in audit(b["id"])
    c.ok(c.post(f"/logs/{a['id']}/verify", None, c.supervisor))
    r = c.patch(f"/logs/{a['id']}", {**edit, "date": TODAY}, me)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "entry_verified"
    # Editing keeps the 24-hour day, not counting the entry itself.
    c.ok(c.log(p, me, hours=16, date="2026-11-02"), 201)
    r = c.patch(f"/logs/{b['id']}", {**edit, "hours": 8.25}, me)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "day_over_24_hours"
    assert c.ok(c.patch(f"/logs/{b['id']}", {**edit, "hours": 8}, me))["hours"] == 8
    _, someone = c.trainee()
    assert c.patch(f"/logs/{b['id']}", edit, someone).status_code == 404


def test_only_the_placements_supervisor_reviews_and_never_their_own(prog):
    c = prog
    _, me, p = c.active()
    e = c.ok(c.log(p, me), 201)
    _, other_sup = c.org.user("field-training-supervisor")
    r = c.post(f"/logs/{e['id']}/verify", None, other_sup)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "not_supervisor"
    assert c.post(f"/logs/{e['id']}/return", {"reason": "Not yours"}, other_sup).status_code == 403
    # A supervisor who is also the trainee of a placement cannot verify their own entry.
    sup_id, sup_and_trainee = c.org.user("field-training-supervisor", "field-training-trainee")
    own = c.ok(c.post("/placements", {"opening_id": c.opening["id"], "trainee_id": sup_id}, c.coordinator), 201)
    c.ok(c.post(f"/placements/{own['id']}/start", None, c.coordinator))
    c.ok(c.patch(f"/placements/{own['id']}", {"supervisor_id": c.supervisor_id}, c.coordinator))
    mine = c.ok(c.log(own, sup_and_trainee), 201)
    r = c.post(f"/logs/{mine['id']}/verify", None, sup_and_trainee)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "own_entry"


def test_no_review_after_the_placement_ends(prog):
    c = prog
    _, me, p = c.active()
    e = c.ok(c.log(p, me), 201)
    c.ok(c.post(f"/placements/{p['id']}/withdraw", {"reason": "Left the course"}, c.coordinator))
    r = c.post(f"/logs/{e['id']}/verify", None, c.supervisor)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "placement_not_active"
    edit = {"date": TODAY, "hours": 2, "activities": "x"}
    assert c.patch(f"/logs/{e['id']}", edit, me).status_code == 409
