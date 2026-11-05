"""Inputs that must be refused cleanly, never reach the database as a 500: NUL characters, far-away dates, oversized
numbers and strings, forged cursors, LIKE wildcards, and a duplicate written past the check."""

import base64

import pytest
from conftest import BASE, PERIOD, TODAY
from eos_core.db import SessionLocal
from eos_field_training.application import service
from eos_field_training.application.service import FieldTrainingError
from eos_field_training.infrastructure.models import SiteSupervisor


def test_nul_in_a_path_is_not_found_and_in_a_query_is_invalid(prog, client):
    c = prog
    assert client.get(f"{BASE}/sites/{c.site['id']}%00", headers=c.viewer).status_code == 404
    assert client.post(f"{BASE}/openings/x%00/publish", headers=c.coordinator).status_code == 404
    r = c.get("/sites?q=Ward%00", c.viewer)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_query"
    r = c.get("/openings?cursor=%00", c.viewer)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_query"


def test_nul_in_a_body_is_refused(prog):
    c = prog
    assert c.post("/sites", {"name": "Ward\x00"}, c.coordinator).status_code == 422
    assert c.post("/sites", {"name": "Ward", "supervisor_ids": ["\x00"]}, c.coordinator).status_code == 422
    _, me, p = c.active()
    assert c.log(p, me, activities="Rounds\x00").status_code == 422
    r = c.post(f"/openings/{c.opening['id']}/cancel", {"reason": "Closed\x00"}, c.coordinator)
    assert r.status_code == 422
    assert c.get(f"/openings/{c.opening['id']}", c.viewer).json()["status"] == "open"


@pytest.mark.parametrize("day", ["0001-01-01", "1899-12-31", "9999-12-31"])
def test_dates_outside_1900_to_9998_are_refused(prog, day):
    c = prog
    body = {"site_id": c.site["id"], "title": "x", **PERIOD, "seats": 1}
    assert c.post("/openings", {**body, "starts_on": day}, c.coordinator).status_code == 422
    assert c.post("/openings", {**body, "ends_on": day}, c.coordinator).status_code == 422
    assert c.get(f"/openings?starts_after={day}", c.viewer).status_code == 422
    trainee_id, _ = c.trainee()
    assign = {"opening_id": c.opening["id"], "trainee_id": trainee_id, "ends_on": day}
    assert c.post("/placements", assign, c.coordinator).status_code == 422


def test_numbers_and_strings_are_bounded(prog):
    c = prog
    _, me, p = c.active()
    assert c.log(p, me, hours=10**12).status_code == 422
    assert c.get("/sites?q=" + "x" * 201, c.viewer).status_code == 422
    assert c.get("/openings?cursor=" + "x" * 101, c.viewer).status_code == 422
    assert c.get("/me/trainees?limit=1000000", c.supervisor).status_code == 422
    body = {"stage": "mid", "outcome": "x", "score": 1e308}
    assert c.post(f"/placements/{p['id']}/assessments", body, c.supervisor).status_code == 422
    assert c.post(f"/placements/{p['id']}/complete", {"reason": "x" * 2001}, c.coordinator).status_code == 422
    assert c.log(p, me, date=TODAY).status_code == 201


def test_forged_cursors_start_from_the_top(prog):
    c = prog
    c.new_opening(title="Second")
    first = c.ok(c.get("/openings?limit=1", c.viewer))["items"]
    for offset in ("1000001", "-5", "99999999999999999999"):
        cursor = base64.urlsafe_b64encode(offset.encode()).decode()
        assert c.ok(c.get(f"/openings?limit=1&cursor={cursor}", c.viewer))["items"] == first, offset
    assert c.ok(c.get("/openings?limit=1&cursor=not-base64!", c.viewer))["items"] == first


def test_search_treats_wildcards_literally(prog):
    c = prog
    c.ok(c.post("/sites", {"name": "Ward 100% ready"}, c.coordinator), 201)
    assert [s["name"] for s in c.ok(c.get("/sites?q=%25", c.viewer))] == ["Ward 100% ready"]
    assert c.ok(c.get("/sites?q=_", c.viewer)) == []


def test_a_duplicate_written_past_the_check_is_a_409(prog):
    c = prog
    with SessionLocal() as db:
        db.info["organisation_id"] = c.org.id
        db.add(SiteSupervisor(organisation_id=c.org.id, site_id=c.site["id"], person_id=c.supervisor_id, position=9))
        with pytest.raises(FieldTrainingError) as e:
            service._flush_unique(db, "duplicate_supervisor", "a supervisor is listed twice on the site")
        assert (e.value.status, e.value.code) == (409, "duplicate_supervisor")
    assert c.ok(c.get(f"/sites/{c.site['id']}", c.viewer))["supervisor_ids"] == [c.supervisor_id]


def test_no_input_schema_accepts_an_explicit_null_except_assessment_score():
    """Contract: only AssessmentInput.score is nullable. Every other optional field is left out to keep its value."""
    import pytest
    from eos_field_training.api import schemas as s
    from pydantic import ValidationError

    bodies = {
        s.SiteIn: {"name": "x"},
        s.OpeningIn: {
            "site_id": "0" * 8 + "-0000-0000-0000-" + "0" * 12,
            "title": "x",
            "starts_on": "2026-11-02",
            "ends_on": "2026-12-31",
            "seats": 1,
        },
        s.AssignIn: {
            "opening_id": "0" * 8 + "-0000-0000-0000-" + "0" * 12,
            "trainee_id": "0" * 8 + "-0000-0000-0000-" + "0" * 12,
        },
        s.PlacementPatchIn: {},
        s.DecisionIn: {"decision": "approved"},
        s.CompleteIn: {},
        s.LogEntryIn: {"date": "2026-11-03", "hours": 1, "activities": "x"},
        s.AssessmentIn: {"stage": "mid", "outcome": "x"},
        s.ApplyIn: {},
    }
    for model, base in bodies.items():
        for name in model.model_fields:
            if name in base:
                continue
            body = {**base, name: None}
            if name in model.nullable:
                model(**body)
            else:
                with pytest.raises(ValidationError):
                    model(**body)
    assert s.AssessmentIn.nullable == {"score"}
