"""Events go to the outbox with exactly the payload fields in contracts/events.yaml, never organisation_id (it is on
the envelope), and always the fields academic-management's roster code requires. Every change is audited."""

from __future__ import annotations

from datetime import date

import yaml
from conftest import CONTRACTS, add_enrolment, add_window
from eos_core.db import new_id
from eos_core.events import OutboxEvent
from eos_enrolment_registration.application import service as svc
from eos_enrolment_registration.application.service import EnrolmentError
from eos_enrolment_registration.infrastructure.models import AuditEntry

PAYLOADS = {
    ev["name"]: set(ev["payload"])
    for ev in yaml.safe_load((CONTRACTS / "events.yaml").read_text(encoding="utf-8"))["events"]
}
# academic-management's roster reads these with p["..."]; a missing one is rejected as malformed_payload.
ROSTER_REQUIRED = {
    "enrolment-registration.course-registration.confirmed": {
        "registration_id",
        "person_id",
        "course_offering_id",
        "section_id",
    },
    "enrolment-registration.course-registration.withdrawn": {
        "registration_id",
        "person_id",
        "course_offering_id",
        "section_id",
    },
    "enrolment-registration.section-allocation.changed": {
        "registration_id",
        "person_id",
        "course_offering_id",
        "from_section_id",
        "to_section_id",
    },
}


def outbox(db, org) -> list[OutboxEvent]:
    return db.query(OutboxEvent).filter(OutboxEvent.organisation_id == org).order_by(OutboxEvent.occurred_at).all()


def check(event: OutboxEvent, org: str, actor: str) -> None:
    assert set(event.payload) == PAYLOADS[event.name], event.name
    assert "organisation_id" not in event.payload
    assert ROSTER_REQUIRED.get(event.name, set()) <= set(event.payload)
    assert all(event.payload[k] is not None for k in ROSTER_REQUIRED.get(event.name, set()))
    assert (event.organisation_id, event.actor) == (org, actor)


def test_every_event_matches_the_contract(db, staff, org):
    term = new_id()
    add_window(db, org, term)
    enrolment = svc.enrol(
        db, staff, person_id=new_id(), student_name="Ana", programme_id=new_id(), start_academic_period_id=term
    )
    reg = svc.register(
        db,
        staff,
        programme_enrolment_id=enrolment["id"],
        course_offering_id=new_id(),
        section_id=new_id(),
        academic_period_id=term,
    )
    svc.change_section(db, staff, reg["id"], new_id(), date(2026, 11, 2))
    svc.withdraw_registration(db, staff, reg["id"], "dropped")
    svc.withdraw_enrolment(db, staff, enrolment["id"], "left")

    names = [ev.name for ev in outbox(db, org)]
    assert names == [
        "enrolment-registration.programme-enrolment.created",
        "enrolment-registration.course-registration.confirmed",
        "enrolment-registration.section-allocation.changed",
        "enrolment-registration.course-registration.withdrawn",
        "enrolment-registration.programme-enrolment.withdrawn",
    ]
    for event in outbox(db, org):
        check(event, org, staff.user_id)
    confirmed = outbox(db, org)[1].payload
    assert (confirmed["roll_number"], confirmed["student_name"], confirmed["registration_type"]) == (
        enrolment["roll_number"],
        "Ana",
        "regular",
    )
    assert outbox(db, org)[2].payload["effective_on"] == "2026-11-02"


def test_enrolment_withdrawal_withdraws_each_registration_with_its_own_event(db, staff, org):
    term = new_id()
    add_window(db, org, term)
    student = add_enrolment(db, org)
    for _ in range(2):
        svc.register(
            db,
            staff,
            programme_enrolment_id=student.id,
            course_offering_id=new_id(),
            section_id=new_id(),
            academic_period_id=term,
        )
    svc.withdraw_enrolment(db, staff, student.id, "left")
    names = [ev.name.rsplit(".", 2)[-2] + "." + ev.name.rsplit(".", 1)[-1] for ev in outbox(db, org)]
    assert names == [
        "course-registration.confirmed",
        "course-registration.confirmed",
        "course-registration.withdrawn",
        "course-registration.withdrawn",
        "programme-enrolment.withdrawn",
    ]


def test_audit_rows_and_no_event_for_windows_or_completion(db, staff, org):
    svc.set_window(db, staff, new_id(), *_window_times())
    enrolment = add_enrolment(db, org)
    svc.complete_enrolment(db, staff, enrolment.id)
    assert outbox(db, org) == []
    actions = sorted(a.action for a in db.query(AuditEntry).filter(AuditEntry.organisation_id == org))
    assert actions == ["enrolment_completed", "window_set"]


def test_a_refused_change_writes_nothing(db, staff, org):
    student = add_enrolment(db, org)
    try:
        svc.register(
            db,
            staff,
            programme_enrolment_id=student.id,
            course_offering_id=new_id(),
            section_id=new_id(),
            academic_period_id=new_id(),
        )
    except EnrolmentError as exc:
        assert exc.code == "window_closed"
    assert outbox(db, org) == []
    assert db.query(AuditEntry).filter(AuditEntry.organisation_id == org).count() == 0


def _window_times():
    from datetime import timedelta

    from eos_core.db import utcnow

    now = utcnow()
    return now, now + timedelta(days=1)
