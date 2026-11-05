"""Sites and openings (docs/user-stories.md SI and OP)."""

from conftest import PERIOD, audit, events
from eos_field_training.infrastructure.models import new_id


def test_sites_create_list_update_deactivate(prog):
    c = prog
    site = c.site
    assert site["supervisor_ids"] == [c.supervisor_id] and site["active"] is True and site["kind"] == "Ward"
    other = c.ok(c.post("/sites", {"name": "Partner School"}, c.coordinator), 201)
    assert [s["name"] for s in c.ok(c.get("/sites", c.viewer))] == ["North Ward", "Partner School"]
    assert [s["id"] for s in c.ok(c.get("/sites?q=school", c.supervisor))] == [other["id"]]
    new_sup = new_id()
    r = c.ok(
        c.patch(
            f"/sites/{other['id']}", {"name": "Partner School", "supervisor_ids": [new_sup, new_sup]}, c.coordinator
        )
    )
    assert r["supervisor_ids"] == [new_sup]
    r = c.ok(c.patch(f"/sites/{other['id']}", {"name": "Partner School 2", "active": False}, c.coordinator))
    assert r["active"] is False and r["supervisor_ids"] == [new_sup] and r["name"] == "Partner School 2"
    assert {"site.created", "site.updated", "site.deactivated"} <= set(audit(other["id"]))
    assert [s["id"] for s in c.ok(c.get("/sites?active=false", c.viewer))] == [other["id"]]
    assert c.ok(c.get(f"/sites/{site['id']}", c.supervisor))["name"] == "North Ward"
    assert c.get(f"/sites/{new_id()}", c.viewer).status_code == 404


def test_site_input_bounds(prog):
    c = prog
    assert c.post("/sites", {"name": ""}, c.coordinator).status_code == 422
    assert c.post("/sites", {"name": "x" * 201}, c.coordinator).status_code == 422
    assert c.post("/sites", {"name": "x", "contact_email": "not-an-email"}, c.coordinator).status_code == 422
    assert c.post("/sites", {"name": "x", "supervisor_ids": ["abc"]}, c.coordinator).status_code == 422
    assert c.post("/sites", {"name": "x", "unknown": 1}, c.coordinator).status_code == 422
    assert c.get("/sites/not-a-uuid", c.viewer).status_code == 422


def test_opening_lifecycle_publishes_events(prog):
    c = prog
    draft = c.new_opening(publish=False, title="Night rotation")
    assert draft["status"] == "draft" and draft["seats_filled"] == 0 and draft["site_name"] == "North Ward"
    assert draft["required_hours"] == 40 and draft["supervisor_ids"] == [c.supervisor_id]
    opened = c.ok(c.post(f"/openings/{draft['id']}/publish", None, c.coordinator))
    assert opened["status"] == "open"
    assert events("field-training.opening.published", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "opening_id": draft["id"],
        "site_id": c.site["id"],
        "starts_on": "2026-11-02",
        "ends_on": "2026-12-31",
        "seats": 2,
        "allow_applications": True,
    }
    assert c.post(f"/openings/{draft['id']}/publish", None, c.coordinator).status_code == 409
    closed = c.ok(c.post(f"/openings/{draft['id']}/close", None, c.coordinator))
    assert closed["status"] == "closed"
    assert events("field-training.opening.closed", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "opening_id": draft["id"],
    }
    assert c.post(f"/openings/{draft['id']}/close", None, c.coordinator).status_code == 409
    assert {"opening.created", "opening.published", "opening.closed"} <= set(audit(draft["id"]))


def test_opening_validation(prog):
    c = prog
    body = {"site_id": c.site["id"], "title": "x", **PERIOD, "seats": 1}
    assert c.post("/openings", {**body, "ends_on": "2026-11-01"}, c.coordinator).status_code == 422
    assert c.post("/openings", {**body, "seats": 0}, c.coordinator).status_code == 422
    assert c.post("/openings", {**body, "seats": 10**9}, c.coordinator).status_code == 422
    assert c.post("/openings", {**body, "required_hours": 10.1}, c.coordinator).status_code == 422
    assert c.post("/openings", {**body, "required_hours": 10**9}, c.coordinator).status_code == 422
    assert c.post("/openings", {**body, "site_id": "site-1"}, c.coordinator).status_code == 422
    assert c.post("/openings", {**body, "site_id": new_id()}, c.coordinator).status_code == 404
    c.patch(f"/sites/{c.site['id']}", {"name": "North Ward", "active": False}, c.coordinator)
    r = c.post("/openings", body, c.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "site_inactive"


def test_opening_update_rules(prog):
    c = prog
    o = c.opening
    path = f"/openings/{o['id']}"
    full = {k: o[k] for k in ("site_id", "title", "starts_on", "ends_on", "seats")}
    c.assigned()
    c.assigned()
    r = c.patch(path, {**full, "seats": 1}, c.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "seats_below_filled"
    r = c.ok(c.patch(path, {**full, "seats": 3, "title": "Renamed", "required_hours": 50}, c.coordinator))
    assert r["seats"] == 3 and r["title"] == "Renamed" and r["seats_filled"] == 2 and r["required_hours"] == 50
    # Placements not yet started follow the new requirement.
    assert {p["required_hours"] for p in c.ok(c.get("/placements", c.coordinator))["items"]} == {50}
    # A placement outside the new period blocks the change; so does an active placement.
    r = c.patch(path, {**full, "starts_on": "2026-11-10"}, c.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "period_locked"
    c.active()
    r = c.patch(path, {**full, "seats": 3, "ends_on": "2027-01-31"}, c.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "period_locked"
    assert c.patch(path, {**full, "site_id": new_id(), "seats": 3}, c.coordinator).status_code == 404


def test_cancel_withdraws_unstarted_placements(prog):
    c = prog
    o = c.opening
    trainee_id, me, assigned = c.assigned()
    _, applicant = c.trainee()
    requested = c.ok(c.post(f"/openings/{o['id']}/apply", {"statement": "Keen"}, applicant), 201)
    assert c.post(f"/openings/{o['id']}/cancel", {"reason": "x"}, c.coordinator).status_code == 422
    r = c.ok(c.post(f"/openings/{o['id']}/cancel", {"reason": "Site closed for works"}, c.coordinator))
    assert r["status"] == "cancelled" and r["seats_filled"] == 0
    assert events("field-training.opening.cancelled", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "opening_id": o["id"],
        "reason": "Site closed for works",
    }
    withdrawn = events("field-training.placement.withdrawn", c.org.id)
    assert {e["placement_id"] for e in withdrawn} == {assigned["id"], requested["id"]}
    assert all(e["was_active"] is False and e["reason"] == "Site closed for works" for e in withdrawn)
    assert c.ok(c.get(f"/placements/{assigned['id']}", me))["status"] == "withdrawn"
    assert c.post(f"/openings/{o['id']}/cancel", {"reason": "Again"}, c.coordinator).status_code == 409
    full = {k: o[k] for k in ("site_id", "title", "starts_on", "ends_on", "seats")}
    assert c.patch(f"/openings/{o['id']}", full, c.coordinator).status_code == 409


def test_cancel_refused_with_an_active_placement(prog):
    c = prog
    c.active()
    r = c.post(f"/openings/{c.opening['id']}/cancel", {"reason": "Site closed"}, c.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "placement_active"


def test_listing_openings_filters_and_pages(prog):
    c = prog
    later = c.new_opening(title="Later rotation", starts_on="2027-01-04", ends_on="2027-02-26", seats=1)
    draft = c.new_opening(publish=False, title="Draft rotation")
    c.assigned(later)  # later is now full
    ids = lambda r: [o["id"] for o in c.ok(r)["items"]]  # noqa: E731
    assert ids(c.get("/openings?status=open", c.coordinator)) == [c.opening["id"], later["id"]]
    assert ids(c.get("/openings?status=open&has_seats=true", c.coordinator)) == [c.opening["id"]]
    assert ids(c.get("/openings?has_seats=false", c.coordinator)) == [later["id"]]
    assert ids(c.get("/openings?starts_after=2026-12-01", c.viewer)) == [later["id"]]
    assert ids(c.get("/openings?status=draft", c.viewer)) == [draft["id"]]
    assert ids(c.get(f"/openings?site_id={c.site['id']}&status=closed", c.viewer)) == []
    first = c.ok(c.get("/openings?limit=2", c.viewer))
    assert len(first["items"]) == 2 and first["next_cursor"]
    rest = c.ok(c.get(f"/openings?limit=2&cursor={first['next_cursor']}", c.viewer))
    assert len(rest["items"]) == 1 and rest["next_cursor"] is None
    assert c.get("/openings?limit=101", c.viewer).status_code == 422
    assert c.get("/openings?status=pending", c.viewer).status_code == 422
    assert c.get("/openings?site_id=abc", c.viewer).status_code == 422
    assert c.ok(c.get(f"/openings/{later['id']}", c.viewer))["seats_filled"] == 1


def test_supervisor_sees_openings_at_own_sites_and_trainee_sees_applications(prog):
    c = prog
    elsewhere = c.ok(c.post("/sites", {"name": "South Plant"}, c.coordinator), 201)
    away = c.new_opening(site_id=elsewhere["id"], title="Plant rotation", supervisor_ids=[])
    closed_to_applications = c.new_opening(title="Assigned only", allow_applications=False)
    ids = lambda r: {o["id"] for o in c.ok(r)["items"]}  # noqa: E731
    assert ids(c.get("/openings", c.supervisor)) == {c.opening["id"], closed_to_applications["id"]}
    assert c.get(f"/openings/{away['id']}", c.supervisor).status_code == 404
    assert c.ok(c.get(f"/openings/{c.opening['id']}", c.supervisor))["id"] == c.opening["id"]
    _, trainee = c.trainee()
    assert ids(c.get("/openings", trainee)) == {c.opening["id"], away["id"]}
    assert ids(c.get("/openings?status=draft", trainee)) == set()
    assert c.get(f"/openings/{c.opening['id']}", trainee).status_code == 403


def test_patch_site_with_explicit_null_is_422_and_changes_nothing(prog):
    """The contract types no site field as nullable: a null is refused, never a silent clear (supervisor_ids: null used
    to wipe the site's supervisors, cutting their access to every placement they supervise)."""
    c = prog
    path = f"/sites/{c.site['id']}"
    before = c.ok(c.get(path, c.coordinator))
    assert before["supervisor_ids"] == [c.supervisor_id]
    for field in ("supervisor_ids", "kind", "address", "contact_name", "contact_email", "active"):
        r = c.patch(path, {"name": before["name"], field: None}, c.coordinator)
        assert r.status_code == 422, field
        assert c.ok(c.get(path, c.coordinator)) == before, field
    # Creating with a null is refused too.
    assert c.post("/sites", {"name": "Null site", "supervisor_ids": None}, c.coordinator).status_code == 422
    # Leaving the field out still keeps the stored supervisors; an empty list clears them on purpose.
    assert c.ok(c.patch(path, {"name": "Renamed"}, c.coordinator))["supervisor_ids"] == [c.supervisor_id]
    assert c.ok(c.patch(path, {"name": "Renamed", "supervisor_ids": []}, c.coordinator))["supervisor_ids"] == []


def test_patch_opening_with_explicit_null_is_422_and_changes_nothing(prog):
    c = prog
    o = c.opening
    path = f"/openings/{o['id']}"
    full = {k: o[k] for k in ("site_id", "title", "starts_on", "ends_on", "seats")}
    before = c.ok(c.get(path, c.coordinator))
    assert before["supervisor_ids"] == [c.supervisor_id]
    for field in ("supervisor_ids", "discipline", "required_hours", "allow_applications", "eligibility"):
        r = c.patch(path, {**full, field: None}, c.coordinator)
        assert r.status_code == 422, field
        assert c.ok(c.get(path, c.coordinator)) == before, field
    assert c.ok(c.patch(path, full, c.coordinator))["supervisor_ids"] == [c.supervisor_id]
