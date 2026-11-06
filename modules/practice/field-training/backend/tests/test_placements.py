"""Placements: assignment, application and decision, start, changes and withdrawal (docs/user-stories.md PL)."""

from conftest import TODAY, audit, events
from eos_field_training.infrastructure.models import new_id


def test_assign_publishes_and_defaults_to_the_opening(prog):
    c = prog
    trainee_id, _, p = c.assigned()
    assert p["status"] == "assigned" and p["trainee_id"] == trainee_id and p["supervisor_id"] == c.supervisor_id
    assert (p["starts_on"], p["ends_on"]) == ("2026-11-02", "2026-12-31")
    assert p["opening_title"] == "General rotation" and p["site_name"] == "North Ward"
    assert p["required_hours"] == 40 and p["verified_hours"] == 0 and p["final_outcome"] is None
    assert events("field-training.placement.assigned", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "placement_id": p["id"],
        "opening_id": c.opening["id"],
        "site_id": c.site["id"],
        "trainee_id": trainee_id,
        "supervisor_id": c.supervisor_id,
        "starts_on": "2026-11-02",
        "ends_on": "2026-12-31",
        "required_hours": 40.0,
    }
    assert "placement.assigned" in audit(p["id"])


def test_assign_checks(prog):
    c = prog
    o = c.opening
    trainee_id, _ = c.trainee()
    base = {"opening_id": o["id"], "trainee_id": trainee_id}
    for over, status in (
        ({"starts_on": "2026-10-01"}, 422),
        ({"starts_on": "2026-11-20", "ends_on": "2026-11-10"}, 422),
        ({"supervisor_id": trainee_id}, 422),
        ({"trainee_id": "someone"}, 422),
        ({"opening_id": new_id()}, 404),
    ):
        assert c.post("/placements", {**base, **over}, c.coordinator).status_code == status, over
    first = c.ok(c.post("/placements", {**base, "ends_on": "2026-11-30"}, c.coordinator), 201)
    r = c.post("/placements", base, c.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "already_applied"
    # The same trainee in another opening over the same dates overlaps; after the first ends it does not.
    other = c.new_opening(title="Second rotation")
    r = c.post("/placements", {**base, "opening_id": other["id"]}, c.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "overlapping_placement"
    second = {**base, "opening_id": other["id"], "starts_on": "2026-12-01"}
    assert c.ok(c.post("/placements", second, c.coordinator), 201)["starts_on"] == "2026-12-01"
    assert first["ends_on"] == "2026-11-30"
    draft = c.new_opening(publish=False, title="Draft")
    r = c.post("/placements", {**base, "opening_id": draft["id"], "trainee_id": new_id()}, c.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "opening_not_open"


def test_seats_are_never_over_filled(prog):
    c = prog
    c.assigned()
    c.assigned()
    r = c.post("/placements", {"opening_id": c.opening["id"], "trainee_id": new_id()}, c.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_seats"
    _, applicant = c.trainee()
    r = c.post(f"/openings/{c.opening['id']}/apply", None, applicant)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_seats"


def test_withdrawing_frees_the_seat(prog):
    c = prog
    _, _, p = c.assigned()
    c.assigned()
    c.ok(c.post(f"/placements/{p['id']}/withdraw", {"reason": "Changed track"}, c.coordinator))
    assert c.ok(c.get(f"/openings/{c.opening['id']}", c.coordinator))["seats_filled"] == 1
    c.assigned()


def test_apply_approve_and_reject(prog):
    c = prog
    o = c.opening
    trainee_id, me = c.trainee()
    p = c.ok(c.post(f"/openings/{o['id']}/apply", {"statement": "I would like this rotation"}, me), 201)
    assert p["status"] == "requested" and p["statement"] == "I would like this rotation" and p["supervisor_id"] is None
    assert events("field-training.placement.requested", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "placement_id": p["id"],
        "opening_id": o["id"],
        "trainee_id": trainee_id,
    }
    assert c.ok(c.get(f"/openings/{o['id']}", c.coordinator))["seats_filled"] == 0  # a request holds no seat
    r = c.post(f"/openings/{o['id']}/apply", {}, me)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "already_applied"
    approved = c.ok(c.post(f"/placements/{p['id']}/decision", {"decision": "approved"}, c.coordinator))
    assert approved["status"] == "assigned" and approved["supervisor_id"] == c.supervisor_id
    assert events("field-training.placement.assigned", c.org.id)[-1]["placement_id"] == p["id"]
    r = c.post(f"/placements/{p['id']}/decision", {"decision": "approved"}, c.coordinator)
    assert r.status_code == 409

    other_id, other = c.trainee()
    q = c.ok(c.post(f"/openings/{o['id']}/apply", None, other), 201)
    path = f"/placements/{q['id']}/decision"
    assert c.post(path, {"decision": "rejected"}, c.coordinator).status_code == 422
    assert c.post(path, {"decision": "maybe"}, c.coordinator).status_code == 422
    r = c.ok(c.post(path, {"decision": "rejected", "reason": "Prerequisite missing"}, c.coordinator))
    assert r["status"] == "rejected" and r["reason"] == "Prerequisite missing"
    assert events("field-training.placement.rejected", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "placement_id": q["id"],
        "trainee_id": other_id,
        "reason": "Prerequisite missing",
    }
    # After a rejection the trainee may apply again.
    assert c.post(f"/openings/{o['id']}/apply", None, other).status_code == 201


def test_apply_refusals(prog):
    c = prog
    _, me = c.trainee()
    no_apps = c.new_opening(title="Assigned only", allow_applications=False)
    r = c.post(f"/openings/{no_apps['id']}/apply", None, me)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "applications_not_allowed"
    draft = c.new_opening(publish=False, title="Draft")
    r = c.post(f"/openings/{draft['id']}/apply", None, me)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "opening_not_open"
    c.ok(c.post(f"/openings/{c.opening['id']}/apply", None, me), 201)
    overlapping = c.new_opening(title="Overlapping")
    r = c.post(f"/openings/{overlapping['id']}/apply", None, me)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "overlapping_placement"
    assert c.post(f"/openings/{c.opening['id']}/apply", {"statement": "x" * 2001}, me).status_code == 422
    assert c.post(f"/openings/{new_id()}/apply", None, me).status_code == 404


def test_approval_needs_a_seat_and_an_open_opening(prog):
    c = prog
    _, me = c.trainee()
    p = c.ok(c.post(f"/openings/{c.opening['id']}/apply", None, me), 201)
    c.assigned()
    c.assigned()
    r = c.post(f"/placements/{p['id']}/decision", {"decision": "approved"}, c.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_seats"
    c.ok(c.post(f"/openings/{c.opening['id']}/close", None, c.coordinator))
    r = c.post(f"/placements/{p['id']}/decision", {"decision": "approved"}, c.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "opening_not_open"


def test_start_early_publishes(prog):
    c = prog
    later = c.new_opening(title="December rotation", starts_on="2026-12-01", ends_on="2026-12-31")
    trainee_id, _, p = c.assigned(later)
    r = c.ok(c.post(f"/placements/{p['id']}/start", None, c.coordinator))
    assert r["status"] == "active"
    assert events("field-training.placement.started", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "placement_id": p["id"],
        "trainee_id": trainee_id,
        "supervisor_id": c.supervisor_id,
        "started_on": TODAY,
    }
    assert c.post(f"/placements/{p['id']}/start", None, c.coordinator).status_code == 409


def test_change_supervisor_and_dates(prog):
    c = prog
    trainee_id, me, p = c.assigned()
    new_sup = new_id()
    path = f"/placements/{p['id']}"
    r = c.ok(c.patch(path, {"supervisor_id": new_sup, "ends_on": "2026-11-30"}, c.coordinator))
    assert r["supervisor_id"] == new_sup and r["ends_on"] == "2026-11-30"
    assert c.patch(path, {"ends_on": "2027-02-01"}, c.coordinator).status_code == 422
    assert c.patch(path, {"supervisor_id": trainee_id}, c.coordinator).status_code == 422
    assert c.patch(path, {"supervisor_id": "nobody"}, c.coordinator).status_code == 422
    other = c.new_opening(title="Second rotation")
    c.ok(
        c.post(
            "/placements",
            {"opening_id": other["id"], "trainee_id": trainee_id, "starts_on": "2026-12-01"},
            c.coordinator,
        ),
        201,
    )
    r = c.patch(path, {"ends_on": "2026-12-15"}, c.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "overlapping_placement"
    c.ok(c.post(f"{path}/withdraw", {"reason": "Moved"}, c.coordinator))
    assert c.patch(path, {"ends_on": "2026-11-20"}, c.coordinator).status_code == 409
    assert "placement.updated" in audit(p["id"])


def test_active_dates_must_keep_the_logged_days(prog):
    c = prog
    _, me, p = c.active()
    c.ok(c.log(p, me, date="2026-11-02"), 201)
    r = c.patch(f"/placements/{p['id']}", {"starts_on": "2026-11-03"}, c.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "date_outside_placement"


def test_withdraw_by_trainee_or_coordinator(prog):
    c = prog
    trainee_id, me, p = c.assigned()
    _, someone = c.trainee()
    path = f"/placements/{p['id']}/withdraw"
    assert c.post(path, {"reason": "Not mine"}, someone).status_code == 404
    assert c.post(path, {"reason": "x"}, me).status_code == 422
    r = c.ok(c.post(path, {"reason": "Family reasons"}, me))
    assert r["status"] == "withdrawn" and r["reason"] == "Family reasons"
    assert events("field-training.placement.withdrawn", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "placement_id": p["id"],
        "trainee_id": trainee_id,
        "was_active": False,
        "reason": "Family reasons",
    }
    assert c.post(path, {"reason": "Again"}, c.coordinator).status_code == 409
    # Once active, only the coordinator withdraws it.
    _, me2, active = c.active()
    r = c.post(f"/placements/{active['id']}/withdraw", {"reason": "Leaving"}, me2)
    assert r.status_code == 403
    c.ok(c.post(f"/placements/{active['id']}/withdraw", {"reason": "Leaving the course"}, c.coordinator))
    assert events("field-training.placement.withdrawn", c.org.id)[-1]["was_active"] is True


def test_list_placements_and_supervision_scope(prog):
    c = prog
    _, _, a = c.active()
    trainee_b, _, b = c.assigned()
    other_sup, _ = c.org.user("field-training-supervisor")
    c.ok(c.patch(f"/placements/{b['id']}", {"supervisor_id": other_sup}, c.coordinator))
    ids = lambda r: [p["id"] for p in c.ok(r)["items"]]  # noqa: E731
    assert set(ids(c.get("/placements", c.viewer))) == {a["id"], b["id"]}
    assert ids(c.get("/placements?status=active", c.coordinator)) == [a["id"]]
    assert ids(c.get(f"/placements?trainee_id={trainee_b}", c.viewer)) == [b["id"]]
    assert ids(c.get(f"/placements?opening_id={c.opening['id']}&site_id={c.site['id']}&status=assigned", c.viewer)) == [
        b["id"]
    ]
    assert ids(c.get(f"/placements?supervisor_id={other_sup}", c.viewer)) == [b["id"]]
    # A supervisor sees only the placements they supervise, whatever the filter.
    assert ids(c.get("/placements", c.supervisor)) == [a["id"]]
    assert ids(c.get(f"/placements?supervisor_id={other_sup}", c.supervisor)) == []
    assert c.ok(c.get(f"/placements/{a['id']}", c.supervisor))["id"] == a["id"]
    assert c.get(f"/placements/{b['id']}", c.supervisor).status_code == 404
    assert c.get("/placements?status=done", c.viewer).status_code == 422
    assert c.get(f"/placements/{new_id()}", c.viewer).status_code == 404
