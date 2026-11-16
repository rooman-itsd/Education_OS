"""The enrolment-registration consumers fill `section_member` (FR-7): confirmation opens a membership, a section
change moves it, a withdrawal ends it. Delivery is at-least-once and unordered, so duplicates change nothing, any
arrival order gives the same memberships, and each organisation keeps its own. Payloads are shaped as
modules/student-lifecycle/enrolment-registration/contracts/events.yaml publishes them."""

import itertools
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
import yaml

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import BASE, Classroom, deliver, ok  # noqa: E402
from eos_core.db import SessionLocal  # noqa: E402
from eos_timetable_attendance.application import consumers  # noqa: E402
from eos_timetable_attendance.application.consumers import (  # noqa: E402
    REGISTRATION_CONFIRMED,
    REGISTRATION_WITHDRAWN,
    SECTION_ALLOCATION_CHANGED,
)
from eos_timetable_attendance.infrastructure import repository as repo  # noqa: E402
from eos_timetable_attendance.infrastructure.models import RegistrationRef, SectionMember  # noqa: E402

MODULE = Path(__file__).resolve().parents[2]
T0 = datetime(2026, 11, 1, 9, tzinfo=UTC)


def uid() -> str:
    return str(uuid.uuid4())


class Registration:
    """One registration's ids and its three payloads."""

    def __init__(self, section: str | None = None, offering: str | None = None, person: str | None = None) -> None:
        self.id, self.person = uid(), person or uid()
        self.offering, self.section = offering or uid(), section or uid()

    def confirmed(self, at="2026-11-02T10:00:00+05:30", name="Asha Rao", section=None) -> dict:
        return {
            "registration_id": self.id,
            "person_id": self.person,
            "course_offering_id": self.offering,
            "section_id": section or self.section,
            "academic_period_id": uid(),
            "registration_type": "regular",
            "student_name": name,
            "roll_number": "R-1",
            "confirmed_at": at,
        }

    def withdrawn(self, at="2026-11-20T12:00:00+00:00") -> dict:
        return {
            "registration_id": self.id,
            "person_id": self.person,
            "course_offering_id": self.offering,
            "section_id": self.section,
            "reason": "changed programme",
            "withdrawn_at": at,
        }

    def moved(self, to: str, on="2026-11-10", frm=None, name="Asha Rao") -> dict:
        return {
            "registration_id": self.id,
            "person_id": self.person,
            "course_offering_id": self.offering,
            "from_section_id": frm or self.section,
            "to_section_id": to,
            "effective_on": on,
            "student_name": name,
        }


def members(org_id: str, student_id: str | None = None) -> list[tuple]:
    with SessionLocal() as db:
        db.info["organisation_id"] = org_id
        query = repo.q(db, SectionMember)
        if student_id:
            query = query.where(SectionMember.student_id == student_id)
        rows = db.scalars(query)
        return sorted((r.section_id, r.allocated_from, r.allocated_to, r.student_name) for r in rows)


def d(text: str) -> date:
    return date.fromisoformat(text)


def test_the_published_payloads_carry_the_fields_the_handlers_read():
    contract = MODULE.parents[1] / "student-lifecycle" / "enrolment-registration" / "contracts" / "events.yaml"
    if not contract.exists():
        pytest.skip("the enrolment-registration contract is not in this checkout")
    events = {e["name"]: e for e in yaml.safe_load(contract.read_text(encoding="utf-8"))["events"]}
    read = {
        REGISTRATION_CONFIRMED: {
            "registration_id",
            "person_id",
            "course_offering_id",
            "section_id",
            "student_name",
            "confirmed_at",
        },
        REGISTRATION_WITHDRAWN: {"registration_id", "person_id", "course_offering_id", "section_id", "withdrawn_at"},
        SECTION_ALLOCATION_CHANGED: {
            "registration_id",
            "person_id",
            "course_offering_id",
            "from_section_id",
            "to_section_id",
            "effective_on",
            "student_name",
        },
    }
    for name, fields in read.items():
        assert "timetable-attendance" in events[name]["consumers"], name
        assert fields <= set(events[name]["payload"]), (name, fields - set(events[name]["payload"]))


def test_confirmed_opens_a_membership_from_the_confirmation_date(org):
    r = Registration()
    assert deliver(org.id, REGISTRATION_CONFIRMED, r.confirmed()) == "applied"
    assert members(org.id, r.person) == [(r.section, d("2026-11-02"), None, "Asha Rao")]
    with SessionLocal() as db:
        db.info["organisation_id"] = org.id
        ref = db.scalars(repo.q(db, RegistrationRef)).one()
        assert (ref.student_id, ref.course_offering_id, ref.confirmed_on) == (r.person, r.offering, d("2026-11-02"))


def test_the_confirmation_date_is_read_in_the_offset_it_carries(org):
    r = Registration()
    deliver(org.id, REGISTRATION_CONFIRMED, r.confirmed(at="2026-11-02T23:30:00-05:00"))  # 3 Nov in UTC
    assert members(org.id, r.person)[0][1] == d("2026-11-02")


def test_withdrawn_ends_the_membership_on_the_withdrawal_date(org):
    r = Registration()
    deliver(org.id, REGISTRATION_CONFIRMED, r.confirmed())
    assert deliver(org.id, REGISTRATION_WITHDRAWN, r.withdrawn()) == "applied"
    assert members(org.id, r.person) == [(r.section, d("2026-11-02"), d("2026-11-20"), "Asha Rao")]


def test_a_section_change_closes_the_old_section_the_day_before_and_opens_the_new_one(org):
    r, b, c = Registration(), uid(), uid()
    deliver(org.id, REGISTRATION_CONFIRMED, r.confirmed())
    assert deliver(org.id, SECTION_ALLOCATION_CHANGED, r.moved(b, on="2026-11-10", name="Asha R.")) == "applied"
    deliver(org.id, SECTION_ALLOCATION_CHANGED, r.moved(c, on="2026-11-15", frm=b, name="Asha R."))
    assert members(org.id, r.person) == sorted(
        [
            (r.section, d("2026-11-02"), d("2026-11-09"), "Asha R."),
            (b, d("2026-11-10"), d("2026-11-14"), "Asha R."),
            (c, d("2026-11-15"), None, "Asha R."),
        ]
    )
    deliver(org.id, REGISTRATION_WITHDRAWN, r.withdrawn(at="2026-11-12T08:00:00+00:00"))
    assert members(org.id, r.person) == sorted(
        [
            (r.section, d("2026-11-02"), d("2026-11-09"), "Asha R."),
            (b, d("2026-11-10"), d("2026-11-12"), "Asha R."),
        ]
    )


def test_a_move_on_the_confirmation_day_leaves_no_empty_membership(org):
    r, b = Registration(), uid()
    deliver(org.id, REGISTRATION_CONFIRMED, r.confirmed())
    deliver(org.id, SECTION_ALLOCATION_CHANGED, r.moved(b, on="2026-11-02"))
    assert members(org.id, r.person) == [(b, d("2026-11-02"), None, "Asha Rao")]


def test_the_same_event_twice_and_a_copy_with_a_new_id_change_nothing(org):
    r, b = Registration(), uid()
    event_id = uid()
    assert deliver(org.id, REGISTRATION_CONFIRMED, r.confirmed(), event_id=event_id) == "applied"
    assert deliver(org.id, REGISTRATION_CONFIRMED, r.confirmed(), event_id=event_id) == "duplicate"
    assert deliver(org.id, REGISTRATION_CONFIRMED, r.confirmed(at="2026-11-05T10:00:00+00:00")) == "ignored"
    deliver(org.id, SECTION_ALLOCATION_CHANGED, r.moved(b))
    assert deliver(org.id, SECTION_ALLOCATION_CHANGED, r.moved(b)) == "ignored"
    deliver(org.id, REGISTRATION_WITHDRAWN, r.withdrawn())
    assert deliver(org.id, REGISTRATION_WITHDRAWN, r.withdrawn(at="2026-11-25T12:00:00+00:00")) == "ignored"
    assert members(org.id, r.person) == sorted(
        [(r.section, d("2026-11-02"), d("2026-11-09"), "Asha Rao"), (b, d("2026-11-10"), d("2026-11-20"), "Asha Rao")]
    )


def test_every_arrival_order_gives_the_same_memberships(org):
    expected = None
    for i, order in enumerate(itertools.permutations(("confirmed", "moved", "withdrawn"))):
        r, b = Registration(person=None), uid()
        payloads = {
            "confirmed": (REGISTRATION_CONFIRMED, r.confirmed()),
            "moved": (SECTION_ALLOCATION_CHANGED, r.moved(b)),
            "withdrawn": (REGISTRATION_WITHDRAWN, r.withdrawn()),
        }
        for step, kind in enumerate(order):
            name, payload = payloads[kind]
            deliver(org.id, name, payload, occurred_at=T0 + timedelta(minutes=step))
        got = sorted(((s == r.section, s == b, a, z) for s, a, z, _ in members(org.id, r.person)), key=lambda m: m[2])
        expected = expected or got
        assert got == expected, (i, order)
    assert expected == [
        (True, False, d("2026-11-02"), d("2026-11-09")),
        (False, True, d("2026-11-10"), d("2026-11-20")),
    ]


def test_a_move_before_the_confirmation_opens_the_new_section_and_the_confirmation_completes_it(org):
    r, b = Registration(), uid()
    deliver(org.id, SECTION_ALLOCATION_CHANGED, r.moved(b))
    assert members(org.id, r.person) == [(b, d("2026-11-10"), None, "Asha Rao")]
    deliver(org.id, REGISTRATION_CONFIRMED, r.confirmed())
    assert len(members(org.id, r.person)) == 2


def test_the_latest_name_wins_whatever_the_arrival_order(org):
    r, b = Registration(), uid()
    deliver(org.id, SECTION_ALLOCATION_CHANGED, r.moved(b, name="New Name"), occurred_at=T0 + timedelta(hours=1))
    deliver(org.id, REGISTRATION_CONFIRMED, r.confirmed(name="Old Name"), occurred_at=T0)
    assert {m[3] for m in members(org.id, r.person)} == {"New Name"}


def test_a_registration_cannot_change_student_or_offering_and_malformed_events_write_nothing(org):
    r = Registration()
    deliver(org.id, REGISTRATION_CONFIRMED, r.confirmed())
    other = {**r.confirmed(), "person_id": uid()}
    with pytest.raises(ValueError, match="one student"):
        deliver(org.id, REGISTRATION_CONFIRMED, other)
    for name, payload in (
        (REGISTRATION_CONFIRMED, {**Registration().confirmed(), "confirmed_at": "2026-11-02"}),
        (REGISTRATION_CONFIRMED, {**Registration().confirmed(), "section_id": "x"}),
        (REGISTRATION_WITHDRAWN, {**Registration().withdrawn(), "withdrawn_at": None}),
        (SECTION_ALLOCATION_CHANGED, {**Registration().moved(uid()), "effective_on": "soon"}),
    ):
        with pytest.raises(ValueError):
            deliver(org.id, name, payload)
    assert members(org.id) == [(r.section, d("2026-11-02"), None, "Asha Rao")]


def test_each_organisation_keeps_its_own_memberships(org, other_org):
    r = Registration()
    deliver(org.id, REGISTRATION_CONFIRMED, r.confirmed())
    deliver(other_org.id, REGISTRATION_CONFIRMED, r.confirmed(at="2026-11-05T10:00:00+00:00"))
    deliver(other_org.id, REGISTRATION_WITHDRAWN, r.withdrawn())
    assert members(org.id) == [(r.section, d("2026-11-02"), None, "Asha Rao")]
    assert members(other_org.id) == [(r.section, d("2026-11-05"), d("2026-11-20"), "Asha Rao")]
    with SessionLocal() as db:  # no organisation on the session: nothing
        assert list(db.scalars(repo.q(db, SectionMember))) == []
        assert list(db.scalars(repo.q(db, RegistrationRef))) == []


def test_an_event_is_not_applied_under_another_organisations_scope(org, other_org):
    from conftest import FakeEvent
    from eos_core.tenant import organisation_scope

    event = FakeEvent(REGISTRATION_CONFIRMED, org.id, Registration().confirmed())
    with organisation_scope(other_org.id), SessionLocal() as db, pytest.raises(RuntimeError):
        consumers.CONSUMERS[REGISTRATION_CONFIRMED](db, event)
    assert members(org.id) == [] and members(other_org.id) == []


def test_a_session_opened_after_a_confirmed_registration_snapshots_that_student(client, org):
    room = Classroom(client, org, students=0)
    r = Registration(section=room.ids["section"], offering=room.ids["offering"])
    late = Registration(section=room.ids["section"], offering=room.ids["offering"])
    gone = Registration(section=room.ids["section"], offering=room.ids["offering"])
    deliver(org.id, REGISTRATION_CONFIRMED, r.confirmed(at="2026-11-02T10:00:00+00:00", name="Asha Rao"))
    deliver(org.id, REGISTRATION_CONFIRMED, late.confirmed(at="2026-11-04T10:00:00+00:00", name="Late Joiner"))
    deliver(org.id, REGISTRATION_CONFIRMED, gone.confirmed(at="2026-11-01T10:00:00+00:00", name="Left Early"))
    deliver(org.id, REGISTRATION_WITHDRAWN, gone.withdrawn(at="2026-11-02T10:00:00+00:00"))
    c = room.new_class("2026-11-03T09:00:00+00:00")
    s = room.open(c["id"])
    assert s["counts"]["eligible"] == 1
    records = ok(client.get(f"{BASE}/attendance-sessions/{s['id']}/records", headers=room.faculty))["items"]
    assert [(x["student_id"], x["student_name"]) for x in records] == [(r.person, "Asha Rao")]
    student = org.user("timetable-attendance-student", user_id=r.person)[1]
    assert [x["id"] for x in ok(client.get(f"{BASE}/me/schedule?date=2026-11-03", headers=student))["items"]] == [
        c["id"]
    ]
