"""The roster read model (FR-14, FR-15): enrolment-registration's agreed events applied by registration_id, safe under
duplicate and out-of-order delivery, and read back through GET /offerings/{id}/roster and GET /me/offerings.

The event fixtures follow the payloads agreed with enrolment-registration on issue #100; they are test fixtures, not
a dependency on an unpublished contract file."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see test_api_deps.py)")

from conftest import BASE, assign, make_course, make_offering, make_term, ok, open_offering  # noqa: E402
from eos_academic_management.application import roster  # noqa: E402
from eos_core.db import SessionLocal, new_id  # noqa: E402

HOD = "department-admin"


def deliver(name: str, organisation_id: str, payload: dict, *, event_id: str | None = None, version: int = 1) -> str:
    envelope = {
        "id": event_id or new_id(),
        "name": f"enrolment-registration.{name}",
        "version": version,
        "organisation_id": organisation_id,
        "actor": None,
        "occurred_at": "2026-10-22T09:00:00+00:00",
        "payload": payload,
    }
    with SessionLocal() as db:
        return roster.handle_event(db, envelope)


def confirmed(o, section, registration_id=None, person_id=None, **extra) -> dict:
    return {
        "registration_id": registration_id or new_id(),
        "person_id": person_id or new_id(),
        "course_offering_id": o["id"],
        "section_id": section["id"],
        "academic_period_id": o["academic_period_id"],
        "confirmed_at": "2026-10-22T08:00:00+00:00",
        **extra,
    }


@pytest.fixture
def world(client, org):
    """An open offering with sections A (capacity 2) and B (capacity 1), taught by one faculty member."""
    _, h = org.user(HOD)
    _, admin = org.user("org-admin")
    term, course = make_term(client, admin), make_course(client, admin)
    o = make_offering(client, h, course["id"], term["id"], (("A", 2), ("B", 1)))
    teacher, teacher_h = org.user("faculty")
    open_offering(client, h, o["id"], teacher)
    o = ok(client.get(f"{BASE}/offerings/{o['id']}", headers=h))
    a, b = o["sections"]
    return {"h": h, "o": o, "a": a, "b": b, "teacher": teacher, "teacher_h": teacher_h, "org": org}


def roster_of(client, w, **query) -> dict:
    qs = "&".join(f"{k}={v}" for k, v in query.items())
    return ok(client.get(f"{BASE}/offerings/{w['o']['id']}/roster?{qs}", headers=w["h"]))


# ---------------------------------------------------------------- confirmation and idempotency


def test_a_confirmation_adds_the_learner_by_person_id_without_a_roll_number(client, world):
    w = world
    p = confirmed(w["o"], w["a"], student_name="Asha")  # no roll_number: it is optional
    assert deliver("course-registration.confirmed", w["org"].id, p) == roster.APPLIED
    r = roster_of(client, w)
    assert r["total"] == 1
    item = r["items"][0]
    assert (item["person_id"], item["section_code"], item["student_name"]) == (p["person_id"], "A", "Asha")
    assert "roll_number" not in item


def test_duplicate_delivery_of_the_same_event_is_applied_once(client, world):
    w = world
    p, event_id = confirmed(w["o"], w["a"], roll_number="R1"), new_id()
    assert deliver("course-registration.confirmed", w["org"].id, p, event_id=event_id) == roster.APPLIED
    assert deliver("course-registration.confirmed", w["org"].id, p, event_id=event_id) == roster.DUPLICATE
    assert roster_of(client, w)["total"] == 1


def test_a_second_confirmation_of_one_registration_upserts_the_same_row(client, world):
    w = world
    p = confirmed(w["o"], w["a"])
    deliver("course-registration.confirmed", w["org"].id, p)
    deliver("course-registration.confirmed", w["org"].id, {**p, "roll_number": "R7", "student_name": "Asha K"})
    r = roster_of(client, w)
    assert r["total"] == 1 and (r["items"][0]["roll_number"], r["items"][0]["student_name"]) == ("R7", "Asha K")


# ---------------------------------------------------------------- withdrawal


def test_withdrawal_keeps_the_row_and_marks_it_withdrawn(client, world):
    w = world
    p = confirmed(w["o"], w["a"])
    deliver("course-registration.confirmed", w["org"].id, p)
    withdrawal = {k: p[k] for k in ("registration_id", "person_id", "course_offering_id", "section_id")}
    assert (
        deliver("course-registration.withdrawn", w["org"].id, {**withdrawal, "withdrawn_at": "2026-10-23T00:00:00Z"})
        == roster.APPLIED
    )
    assert roster_of(client, w)["total"] == 0  # the roster lists enrolled learners
    from eos_academic_management.infrastructure.models import RosterEntryRow
    from sqlalchemy import select

    with SessionLocal() as db:
        row = db.scalars(select(RosterEntryRow).where(RosterEntryRow.registration_id == p["registration_id"])).one()
        assert (row.status, row.withdrawn_at is not None) == ("withdrawn", True)  # kept, not deleted


def test_a_late_confirmation_never_revives_a_withdrawn_registration(client, world):
    w = world
    p = confirmed(w["o"], w["a"])
    withdrawal = {k: p[k] for k in ("registration_id", "person_id", "course_offering_id", "section_id")}
    assert deliver("course-registration.withdrawn", w["org"].id, withdrawal) == roster.APPLIED  # arrived first
    assert deliver("course-registration.confirmed", w["org"].id, p) == roster.STALE
    assert roster_of(client, w)["total"] == 0


# ---------------------------------------------------------------- section changes


def test_a_section_change_moves_the_same_registration(client, world):
    w = world
    p = confirmed(w["o"], w["a"])
    deliver("course-registration.confirmed", w["org"].id, p)
    move = {
        "registration_id": p["registration_id"],
        "person_id": p["person_id"],
        "course_offering_id": w["o"]["id"],
        "from_section_id": w["a"]["id"],
        "to_section_id": w["b"]["id"],
    }
    assert deliver("section-allocation.changed", w["org"].id, move) == roster.APPLIED
    r = roster_of(client, w)
    assert r["total"] == 1 and r["items"][0]["section_code"] == "B"
    assert deliver("section-allocation.changed", w["org"].id, move) == roster.STALE  # no longer in section A


def test_a_section_change_before_its_confirmation_keeps_the_new_section(client, world):
    w = world
    p = confirmed(w["o"], w["a"], roll_number="R2")
    move = {
        "registration_id": p["registration_id"],
        "person_id": p["person_id"],
        "course_offering_id": w["o"]["id"],
        "from_section_id": w["a"]["id"],
        "to_section_id": w["b"]["id"],
    }
    assert deliver("section-allocation.changed", w["org"].id, move) == roster.APPLIED
    assert deliver("course-registration.confirmed", w["org"].id, p) == roster.APPLIED
    item = roster_of(client, w)["items"][0]
    assert (item["section_code"], item["roll_number"]) == ("B", "R2")


# ---------------------------------------------------------------- admission rules


def test_a_full_section_rejects_new_registrations(client, world):
    w = world
    deliver("course-registration.confirmed", w["org"].id, confirmed(w["o"], w["b"]))  # B holds 1
    assert (
        deliver("course-registration.confirmed", w["org"].id, confirmed(w["o"], w["b"])) == roster.REJECTED_SECTION_FULL
    )
    assert roster_of(client, w, section_id=w["b"]["id"])["total"] == 1


def test_a_section_with_students_is_closed_not_deleted_and_takes_no_one_new(client, world):
    w = world
    deliver("course-registration.confirmed", w["org"].id, confirmed(w["o"], w["a"]))
    closed = ok(client.patch(f"{BASE}/sections/{w['a']['id']}", json={"status": "closed"}, headers=w["h"]))
    assert (closed["status"], closed["enrolled_count"]) == ("closed", 1)
    assert (
        deliver("course-registration.confirmed", w["org"].id, confirmed(w["o"], w["a"]))
        == roster.REJECTED_SECTION_CLOSED
    )
    assert roster_of(client, w)["total"] == 1  # the enrolled learner stays on the roster


def test_an_offering_that_is_not_open_rejects_registrations(client, org):
    _, admin = org.user("org-admin")
    term, course = make_term(client, admin), make_course(client, admin)
    o = make_offering(client, admin, course["id"], term["id"])  # planned
    assert (
        deliver("course-registration.confirmed", org.id, confirmed(o, o["sections"][0]))
        == roster.REJECTED_OFFERING_NOT_OPEN
    )


def test_unknown_names_unsupported_versions_and_foreign_sections_are_not_applied(client, world):
    w = world
    p = confirmed(w["o"], w["a"])
    assert deliver("course-registration.amended", w["org"].id, p) == roster.IGNORED
    assert deliver("course-registration.confirmed", w["org"].id, p, version=2) == roster.IGNORED
    assert roster_of(client, w)["total"] == 0


def test_an_event_of_another_organisation_cannot_touch_this_roster(client, world, other_org):
    w = world
    p = confirmed(w["o"], w["a"])
    assert deliver("course-registration.confirmed", other_org.id, p) == roster.REJECTED_UNKNOWN_SECTION
    assert roster_of(client, w)["total"] == 0


# ---------------------------------------------------------------- reading the roster (FR-15)


def test_faculty_read_only_rosters_of_offerings_they_teach(client, world, org):
    w = world
    deliver("course-registration.confirmed", w["org"].id, confirmed(w["o"], w["a"]))
    mine = client.get(f"{BASE}/offerings/{w['o']['id']}/roster", headers=w["teacher_h"])
    assert (mine.status_code, mine.json()["total"]) == (200, 1)
    _, stranger = org.user("faculty")
    other = client.get(f"{BASE}/offerings/{w['o']['id']}/roster", headers=stranger)
    assert (other.status_code, other.json()["detail"]["code"]) == (403, "forbidden")
    _, student = org.user("student")
    assert client.get(f"{BASE}/offerings/{w['o']['id']}/roster", headers=student).status_code == 403


def test_my_offerings_lists_what_the_caller_teaches_with_counts(client, world):
    w = world
    deliver("course-registration.confirmed", w["org"].id, confirmed(w["o"], w["a"]))
    deliver("course-registration.confirmed", w["org"].id, confirmed(w["o"], w["b"]))
    mine = ok(
        client.get(f"{BASE}/me/offerings?academic_period_id={w['o']['academic_period_id']}", headers=w["teacher_h"])
    )
    (item,) = mine["items"]
    assert (item["course_offering_id"], item["role"], item["enrolled_count"]) == (w["o"]["id"], "primary", 2)
    assert sorted((s["code"], s["enrolled_count"]) for s in item["sections"]) == [("A", 1), ("B", 1)]


def test_a_section_only_assignment_lists_only_that_section(client, world, org):
    w = world
    ta, ta_h = org.user("faculty")
    assign(client, w["h"], w["o"]["id"], ta, role="teaching_assistant", hours=2, section_id=w["b"]["id"])
    (item,) = ok(client.get(f"{BASE}/me/offerings?academic_period_id={w['o']['academic_period_id']}", headers=ta_h))[
        "items"
    ]
    assert [s["code"] for s in item["sections"]] == ["B"]


# ---------------------------------------------------------------- the term of /me/offerings; withdrawals and malformed events


def test_my_offerings_needs_a_term_that_exists(client, org):
    """The contract's academic_period_id is a required uuid: no active term is 404 active_term_not_found, an unknown
    term is 404, and a value that is not a uuid is refused (the id was echoed back before)."""
    _, teacher_h = org.user("faculty")
    r = client.get(f"{BASE}/me/offerings", headers=teacher_h)
    assert (r.status_code, r.json()["detail"]["code"]) == (404, "active_term_not_found")
    unknown = client.get(f"{BASE}/me/offerings?academic_period_id={new_id()}", headers=teacher_h)
    assert (unknown.status_code, unknown.json()["detail"]["code"]) == (404, "not_found")
    assert client.get(f"{BASE}/me/offerings?academic_period_id=not-a-uuid", headers=teacher_h).status_code == 422
    _, admin = org.user("org-admin")
    term = make_term(client, admin)
    ok(client.post(f"{BASE}/terms/{term['id']}/activate", headers=admin))
    assert ok(client.get(f"{BASE}/me/offerings", headers=teacher_h)) == {"academic_period_id": term["id"], "items": []}


def test_a_withdrawal_before_its_confirmation_names_a_section_of_the_offering(client, world):
    """The row is written with the section's offering, so the foreign key holds on PostgreSQL (SQLite does not
    enforce it unless asked, hence the pragma): a withdrawal naming a section of another offering is rejected."""
    from sqlalchemy import text

    w = world
    stray = {
        "registration_id": new_id(),
        "person_id": new_id(),
        "course_offering_id": new_id(),  # not the offering section A belongs to
        "section_id": w["a"]["id"],
        "withdrawn_at": "2026-10-22T09:30:00+00:00",
    }
    envelope = {
        "id": new_id(),
        "name": roster.WITHDRAWN,
        "version": 1,
        "organisation_id": w["org"].id,
        "occurred_at": "2026-10-22T09:00:00+00:00",
        "payload": stray,
    }
    with SessionLocal() as db:
        db.execute(text("PRAGMA foreign_keys=ON"))
        assert roster.handle_event(db, envelope) == roster.REJECTED_UNKNOWN_SECTION
    with SessionLocal() as db:
        db.execute(text("PRAGMA foreign_keys=ON"))
        good = {**stray, "course_offering_id": w["o"]["id"]}
        assert roster.handle_event(db, {**envelope, "id": new_id(), "payload": good}) == roster.APPLIED
    assert roster_of(client, w)["total"] == 0  # kept as withdrawn, never enrolled
    late = confirmed(w["o"], w["a"], registration_id=stray["registration_id"])
    assert deliver("course-registration.confirmed", w["org"].id, late) == roster.STALE


@pytest.mark.parametrize("name", ["course-registration.confirmed", "course-registration.withdrawn"])
def test_a_payload_missing_an_agreed_field_is_rejected_once_and_not_redelivered_forever(client, world, name):
    w = world
    event_id = new_id()
    payload = {"registration_id": new_id(), "section_id": w["a"]["id"]}  # no person_id, no course_offering_id
    assert deliver(name, w["org"].id, payload, event_id=event_id) == roster.REJECTED_MALFORMED_PAYLOAD
    assert deliver(name, w["org"].id, payload, event_id=event_id) == roster.DUPLICATE
    assert roster_of(client, w)["total"] == 0
