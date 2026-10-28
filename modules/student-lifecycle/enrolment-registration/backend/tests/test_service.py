from __future__ import annotations

from datetime import date, timedelta

import pytest
from conftest import add_enrolment, add_offering, add_section, add_term, add_window, make_actor
from eos_core.db import new_id, utcnow
from eos_enrolment_registration.application import service as svc
from eos_enrolment_registration.application.service import EnrolmentError
from eos_enrolment_registration.domain import enums as e


def refused(fn, *args, **kwargs) -> tuple[int, str]:
    with pytest.raises(EnrolmentError) as exc:
        fn(*args, **kwargs)
    return exc.value.status, exc.value.code


def enrol(db, staff, person=None, programme=None):
    return svc.enrol(
        db,
        staff,
        person_id=person or new_id(),
        student_name="  Ana Silva ",
        programme_id=programme or new_id(),
        start_academic_period_id=new_id(),
    )


def register(db, staff, enrolment_id, offering, section, term, registration_type=e.REGULAR):
    return svc.register(
        db,
        staff,
        programme_enrolment_id=enrolment_id,
        course_offering_id=offering,
        section_id=section,
        academic_period_id=term,
        registration_type=registration_type,
    )


# ---------------------------------------------------------------- enrolment


def test_roll_numbers_count_per_organisation_and_are_never_reused(db, staff, org, other_org):
    year = utcnow().year
    first, second = enrol(db, staff), enrol(db, staff)
    assert (first["roll_number"], second["roll_number"]) == (f"RN{year}-00001", f"RN{year}-00002")
    assert first["student_name"] == "Ana Silva" and first["status"] == e.ACTIVE
    svc.withdraw_enrolment(db, staff, second["id"], "left")
    assert enrol(db, staff)["roll_number"] == f"RN{year}-00003"
    assert enrol(db, make_actor(other_org))["roll_number"] == f"RN{year}-00001"


def test_roll_number_prefix_from_config(db, staff, monkeypatch):
    monkeypatch.setenv("ENROLMENT_REGISTRATION_ROLL_NUMBER_PREFIX", "STU")
    assert enrol(db, staff)["roll_number"].startswith("STU")


def test_one_active_enrolment_per_programme(db, staff):
    person, programme = new_id(), new_id()
    enrolment = enrol(db, staff, person, programme)
    assert refused(enrol, db, staff, person, programme) == (409, "duplicate_enrolment")
    enrol(db, staff, person, new_id())
    svc.withdraw_enrolment(db, staff, enrolment["id"], "transfer")
    enrol(db, staff, person, programme)


def test_withdraw_and_complete_end_an_enrolment_once(db, staff):
    withdrawn = svc.withdraw_enrolment(db, staff, enrol(db, staff)["id"], "  moved away ")
    assert (withdrawn["status"], withdrawn["end_reason"]) == (e.WITHDRAWN, "moved away")
    assert withdrawn["ended_at"] is not None
    assert refused(svc.complete_enrolment, db, staff, withdrawn["id"]) == (409, "enrolment_ended")
    completed = svc.complete_enrolment(db, staff, enrol(db, staff)["id"])
    assert completed["status"] == e.COMPLETED
    assert refused(svc.withdraw_enrolment, db, staff, completed["id"], "x") == (409, "enrolment_ended")


def test_list_search_and_page_enrolments(db, staff, other_org):
    programme = new_id()
    add_enrolment(
        db, staff.organisation_id, student_name="Zara Khan", roll_number="RN2026-77777", programme_id=programme
    )
    add_enrolment(db, staff.organisation_id, programme_id=programme, status=e.WITHDRAWN)
    add_enrolment(db, staff.organisation_id)
    add_enrolment(db, other_org)
    assert svc.list_enrolments(db, staff)["total"] == 3
    assert svc.list_enrolments(db, staff, programme_id=programme)["total"] == 2
    assert svc.list_enrolments(db, staff, status=e.WITHDRAWN)["total"] == 1
    assert svc.list_enrolments(db, staff, q="zar")["items"][0]["student_name"] == "Zara Khan"
    assert svc.list_enrolments(db, staff, q="77777")["total"] == 1
    assert svc.list_enrolments(db, staff, q="100%")["total"] == 0
    page = svc.list_enrolments(db, staff, page=2, page_size=2)
    assert (page["total"], len(page["items"])) == (3, 1)
    assert refused(svc.get_enrolment, db, make_actor(other_org), page["items"][0]["id"]) == (404, "not_found")


# ---------------------------------------------------------------- windows


def test_windows(db, staff):
    term, now = new_id(), utcnow()
    assert refused(svc.get_window, db, staff, term) == (404, "not_found")
    assert refused(svc.set_window, db, staff, term, now, now) == (422, "invalid_window")
    window = svc.set_window(db, staff, term, now - timedelta(hours=1), now + timedelta(days=1))
    assert window["is_open"] is True and window["academic_period_id"] == term
    later = svc.set_window(db, staff, term, now + timedelta(days=1), now + timedelta(days=2))
    assert later["is_open"] is False
    assert svc.get_window(db, staff, term)["opens_at"] == later["opens_at"]


# ---------------------------------------------------------------- registration


def test_register_without_local_copies_is_accepted_but_unverified(db, staff):
    term = new_id()
    add_window(db, staff.organisation_id, term)
    enrolment = add_enrolment(db, staff.organisation_id)
    reg = register(db, staff, enrolment.id, new_id(), new_id(), term)
    assert reg["status"] == e.CONFIRMED and reg["references_verified"] is False
    assert (reg["student_name"], reg["roll_number"]) == (enrolment.student_name, enrolment.roll_number)
    assert reg["section_since"] == utcnow().date().isoformat()


def test_register_with_known_offering_and_section_is_verified(db, staff):
    term = new_id()
    add_window(db, staff.organisation_id, term)
    offering = add_offering(db, staff.organisation_id, term)
    section = add_section(db, offering)
    reg = register(
        db, staff, add_enrolment(db, staff.organisation_id).id, offering.course_offering_id, section.section_id, term
    )
    assert reg["references_verified"] is True


def test_refusals_follow_the_contract_order(db, staff):
    org, term = staff.organisation_id, new_id()
    offering = add_offering(db, org, term)
    section = add_section(db, offering, capacity=1)
    args = (offering.course_offering_id, section.section_id, term)

    ended = add_enrolment(db, org, status=e.WITHDRAWN)
    assert refused(register, db, staff, ended.id, *args) == (409, "enrolment_not_active")
    assert refused(register, db, staff, new_id(), *args) == (404, "not_found")

    student = add_enrolment(db, org)
    assert refused(register, db, staff, student.id, *args) == (409, "window_closed")
    register(db, staff, student.id, *args, registration_type=e.SUPPLEMENTARY)
    assert refused(register, db, staff, student.id, *args, registration_type=e.BACKLOG) == (409, "already_registered")

    add_window(db, org, term)
    assert refused(register, db, staff, add_enrolment(db, org).id, *args) == (409, "section_full")
    other_term = add_offering(db, org, new_id())
    assert refused(register, db, staff, add_enrolment(db, org).id, other_term.course_offering_id, new_id(), term) == (
        422,
        "term_mismatch",
    )
    planned = add_offering(db, org, term, status="planned")
    assert refused(register, db, staff, add_enrolment(db, org).id, planned.course_offering_id, new_id(), term) == (
        409,
        "offering_not_open",
    )
    elsewhere = add_section(db, add_offering(db, org, term))
    assert refused(
        register, db, staff, add_enrolment(db, org).id, offering.course_offering_id, elsewhere.section_id, term
    ) == (
        422,
        "section_not_in_offering",
    )
    closed = add_section(db, offering, status="closed")
    assert refused(
        register, db, staff, add_enrolment(db, org).id, offering.course_offering_id, closed.section_id, term
    ) == (
        409,
        "section_not_open",
    )


def test_closed_window_does_not_stop_supplementary_or_backlog(db, staff):
    term = new_id()
    add_window(db, staff.organisation_id, term, open_now=False)
    for registration_type in (e.SUPPLEMENTARY, e.BACKLOG):
        reg = register(
            db, staff, add_enrolment(db, staff.organisation_id).id, new_id(), new_id(), term, registration_type
        )
        assert reg["registration_type"] == registration_type


def test_bulk_reports_each_student_and_counts_seats_within_the_batch(db, staff):
    org, term = staff.organisation_id, new_id()
    add_window(db, org, term)
    offering = add_offering(db, org, term)
    section = add_section(db, offering, capacity=2)
    first, second, third = (add_enrolment(db, org) for _ in range(3))
    inactive = add_enrolment(db, org, status=e.COMPLETED)
    result = svc.register_bulk(
        db,
        staff,
        programme_enrolment_ids=[first.id, inactive.id, new_id(), second.id, third.id],
        course_offering_id=offering.course_offering_id,
        section_id=section.section_id,
        academic_period_id=term,
    )
    assert (result["confirmed"], result["refused"]) == (2, 3)
    assert [(r["outcome"], r["code"]) for r in result["results"]] == [
        ("confirmed", None),
        ("refused", "enrolment_not_active"),
        ("refused", "not_found"),
        ("confirmed", None),
        ("refused", "section_full"),
    ]
    assert result["results"][0]["registration"]["roll_number"] == first.roll_number


def test_withdraw_registration_frees_the_seat_and_allows_registering_again(db, staff):
    org, term = staff.organisation_id, new_id()
    add_window(db, org, term)
    offering = add_offering(db, org, term)
    section = add_section(db, offering, capacity=1)
    student = add_enrolment(db, org)
    args = (offering.course_offering_id, section.section_id, term)
    reg = register(db, staff, student.id, *args)
    withdrawn = svc.withdraw_registration(db, staff, reg["id"], "dropped")
    assert (withdrawn["status"], withdrawn["withdrawal_reason"]) == (e.WITHDRAWN, "dropped")
    assert refused(svc.withdraw_registration, db, staff, reg["id"], "again") == (409, "registration_not_confirmed")
    again = register(db, staff, add_enrolment(db, org).id, *args)
    assert again["id"] != reg["id"]


def test_withdrawing_an_enrolment_withdraws_its_registrations(db, staff):
    term = new_id()
    add_window(db, staff.organisation_id, term)
    student = add_enrolment(db, staff.organisation_id)
    regs = [register(db, staff, student.id, new_id(), new_id(), term) for _ in range(2)]
    svc.withdraw_enrolment(db, staff, student.id, "left")
    assert {svc.get_registration(db, staff, r["id"])["status"] for r in regs} == {e.WITHDRAWN}


def test_change_section(db, staff):
    org, term = staff.organisation_id, new_id()
    add_window(db, org, term)
    offering = add_offering(db, org, term)
    a, b, full = add_section(db, offering), add_section(db, offering), add_section(db, offering, capacity=0)
    reg = register(db, staff, add_enrolment(db, org).id, offering.course_offering_id, a.section_id, term)
    effective = date(2026, 11, 2)
    moved = svc.change_section(db, staff, reg["id"], b.section_id, effective)
    assert (moved["id"], moved["section_id"], moved["section_since"]) == (reg["id"], b.section_id, "2026-11-02")
    assert refused(svc.change_section, db, staff, reg["id"], b.section_id, effective) == (409, "same_section")
    assert refused(svc.change_section, db, staff, reg["id"], full.section_id, effective) == (409, "section_full")
    other = add_section(db, add_offering(db, org, term))
    assert refused(svc.change_section, db, staff, reg["id"], other.section_id, effective) == (
        422,
        "section_not_in_offering",
    )
    svc.withdraw_registration(db, staff, reg["id"], "x")
    assert refused(svc.change_section, db, staff, reg["id"], a.section_id, effective) == (
        409,
        "registration_not_confirmed",
    )


def test_list_registrations_filters(db, staff, other_org):
    org, term = staff.organisation_id, new_id()
    add_window(db, org, term)
    offering = new_id()
    s1 = register(db, staff, add_enrolment(db, org).id, offering, new_id(), term)
    register(db, staff, add_enrolment(db, org).id, offering, new_id(), term, e.BACKLOG)
    register(db, staff, add_enrolment(db, org).id, new_id(), new_id(), term)
    svc.withdraw_registration(db, staff, s1["id"], "x")
    assert svc.list_registrations(db, staff)["total"] == 3
    assert svc.list_registrations(db, staff, course_offering_id=offering)["total"] == 2
    assert svc.list_registrations(db, staff, registration_type=e.BACKLOG)["total"] == 1
    assert svc.list_registrations(db, staff, status=e.WITHDRAWN)["items"][0]["id"] == s1["id"]
    assert svc.list_registrations(db, staff, academic_period_id=new_id())["total"] == 0
    assert svc.list_registrations(db, make_actor(other_org))["total"] == 0


# ---------------------------------------------------------------- report


def test_registered_candidates_report(db, staff):
    org = staff.organisation_id
    active = add_term(db, org, active=True, name="Term 1 2026")
    old_term = new_id()
    add_window(db, org, active.academic_period_id)
    busy = add_offering(db, org, active.academic_period_id, course_code="CS101", course_title="Programming I")
    quiet = new_id()
    t = active.academic_period_id
    for _ in range(3):
        register(db, staff, add_enrolment(db, org).id, busy.course_offering_id, new_id(), t)
    register(db, staff, add_enrolment(db, org).id, quiet, new_id(), t, e.SUPPLEMENTARY)
    withdrawn = register(db, staff, add_enrolment(db, org).id, quiet, new_id(), t, e.BACKLOG)
    svc.withdraw_registration(db, staff, withdrawn["id"], "x")
    register(db, staff, add_enrolment(db, org).id, new_id(), new_id(), old_term, e.BACKLOG)

    report = svc.registered_candidates(db, staff)
    assert (report["academic_period_id"], report["term_name"], report["total"]) == (t, "Term 1 2026", 4)
    assert report["by_type"] == {"regular": 3, "supplementary": 1, "backlog": 0}
    assert report["offerings"][0] == {
        "course_offering_id": busy.course_offering_id,
        "course_code": "CS101",
        "course_title": "Programming I",
        "registered": 3,
    }
    assert report["offerings"][1]["course_code"] is None
    assert len(svc.registered_candidates(db, staff, limit=1)["offerings"]) == 1
    assert svc.registered_candidates(db, staff, academic_period_id=old_term)["by_type"]["backlog"] == 1


def test_report_without_any_known_term_counts_everything(db, staff):
    term = new_id()
    add_window(db, staff.organisation_id, term)
    register(db, staff, add_enrolment(db, staff.organisation_id).id, new_id(), new_id(), term)
    register(db, staff, add_enrolment(db, staff.organisation_id).id, new_id(), new_id(), new_id(), e.BACKLOG)
    report = svc.registered_candidates(db, staff)
    assert (report["academic_period_id"], report["total"]) == (None, 2)
