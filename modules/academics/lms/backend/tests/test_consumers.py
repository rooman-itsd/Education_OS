"""The consumers that fill the read models: idempotent, order-tolerant, refusing malformed events, scoped to the
event's organisation."""

from datetime import timedelta
from pathlib import Path

import pytest
import yaml
from conftest import (
    NOW,
    STUDENT,
    Course,
    assignment_created,
    deliver,
    offering_created,
    registration_confirmed,
)
from eos_core.db import SessionLocal
from eos_core.tenant import organisation_scope
from eos_lms.application import consumers as cons
from eos_lms.infrastructure.models import InstructorRef, MemberRef, OfferingRef, new_id
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[5]
MANIFEST = yaml.safe_load((Path(__file__).resolve().parents[2] / "module.yaml").read_text(encoding="utf-8"))


def row(model, column, value):
    with SessionLocal() as db:
        return db.scalars(select(model).where(column == value)).first()


# student-information publishes person.account-linked from contract 0.2.0 (its own PR). This module may merge first: it
# simply receives nothing until then. Once the producer's contract has the event, it is checked like every other.
NOT_YET_UPSTREAM = {cons.ACCOUNT_LINKED}


def test_consumers_are_the_manifests_and_exist_upstream():
    assert set(cons.CONSUMERS) == set(MANIFEST["consumes_events"])
    published = {}
    for module in (
        "academics/academic-management",
        "student-lifecycle/enrolment-registration",
        "student-lifecycle/student-information",
    ):
        events = yaml.safe_load((ROOT / "modules" / module / "contracts" / "events.yaml").read_text(encoding="utf-8"))
        published |= {e["name"]: e for e in events["events"]}
    for name in cons.CONSUMERS:
        if name not in published and name in NOT_YET_UPSTREAM:
            continue
        assert name in published, name
        assert "lms" in published[name]["consumers"], name


def test_offering_events_are_idempotent_and_ordered(org):
    offering, event_id = new_id(), new_id()
    payload = offering_created(offering, code="MA201", title="Algebra")
    assert deliver(org.id, cons.OFFERING_CREATED, payload, event_id=event_id) == cons.APPLIED
    assert deliver(org.id, cons.OFFERING_CREATED, payload, event_id=event_id) == cons.DUPLICATE
    assert deliver(org.id, cons.OFFERING_CREATED, payload) == cons.IGNORED
    status = {
        "course_offering_id": offering,
        "from_status": "planned",
        "to_status": "open",
        "changed_at": NOW.isoformat(),
    }
    assert deliver(org.id, cons.OFFERING_STATUS_CHANGED, status, occurred_at=NOW) == cons.APPLIED
    older = {**status, "to_status": "planned"}
    assert deliver(org.id, cons.OFFERING_STATUS_CHANGED, older, occurred_at=NOW - timedelta(hours=1)) == cons.STALE
    ref = row(OfferingRef, OfferingRef.course_offering_id, offering)
    assert (ref.course_code, ref.course_title, ref.status, ref.organisation_id) == ("MA201", "Algebra", "open", org.id)


def test_a_status_before_the_creation_is_kept(org):
    offering = new_id()
    status = {
        "course_offering_id": offering,
        "from_status": "planned",
        "to_status": "open",
        "changed_at": NOW.isoformat(),
    }
    deliver(org.id, cons.OFFERING_STATUS_CHANGED, status)
    assert deliver(org.id, cons.OFFERING_CREATED, offering_created(offering)) == cons.APPLIED
    ref = row(OfferingRef, OfferingRef.course_offering_id, offering)
    assert ref.status == "open" and ref.course_code == "CS101"


def test_instructor_assignment_and_its_end(client, org):
    c = Course(client, org)
    teacher_id, teacher = org.user("faculty")
    payload = assignment_created(c.offering, teacher_id)
    deliver(org.id, cons.ASSIGNMENT_CREATED, payload)
    assert c.get(f"/course-spaces/{c.space['id']}", teacher)["caller_is_instructor"] is True
    ended = {**payload, "ended_at": NOW.isoformat()}
    ended.pop("role"), ended.pop("contact_hours")
    deliver(org.id, cons.ASSIGNMENT_ENDED, ended, occurred_at=NOW + timedelta(minutes=1))
    assert c.call("GET", f"/course-spaces/{c.space['id']}", headers=teacher).status_code == 403
    # A late, older creation does not bring the assignment back.
    deliver(org.id, cons.ASSIGNMENT_CREATED, payload, occurred_at=NOW - timedelta(days=1))
    ref = row(InstructorRef, InstructorRef.instructor_assignment_id, payload["instructor_assignment_id"])
    assert ref.status == "ended"


def test_registration_withdrawal_and_section_moves(client, org):
    c = Course(client, org)
    c.material("For B", visible_section_ids=[c.section_b])
    person, student = org.user(STUDENT)
    reg = registration_confirmed(c.offering, person, c.section_a, name="Esha")
    deliver(org.id, cons.REGISTRATION_CONFIRMED, reg)
    assert c.get("/me/course-materials", student)["items"] == []
    move = {
        "registration_id": reg["registration_id"],
        "person_id": person,
        "course_offering_id": c.offering,
        "from_section_id": c.section_a,
        "to_section_id": c.section_b,
        "effective_on": "2026-11-05",
        "student_name": "Esha",
    }
    deliver(org.id, cons.SECTION_CHANGED, move, occurred_at=NOW + timedelta(minutes=1))
    assert [i["title"] for i in c.get("/me/course-materials", student)["items"]] == ["For B"]
    withdrawn = {**reg, "reason": "Dropped", "withdrawn_at": NOW.isoformat()}
    deliver(org.id, cons.REGISTRATION_WITHDRAWN, withdrawn, occurred_at=NOW + timedelta(minutes=2))
    assert c.call("GET", f"/course-spaces/{c.space['id']}", headers=student).status_code == 403
    ref = row(MemberRef, MemberRef.registration_id, reg["registration_id"])
    assert (ref.status, ref.section_id, ref.student_name) == ("withdrawn", c.section_b, "Esha")


@pytest.mark.parametrize(
    "name,payload",
    [
        (cons.OFFERING_CREATED, {"course_offering_id": "nope"}),
        (cons.OFFERING_CREATED, {**offering_created(new_id()), "course_title": "x" * 201}),
        (cons.ASSIGNMENT_CREATED, {"instructor_assignment_id": new_id(), "course_offering_id": new_id()}),
        (cons.REGISTRATION_CONFIRMED, {"registration_id": new_id(), "person_id": 5, "course_offering_id": new_id()}),
    ],
)
def test_malformed_events_are_refused_and_leave_nothing(org, name, payload):
    with pytest.raises(ValueError):
        deliver(org.id, name, payload)
    with SessionLocal() as db:
        for model in (OfferingRef, InstructorRef, MemberRef):
            assert db.scalars(select(model).where(model.organisation_id == org.id)).first() is None


def test_envelope_checks(org):
    assert cons.on_offering_created(None, _Event(None)) == cons.IGNORED
    with pytest.raises(cons.UnsupportedEventVersionError):
        deliver(org.id, cons.OFFERING_CREATED, offering_created(new_id()), version=2)
    with organisation_scope(new_id()), SessionLocal() as db, pytest.raises(RuntimeError):
        cons.on_offering_created(db, _Event(org.id))


class _Event:
    def __init__(self, organisation_id):
        self.id, self.name, self.version = new_id(), cons.OFFERING_CREATED, 1
        self.organisation_id, self.occurred_at, self.payload = organisation_id, NOW, offering_created(new_id())
