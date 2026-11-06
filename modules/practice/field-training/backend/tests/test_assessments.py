"""Assessments and completion (docs/user-stories.md AS and CO)."""

from conftest import audit, events


def assess(c, p, stage="final", **over):
    body = {"stage": stage, "outcome": "Competent", "score": 78.5, "comments": "Steady progress", **over}
    return c.post(f"/placements/{p['id']}/assessments", body, c.supervisor)


def test_record_mid_and_final(prog):
    c = prog
    trainee_id, me, p = c.active()
    mid = c.ok(assess(c, p, stage="mid", outcome="On track"), 201)
    assert mid["stage"] == "mid" and mid["assessor_id"] == c.supervisor_id and mid["recorded_at"]
    final = c.ok(assess(c, p), 201)
    assert events("field-training.assessment.recorded", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "assessment_id": final["id"],
        "placement_id": p["id"],
        "trainee_id": trainee_id,
        "assessor_id": c.supervisor_id,
        "stage": "final",
        "outcome": "Competent",
    }
    r = assess(c, p)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "final_recorded"
    assert [a["stage"] for a in c.ok(c.get(f"/placements/{p['id']}/assessments", me))] == ["mid", "final"]
    assert c.ok(c.get(f"/placements/{p['id']}", c.viewer))["final_outcome"] == "Competent"
    assert "assessment.recorded" in audit(final["id"])


def test_assessment_checks(prog):
    c = prog
    _, _, assigned = c.assigned()
    r = assess(c, assigned)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "placement_not_active"
    _, _, p = c.active()
    for over in (
        {"stage": "end"},
        {"score": 101},
        {"score": -1},
        {"outcome": ""},
        {"outcome": "x" * 201},
        {"comments": "x" * 4001},
    ):
        assert assess(c, p, **over).status_code == 422, over
    assert assess(c, p, score=None).status_code == 201
    _, other_sup = c.org.user("field-training-supervisor")
    body = {"stage": "mid", "outcome": "x"}
    r = c.post(f"/placements/{p['id']}/assessments", body, other_sup)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "not_supervisor"


def test_complete_refusals_then_completion(prog):
    c = prog
    trainee_id, me, p = c.active()
    path = f"/placements/{p['id']}/complete"
    r = c.post(path, None, c.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no-final-assessment"
    c.ok(assess(c, p), 201)
    r = c.post(path, {}, c.coordinator)
    assert r.status_code == 409 and r.json()["detail"] == {
        "code": "hours-short",
        "message": "0 of 40 required hours are verified; complete with override and a reason",
    }
    r = c.post(path, {"override": True}, c.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "reason-required"
    done = c.ok(c.post(path, {"override": True, "reason": "Absence agreed with the site"}, c.coordinator))
    assert done["status"] == "completed" and done["reason"] == "Absence agreed with the site"
    assert events("field-training.placement.completed", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "placement_id": p["id"],
        "opening_id": c.opening["id"],
        "site_id": c.site["id"],
        "trainee_id": trainee_id,
        "verified_hours": 0.0,
        "required_hours": 40.0,
        "final_outcome": "Competent",
        "hours_overridden": True,
    }
    r = c.post(path, None, c.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not-active"
    assert c.post(f"/placements/{p['id']}/withdraw", {"reason": "Too late"}, c.coordinator).status_code == 409
    assert "placement.completed" in audit(p["id"])


def test_complete_with_hours_met_needs_no_override(prog):
    c = prog
    small = c.new_opening(title="Short rotation", required_hours=10)
    _, me, p = c.active(small)
    for day, hours in (("2026-11-02", 6), ("2026-11-03", 4)):
        e = c.ok(c.log(p, me, hours=hours, date=day), 201)
        c.ok(c.post(f"/logs/{e['id']}/verify", None, c.supervisor))
    c.ok(assess(c, p), 201)
    done = c.ok(c.post(f"/placements/{p['id']}/complete", None, c.coordinator))
    assert done["status"] == "completed" and done["verified_hours"] == 10 and done["reason"] is None
    last = events("field-training.placement.completed", c.org.id)[-1]
    assert last["hours_overridden"] is False and last["verified_hours"] == 10.0
    # A completed placement keeps its seat.
    assert c.ok(c.get(f"/openings/{small['id']}", c.coordinator))["seats_filled"] == 1
