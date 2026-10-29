"""Consumed academic-management events keep the local copies, once per envelope, in any order, per organisation;
once filled, registration enforces the roster's checks and the report names the courses."""

from __future__ import annotations

import pytest
from conftest import add_enrolment, add_window, make_actor
from eos_core.db import new_id
from eos_enrolment_registration.application import service as svc
from eos_enrolment_registration.application.consumers import APPLIED, DUPLICATE, IGNORED, handle_event
from eos_enrolment_registration.application.service import EnrolmentError
from eos_enrolment_registration.infrastructure.models import OfferingRef, ProcessedEvent, SectionRef, TermRef


def envelope(org: str, name: str, payload: dict, version: int = 1, event_id: str | None = None) -> dict:
    return {
        "id": event_id or new_id(),
        "name": f"academic-management.{name}",
        "version": version,
        "organisation_id": org,
        "actor": None,
        "occurred_at": "2026-10-29T09:00:00+00:00",
        "payload": payload,
    }


def offering_created(org, offering, term, **over):
    payload = {
        "course_offering_id": offering,
        "course_id": new_id(),
        "academic_period_id": term,
        "programme_ids": [],
        "course_code": "CS101",
        "course_title": "Programming I",
        "credits": 4,
        "course_type": "core",
        "department_id": new_id(),
    } | over
    return envelope(org, "offering.created", payload)


def test_terms_and_the_active_flag(db, org):
    t1, t2 = new_id(), new_id()
    created = {
        "academic_period_id": t1,
        "code": "T1",
        "name": "Term 1",
        "starts_on": "2026-08-01",
        "ends_on": "2026-12-15",
    }
    assert handle_event(db, envelope(org, "term.created", created)) == APPLIED
    assert db.get(TermRef, t1).starts_on.isoformat() == "2026-08-01"
    handle_event(
        db, envelope(org, "term.activated", {"academic_period_id": t1, "activated_at": "2026-08-01T00:00:00Z"})
    )
    handle_event(
        db,
        envelope(
            org,
            "term.activated",
            {"academic_period_id": t2, "previous_academic_period_id": t1, "activated_at": "2027-01-01T00:00:00Z"},
        ),
    )
    assert (db.get(TermRef, t1).is_active, db.get(TermRef, t2).is_active) == (False, True)


def test_offerings_and_sections_in_any_order(db, org):
    offering, term, section = new_id(), new_id(), new_id()
    assert (
        handle_event(
            db,
            envelope(
                org,
                "offering.status-changed",
                {"course_offering_id": offering, "from_status": "planned", "to_status": "open", "changed_at": "x"},
            ),
        )
        == IGNORED
    )
    assert handle_event(db, offering_created(org, offering, term)) == APPLIED
    assert db.get(OfferingRef, offering).status == "planned"
    handle_event(
        db,
        envelope(
            org,
            "offering.status-changed",
            {"course_offering_id": offering, "from_status": "planned", "to_status": "open", "changed_at": "x"},
        ),
    )
    handle_event(db, offering_created(org, offering, term, course_title="Programming I (rev)"))
    row = db.get(OfferingRef, offering)
    assert (row.status, row.course_title) == ("open", "Programming I (rev)")
    assert (
        handle_event(
            db, envelope(org, "offering.updated", {"course_offering_id": offering, "changed_fields": ["credits"]})
        )
        == IGNORED
    )

    assert (
        handle_event(
            db,
            envelope(
                org,
                "section.updated",
                {"section_id": section, "course_offering_id": offering, "capacity": 20, "status": "closed"},
            ),
        )
        == APPLIED
    )
    handle_event(
        db,
        envelope(
            org, "section.created", {"section_id": section, "course_offering_id": offering, "code": "A", "capacity": 25}
        ),
    )
    row = db.get(SectionRef, section)
    assert (row.status, row.code, row.course_offering_id) == ("closed", "A", offering)


def test_each_envelope_applies_once_and_unknowns_are_ignored(db, org):
    event = offering_created(org, new_id(), new_id())
    assert handle_event(db, event) == APPLIED
    assert handle_event(db, event) == DUPLICATE
    assert db.query(ProcessedEvent).filter(ProcessedEvent.event_id == event["id"]).count() == 1
    assert handle_event(db, {**offering_created(org, new_id(), new_id()), "version": 2}) == IGNORED
    assert handle_event(db, envelope(org, "faculty-assignment.created", {})) == IGNORED
    assert handle_event(db, {**offering_created(None, new_id(), new_id()), "organisation_id": None}) == IGNORED


def test_an_event_never_changes_another_organisations_copy(db, org, other_org):
    offering = new_id()
    handle_event(db, offering_created(org, offering, new_id()))
    assert (
        handle_event(
            db,
            envelope(
                other_org,
                "offering.status-changed",
                {"course_offering_id": offering, "from_status": "planned", "to_status": "cancelled", "changed_at": "x"},
            ),
        )
        == IGNORED
    )
    assert db.get(OfferingRef, offering).status == "planned"


def test_once_filled_registration_is_verified_and_enforces_the_roster_checks(db, org):
    staff = make_actor(org)
    offering, term, section = new_id(), new_id(), new_id()
    add_window(db, org, term)
    handle_event(db, offering_created(org, offering, term))
    handle_event(
        db,
        envelope(
            org,
            "offering.status-changed",
            {"course_offering_id": offering, "from_status": "planned", "to_status": "open", "changed_at": "x"},
        ),
    )
    handle_event(
        db,
        envelope(
            org, "section.created", {"section_id": section, "course_offering_id": offering, "code": "A", "capacity": 1}
        ),
    )
    handle_event(db, envelope(org, "term.activated", {"academic_period_id": term, "activated_at": "x"}))

    def register():
        return svc.register(
            db,
            staff,
            programme_enrolment_id=add_enrolment(db, org).id,
            course_offering_id=offering,
            section_id=section,
            academic_period_id=term,
        )

    assert register()["references_verified"] is True
    with pytest.raises(EnrolmentError) as full:
        register()
    assert full.value.code == "section_full"

    handle_event(
        db,
        envelope(
            org,
            "section.updated",
            {"section_id": section, "course_offering_id": offering, "capacity": 5, "status": "closed"},
        ),
    )
    with pytest.raises(EnrolmentError) as closed:
        register()
    assert closed.value.code == "section_not_open"

    report = svc.registered_candidates(db, staff)
    assert report["academic_period_id"] == term
    assert (report["offerings"][0]["course_code"], report["offerings"][0]["registered"]) == ("CS101", 1)
