"""student-information.person.account-linked -> person_account, and a student's own reads through it.

`section_member.student_id` holds enrolment-registration's `person_id` (the student-information person); a student
signs in with their identity user id. `/me/schedule`, `/me/attendance-summary` and `/me/attendance-history` map one to
the other (classes.my_student_ids) and fall back to the user id while no link is known."""

import uuid
from datetime import timedelta
from pathlib import Path

import pytest
import yaml

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import BASE, NOW, STUDENT, Classroom, active_term, deliver, ok  # noqa: E402
from eos_core.db import SessionLocal, init_db  # noqa: E402
from eos_core.tenant import organisation_scope  # noqa: E402
from eos_timetable_attendance.application import consumers  # noqa: E402
from eos_timetable_attendance.application.consumers import (  # noqa: E402
    ACCOUNT_LINKED,
    REGISTRATION_CONFIRMED,
)
from eos_timetable_attendance.infrastructure import repository as repo  # noqa: E402
from eos_timetable_attendance.infrastructure.models import PersonAccount  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _tables():
    init_db()  # the consumer tests need no client, so the tables are made here (the file passes alone)


def uid() -> str:
    return str(uuid.uuid4())


def link(org_id, person_id, user_id, *, linked=True, at=NOW, event_id=None) -> str:
    payload = {
        "person_id": person_id,
        "identity_user_id": user_id if linked else None,
        "linked": linked,
        "previous_identity_user_id": None if linked else user_id,
    }
    return deliver(org_id, ACCOUNT_LINKED, payload, occurred_at=at, event_id=event_id)


def account(org_id, person_id) -> PersonAccount | None:
    with organisation_scope(org_id), SessionLocal() as db:
        return db.scalars(
            repo.q(db, PersonAccount).where(
                PersonAccount.organisation_id == org_id, PersonAccount.person_id == person_id
            )
        ).first()


def registered(room: Classroom, name: str = "Deepa Iyer") -> str:
    """A student whose registration arrives by person id (enrolment-registration's payload)."""
    person = uid()
    deliver(
        room.org.id,
        REGISTRATION_CONFIRMED,
        {
            "registration_id": uid(),
            "person_id": person,
            "course_offering_id": room.ids["offering"],
            "section_id": room.ids["section"],
            "academic_period_id": room.ids["period"],
            "registration_type": "regular",
            "student_name": name,
            "roll_number": "R-9",
            "confirmed_at": "2026-11-01T10:00:00+00:00",
        },
    )
    return person


# ---------------------------------------------------------------- the consumer


def test_the_published_payload_carries_the_fields_the_handler_reads():
    contract = (
        Path(__file__).resolve().parents[5] / "modules/student-lifecycle/student-information/contracts/events.yaml"
    )
    if not contract.exists():
        pytest.skip("the student-information contract is not in this checkout")
    events = {e["name"]: e for e in yaml.safe_load(contract.read_text(encoding="utf-8"))["events"]}
    if ACCOUNT_LINKED not in events:
        pytest.skip("student-information publishes person.account-linked from its contract 0.2.0 (its own PR)")
    assert "timetable-attendance" in events[ACCOUNT_LINKED]["consumers"]
    assert {"person_id", "identity_user_id", "linked"} <= set(events[ACCOUNT_LINKED]["payload"])


def test_a_link_is_applied_once(org):
    person, user, event_id = uid(), uid(), uid()
    assert link(org.id, person, user, event_id=event_id) == "applied"
    assert link(org.id, person, user, event_id=event_id) == "duplicate"
    assert link(org.id, person, user) == "applied"  # a republish of the same link changes nothing
    row = account(org.id, person)
    assert (row.identity_user_id, row.organisation_id) == (user, org.id)


def test_an_older_link_never_replaces_a_newer_one(org):
    person, first, second = uid(), uid(), uid()
    assert link(org.id, person, second, at=NOW) == "applied"
    assert link(org.id, person, first, at=NOW - timedelta(hours=1)) == "stale"
    assert link(org.id, person, second, linked=False, at=NOW - timedelta(minutes=1)) == "stale"
    assert account(org.id, person).identity_user_id == second
    assert link(org.id, person, second, linked=False, at=NOW + timedelta(minutes=1)) == "applied"
    assert account(org.id, person).identity_user_id is None


@pytest.mark.parametrize(
    "payload",
    [
        {"identity_user_id": "u", "linked": True},
        {"person_id": "p", "identity_user_id": "u", "linked": "yes"},
        {"person_id": "p", "identity_user_id": None, "linked": True},
        {"person_id": "p", "identity_user_id": "not-a-uuid", "linked": True},
    ],
)
def test_a_malformed_link_is_refused(org, payload):
    payload = {k: (uid() if v in ("p", "u") else v) for k, v in payload.items()}
    with pytest.raises(ValueError):
        deliver(org.id, ACCOUNT_LINKED, payload)
    assert consumers.CONSUMERS[ACCOUNT_LINKED] is consumers.on_account_linked


def test_a_link_without_an_organisation_is_not_ours():
    payload = {"person_id": uid(), "identity_user_id": uid(), "linked": True}
    assert deliver(None, ACCOUNT_LINKED, payload) == "ignored"


def test_a_link_lands_only_in_its_own_organisation(org, other_org):
    person, user = uid(), uid()
    link(other_org.id, person, user)
    assert account(org.id, person) is None and account(other_org.id, person).identity_user_id == user
    with SessionLocal() as db:  # no organisation on the session: nothing
        assert list(db.scalars(repo.q(db, PersonAccount))) == []


# ---------------------------------------------------------------- a student's own reads


def test_a_student_registered_by_person_id_sees_their_schedule_once_linked(client, org):
    room = Classroom(client, org, students=0)
    person = registered(room)
    c = room.new_class("2026-11-03T09:00:00+00:00")
    user_id, student = org.user(STUDENT)
    schedule = f"{BASE}/me/schedule?date=2026-11-03"
    assert ok(client.get(schedule, headers=student))["items"] == []
    link(org.id, person, user_id)
    assert [x["id"] for x in ok(client.get(schedule, headers=student))["items"]] == [c["id"]]


def test_a_student_registered_by_person_id_sees_their_attendance_once_linked(client, org):
    room = Classroom(client, org, students=0)
    active_term(org.id, room.ids["period"])
    person = registered(room)
    c, _ = room.held({person: "present"})
    user_id, student = org.user(STUDENT)
    summary, history = f"{BASE}/me/attendance-summary", f"{BASE}/me/attendance-history"
    assert ok(client.get(summary, headers=student))["items"] == []
    assert ok(client.get(history, headers=student))["items"] == []
    link(org.id, person, user_id)
    mine = ok(client.get(summary, headers=student))
    assert mine["student_id"] == person
    [item] = mine["items"]
    assert (item["classes_held"], item["attended"], item["percentage"]) == (1, 1, 100.0)
    past = ok(client.get(history, headers=student))
    assert past["student_id"] == person
    assert [(x["scheduled_class_id"], x["status"]) for x in past["items"]] == [(c["id"], "present")]


def test_data_kept_under_the_user_id_still_reaches_the_student_after_a_link(client, org):
    """Dev and test data allocate students by user id; a link arriving later keeps those records theirs."""
    room = Classroom(client, org, students=1)
    active_term(org.id, room.ids["period"])
    [user_id] = room.students
    room.held({user_id: "late"})
    student = org.user(STUDENT, user_id=user_id)[1]
    link(org.id, uid(), user_id)
    [item] = ok(client.get(f"{BASE}/me/attendance-summary", headers=student))["items"]
    assert item["attended"] == 1
    assert ok(client.get(f"{BASE}/me/schedule?date=2026-11-03", headers=student))["items"]


def test_unlinking_ends_the_mapping(client, org):
    room = Classroom(client, org, students=0)
    person = registered(room)
    room.new_class("2026-11-03T09:00:00+00:00")
    user_id, student = org.user(STUDENT)
    link(org.id, person, user_id)
    schedule = f"{BASE}/me/schedule?date=2026-11-03"
    assert ok(client.get(schedule, headers=student))["items"]
    link(org.id, person, user_id, linked=False, at=NOW + timedelta(minutes=1))
    assert ok(client.get(schedule, headers=student))["items"] == []


def test_a_link_in_another_organisation_maps_nothing_here(client, org, other_org):
    room = Classroom(client, org, students=0)
    person = registered(room)
    room.new_class("2026-11-03T09:00:00+00:00")
    user_id, student = org.user(STUDENT)
    link(other_org.id, person, user_id)
    assert ok(client.get(f"{BASE}/me/schedule?date=2026-11-03", headers=student))["items"] == []
