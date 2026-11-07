"""The academic-management consumers: every handler, duplicate and out-of-order delivery, organisation isolation,
and rollback. Events are delivered through the handlers (conftest.deliver), with payloads shaped as academic-management
publishes them; no read-model row is inserted by hand."""

import tomllib
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
import yaml

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    ADMIN,
    BASE,
    NOW,
    FakeEvent,
    deliver,
    make_timetable,
    offering_created,
    offering_status_changed,
    section_created,
    section_updated,
    slot,
    term_created,
)
from eos_core.db import SessionLocal, init_db, new_id  # noqa: E402
from eos_core.tenant import organisation_scope  # noqa: E402
from eos_timetable_attendance.application import consumers  # noqa: E402
from eos_timetable_attendance.application.consumers import (  # noqa: E402
    CONSUMERS,
    OFFERING_CREATED,
    OFFERING_STATUS_CHANGED,
    SECTION_CREATED,
    SECTION_UPDATED,
    TERM_CREATED,
)
from eos_timetable_attendance.infrastructure import repository as repo  # noqa: E402
from eos_timetable_attendance.infrastructure.models import (  # noqa: E402
    OfferingRef,
    ProcessedEvent,
    SectionRef,
    TermRef,
    as_utc,
)
from sqlalchemy import select  # noqa: E402

MODULE = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module", autouse=True)
def _tables():
    init_db()


def rows(org_id: str, model, **where) -> list:
    """The organisation's rows of a read model, read the way the module reads them (scoped)."""
    with organisation_scope(org_id), SessionLocal() as db:
        query = repo.q(db, model)
        for column, value in where.items():
            query = query.where(getattr(model, column) == value)
        return list(db.scalars(query))


def one(org_id: str, model, **where):
    [row] = rows(org_id, model, **where)
    return row


def later(minutes: int) -> datetime:
    return NOW + timedelta(minutes=minutes)


# ---------------------------------------------------------------- registration


def test_the_consumers_are_exactly_the_events_of_the_manifest_and_the_entry_point():
    manifest = yaml.safe_load((MODULE / "module.yaml").read_text(encoding="utf-8"))
    assert set(CONSUMERS) == set(manifest["consumes_events"])
    assert set(CONSUMERS) == {
        "academic-management.term.created",
        "academic-management.offering.created",
        "academic-management.offering.status-changed",
        "academic-management.section.created",
        "academic-management.section.updated",
        "enrolment-registration.course-registration.confirmed",
        "enrolment-registration.course-registration.withdrawn",
        "enrolment-registration.section-allocation.changed",
        "scheduler.job.due",  # FR-11: its own timetable-attendance.close-expired-sessions job (tests/test_auto_close.py)
    }
    project = tomllib.loads((MODULE / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    entry = project["project"]["entry-points"]["eos.event_consumers"]
    assert entry == {"timetable-attendance": "eos_timetable_attendance.application.consumers:CONSUMERS"}
    assert all(callable(handler) for handler in CONSUMERS.values())


def test_nothing_is_consumed_whose_mapping_is_unconfirmed():
    """faculty-assignment.* needs Faizan's identity mapping, and offering.updated / course.* carry no new values; none
    has a handler."""
    for name in CONSUMERS:
        assert ".faculty-assignment." not in name
        assert not name.endswith((".offering.updated", ".course.created", ".course.updated", ".course.archived"))


def test_the_published_payloads_carry_the_fields_the_handlers_read():
    contract = MODULE.parents[2] / "modules" / "academics" / "academic-management" / "contracts" / "events.yaml"
    if not contract.exists():
        pytest.skip("the academic-management contract is not in this checkout")
    events = {e["name"]: e for e in yaml.safe_load(contract.read_text(encoding="utf-8"))["events"]}
    read = {
        consumers.TERM_CREATED: {"academic_period_id", "code", "name", "starts_on", "ends_on"},
        consumers.OFFERING_CREATED: {
            "course_offering_id",
            "academic_period_id",
            "course_code",
            "course_title",
            "department_id",
        },
        consumers.OFFERING_STATUS_CHANGED: {"course_offering_id", "to_status"},
        consumers.SECTION_CREATED: {"section_id", "course_offering_id", "code"},
        consumers.SECTION_UPDATED: {"section_id", "course_offering_id", "status"},
    }
    for name, fields in read.items():
        assert "timetable-attendance" in events[name]["consumers"], name
        assert fields <= set(events[name]["payload"]), (name, fields - set(events[name]["payload"]))


# ---------------------------------------------------------------- each handler


def test_term_created_fills_term_ref_with_the_dates(org):
    period = new_id()
    assert deliver(org.id, TERM_CREATED, term_created(period)) == "applied"
    term = one(org.id, TermRef, academic_period_id=period)
    assert (term.code, term.name, term.starts_on, term.ends_on) == (
        "2026-ODD",
        "Odd semester 2026",
        date(2026, 7, 1),
        date(2026, 11, 30),
    )
    assert term.organisation_id == org.id


def test_a_single_day_term_is_valid_and_a_term_ending_before_it_starts_is_refused(org):
    day = new_id()
    deliver(org.id, TERM_CREATED, term_created(day, starts_on="2026-08-01", ends_on="2026-08-01"))
    assert one(org.id, TermRef, academic_period_id=day).starts_on == date(2026, 8, 1)
    with pytest.raises(ValueError, match="ends_on"):
        deliver(org.id, TERM_CREATED, term_created(new_id(), starts_on="2026-09-01", ends_on="2026-08-01"))


def test_offering_created_fills_the_course_facts_and_leaves_the_status_unknown(org):
    offering, period, department = new_id(), new_id(), new_id()
    deliver(org.id, OFFERING_CREATED, offering_created(offering, period, department_id=department))
    row = one(org.id, OfferingRef, course_offering_id=offering)
    assert (row.academic_period_id, row.course_code, row.course_title, row.department_id) == (
        period,
        "CS101",
        "Programming",
        department,
    )
    assert (row.status, row.status_as_of) == (None, None)  # offering.created carries no status


def test_offering_status_changed_sets_the_status(org):
    offering = new_id()
    deliver(org.id, OFFERING_CREATED, offering_created(offering, new_id()))
    deliver(org.id, OFFERING_STATUS_CHANGED, offering_status_changed(offering, "open"))
    row = one(org.id, OfferingRef, course_offering_id=offering)
    assert (row.status, as_utc(row.status_as_of)) == ("open", NOW)
    deliver(
        org.id, OFFERING_STATUS_CHANGED, offering_status_changed(offering, "in_progress", "open"), occurred_at=later(5)
    )
    assert one(org.id, OfferingRef, course_offering_id=offering).status == "in_progress"


def test_section_created_and_updated_fill_section_ref(org):
    section, offering = new_id(), new_id()
    deliver(org.id, SECTION_CREATED, section_created(section, offering, code="B"))
    row = one(org.id, SectionRef, section_id=section)
    assert (row.course_offering_id, row.code, row.status) == (offering, "B", None)
    deliver(org.id, SECTION_UPDATED, section_updated(section, offering, "closed"), occurred_at=later(1))
    assert one(org.id, SectionRef, section_id=section).status == "closed"


@pytest.mark.parametrize(
    ("name", "payload", "message"),
    [
        (
            TERM_CREATED,
            {
                "academic_period_id": "not-a-uuid",
                "code": "c",
                "name": "n",
                "starts_on": "2026-01-01",
                "ends_on": "2026-02-01",
            },
            "academic_period_id",
        ),
        (TERM_CREATED, term_created() | {"code": "  "}, "code"),
        (TERM_CREATED, term_created() | {"starts_on": "soon"}, "starts_on"),
        (TERM_CREATED, {k: v for k, v in term_created().items() if k != "ends_on"}, "ends_on is missing"),
        (OFFERING_CREATED, offering_created(new_id(), new_id()) | {"course_code": None}, "course_code"),
        (OFFERING_CREATED, offering_created(new_id(), new_id()) | {"course_title": "x" * 201}, "course_title"),
        (OFFERING_STATUS_CHANGED, {"course_offering_id": new_id()}, "to_status"),
        (OFFERING_STATUS_CHANGED, offering_status_changed(new_id(), "a-status-that-is-far-too-long"), "to_status"),
        (SECTION_CREATED, section_created(new_id(), new_id()) | {"code": ""}, "code"),
        (SECTION_UPDATED, section_updated(new_id(), "x", "open"), "course_offering_id"),
    ],
)
def test_a_malformed_event_is_refused_and_writes_nothing(org, name, payload, message):
    before = (
        len(rows(org.id, TermRef)),
        len(rows(org.id, OfferingRef)),
        len(rows(org.id, SectionRef)),
        len(rows(org.id, ProcessedEvent)),
    )
    with pytest.raises(ValueError, match=message):
        deliver(org.id, name, payload)
    after = (
        len(rows(org.id, TermRef)),
        len(rows(org.id, OfferingRef)),
        len(rows(org.id, SectionRef)),
        len(rows(org.id, ProcessedEvent)),
    )
    assert after == before


def test_an_unsupported_envelope_version_is_refused(org):
    with pytest.raises(consumers.UnsupportedEventVersionError):
        deliver(org.id, TERM_CREATED, term_created(), version=2)
    assert rows(org.id, ProcessedEvent) == []


def test_unknown_payload_fields_are_tolerated(org):
    period = new_id()
    deliver(org.id, TERM_CREATED, term_created(period) | {"a_field_added_later": 1})
    assert one(org.id, TermRef, academic_period_id=period)


# ---------------------------------------------------------------- duplicate delivery


def test_the_same_event_twice_has_the_effect_of_once_and_is_recorded_once(org):
    period, event_id = new_id(), new_id()
    assert deliver(org.id, TERM_CREATED, term_created(period), event_id=event_id) == "applied"
    assert deliver(org.id, TERM_CREATED, term_created(period), event_id=event_id) == "duplicate"
    assert len(rows(org.id, TermRef, academic_period_id=period)) == 1
    [marker] = rows(org.id, ProcessedEvent, event_id=event_id)
    assert marker.name == TERM_CREATED


def test_a_redelivered_status_change_does_not_undo_a_later_one(org):
    offering = new_id()
    deliver(org.id, OFFERING_CREATED, offering_created(offering, new_id()))
    first = new_id()
    deliver(
        org.id, OFFERING_STATUS_CHANGED, offering_status_changed(offering, "open"), event_id=first, occurred_at=later(1)
    )
    deliver(
        org.id, OFFERING_STATUS_CHANGED, offering_status_changed(offering, "completed", "open"), occurred_at=later(9)
    )
    assert (
        deliver(
            org.id,
            OFFERING_STATUS_CHANGED,
            offering_status_changed(offering, "open"),
            event_id=first,
            occurred_at=later(1),
        )
        == "duplicate"
    )
    assert one(org.id, OfferingRef, course_offering_id=offering).status == "completed"


def test_a_second_creation_with_a_new_id_changes_nothing(org):
    period = new_id()
    deliver(org.id, TERM_CREATED, term_created(period))
    assert deliver(org.id, TERM_CREATED, term_created(period, name="Renamed", ends_on="2027-01-31")) == "ignored"
    term = one(org.id, TermRef, academic_period_id=period)
    assert (term.name, term.ends_on) == ("Odd semester 2026", date(2026, 11, 30))
    offering = new_id()
    deliver(org.id, OFFERING_CREATED, offering_created(offering, new_id(), code="CS101"))
    assert deliver(org.id, OFFERING_CREATED, offering_created(offering, new_id(), code="OTHER")) == "ignored"
    assert one(org.id, OfferingRef, course_offering_id=offering).course_code == "CS101"


def test_two_deliveries_racing_for_one_id_lose_on_the_constraint_and_the_redelivery_is_a_duplicate(org, monkeypatch):
    """Both deliveries read "not seen"; the unique constraint refuses the second marker, so it fails (nothing applied,
    nothing recorded) and its redelivery finds the first one's marker."""
    from sqlalchemy.exc import IntegrityError

    period, event_id = new_id(), new_id()
    event = FakeEvent(TERM_CREATED, org.id, term_created(period), event_id=event_id)
    real = repo.ref_row
    with organisation_scope(org.id), SessionLocal() as first, SessionLocal() as second:
        monkeypatch.setattr(
            repo,
            "ref_row",
            lambda db, model, column, value, org_id: (
                None if model is ProcessedEvent else real(db, model, column, value, org_id)
            ),
        )
        assert CONSUMERS[TERM_CREATED](first, event) == "applied"
        first.commit()
        with pytest.raises(IntegrityError):
            CONSUMERS[TERM_CREATED](second, event)
        second.rollback()
        monkeypatch.setattr(repo, "ref_row", real)
    assert len(rows(org.id, TermRef, academic_period_id=period)) == 1
    assert deliver(org.id, TERM_CREATED, term_created(period), event_id=event_id) == "duplicate"


# ---------------------------------------------------------------- out-of-order delivery


def test_a_status_change_before_the_creation_leaves_a_partial_row_the_creation_completes(org):
    offering, period = new_id(), new_id()
    deliver(org.id, OFFERING_STATUS_CHANGED, offering_status_changed(offering, "open"), occurred_at=later(5))
    partial = one(org.id, OfferingRef, course_offering_id=offering)
    assert (partial.status, partial.academic_period_id, partial.course_code) == ("open", None, None)
    with organisation_scope(org.id), SessionLocal() as db:
        assert repo.offering_refs(db, {offering}) == {}  # not known until it is created
    deliver(org.id, OFFERING_CREATED, offering_created(offering, period), occurred_at=later(1))
    row = one(org.id, OfferingRef, course_offering_id=offering)
    assert (row.status, row.academic_period_id, row.course_code) == ("open", period, "CS101")  # the status is kept
    with organisation_scope(org.id), SessionLocal() as db:
        assert set(repo.offering_refs(db, {offering})) == {offering}


def test_an_older_status_change_arriving_late_is_ignored_and_a_newer_one_applies(org):
    offering = new_id()
    deliver(org.id, OFFERING_CREATED, offering_created(offering, new_id()))
    deliver(
        org.id,
        OFFERING_STATUS_CHANGED,
        offering_status_changed(offering, "completed", "in_progress"),
        occurred_at=later(30),
    )
    stale = deliver(
        org.id, OFFERING_STATUS_CHANGED, offering_status_changed(offering, "in_progress", "open"), occurred_at=later(10)
    )
    assert stale == "stale"
    row = one(org.id, OfferingRef, course_offering_id=offering)
    assert (row.status, as_utc(row.status_as_of)) == ("completed", later(30))
    assert (
        deliver(
            org.id,
            OFFERING_STATUS_CHANGED,
            offering_status_changed(offering, "cancelled", "completed"),
            occurred_at=later(40),
        )
        == "applied"
    )
    assert one(org.id, OfferingRef, course_offering_id=offering).status == "cancelled"


def test_events_at_the_same_time_apply_in_arrival_order(org):
    offering = new_id()
    deliver(org.id, OFFERING_STATUS_CHANGED, offering_status_changed(offering, "open"), occurred_at=later(3))
    assert (
        deliver(org.id, OFFERING_STATUS_CHANGED, offering_status_changed(offering, "in_progress"), occurred_at=later(3))
        == "applied"
    )
    assert one(org.id, OfferingRef, course_offering_id=offering).status == "in_progress"


def test_section_updated_before_created_and_stale_updates(org):
    section, offering = new_id(), new_id()
    deliver(org.id, SECTION_UPDATED, section_updated(section, offering, "closed"), occurred_at=later(20))
    partial = one(org.id, SectionRef, section_id=section)
    assert (partial.code, partial.status, partial.course_offering_id) == (None, "closed", offering)
    with organisation_scope(org.id), SessionLocal() as db:
        assert repo.section_refs(db, {section}) == {}
    deliver(org.id, SECTION_CREATED, section_created(section, offering, code="C"), occurred_at=later(1))
    row = one(org.id, SectionRef, section_id=section)
    assert (row.code, row.status) == ("C", "closed")
    assert (
        deliver(org.id, SECTION_UPDATED, section_updated(section, offering, "open"), occurred_at=later(10)) == "stale"
    )
    assert one(org.id, SectionRef, section_id=section).status == "closed"


def test_a_section_cannot_move_to_another_offering(org):
    section = new_id()
    deliver(org.id, SECTION_CREATED, section_created(section, new_id()))
    with pytest.raises(ValueError, match="one course offering"):
        deliver(org.id, SECTION_UPDATED, section_updated(section, new_id(), "open"))


def test_arrival_order_never_changes_the_result(org):
    """The same four events in every arrival order end in the same row."""
    import itertools

    for order in itertools.permutations(range(4)):
        offering, period = new_id(), new_id()
        events = [
            (OFFERING_CREATED, offering_created(offering, period), later(0)),
            (OFFERING_STATUS_CHANGED, offering_status_changed(offering, "open"), later(1)),
            (OFFERING_STATUS_CHANGED, offering_status_changed(offering, "in_progress", "open"), later(2)),
            (OFFERING_STATUS_CHANGED, offering_status_changed(offering, "completed", "in_progress"), later(3)),
        ]
        for i in order:
            name, payload, at = events[i]
            deliver(org.id, name, payload, occurred_at=at)
        row = one(org.id, OfferingRef, course_offering_id=offering)
        assert (row.status, row.academic_period_id) == ("completed", period), order


# ---------------------------------------------------------------- organisation isolation


def test_the_same_ids_in_two_organisations_are_separate_rows(org, other_org):
    offering, period = new_id(), new_id()
    deliver(org.id, OFFERING_CREATED, offering_created(offering, period, code="A-101"))
    deliver(other_org.id, OFFERING_CREATED, offering_created(offering, period, code="B-101"))
    deliver(org.id, OFFERING_STATUS_CHANGED, offering_status_changed(offering, "completed"), occurred_at=later(9))
    mine, theirs = (
        one(org.id, OfferingRef, course_offering_id=offering),
        one(other_org.id, OfferingRef, course_offering_id=offering),
    )
    assert (mine.course_code, mine.status) == ("A-101", "completed")
    assert (theirs.course_code, theirs.status) == ("B-101", None)  # the other organisation's row is untouched
    assert (mine.organisation_id, theirs.organisation_id) == (org.id, other_org.id)


def test_a_session_scoped_to_another_organisation_sees_none_of_the_rows(org, other_org):
    period = new_id()
    deliver(org.id, TERM_CREATED, term_created(period))
    event_id = new_id()
    deliver(org.id, SECTION_CREATED, section_created(new_id(), new_id()), event_id=event_id)
    assert rows(other_org.id, TermRef, academic_period_id=period) == []
    assert rows(other_org.id, ProcessedEvent, event_id=event_id) == []
    # the same envelope id in another organisation is a separate delivery: marker ids are per organisation
    assert deliver(other_org.id, TERM_CREATED, term_created(period), event_id=event_id) == "applied"


def test_an_event_is_never_applied_under_another_organisations_scope(org, other_org):
    event = FakeEvent(TERM_CREATED, org.id, term_created(), occurred_at=NOW)
    with organisation_scope(other_org.id), SessionLocal() as db:
        with pytest.raises(RuntimeError, match="not scoped"):
            CONSUMERS[TERM_CREATED](db, event)
        db.rollback()
    with SessionLocal() as db:  # no scope at all
        with pytest.raises(RuntimeError, match="not scoped"):
            CONSUMERS[TERM_CREATED](db, event)
        db.rollback()
    assert rows(org.id, TermRef) == [] and rows(other_org.id, TermRef) == []


def test_an_event_without_an_organisation_is_not_applied(org):
    event = FakeEvent(TERM_CREATED, None, term_created())
    with SessionLocal() as db:
        assert CONSUMERS[TERM_CREATED](db, event) == "ignored"
        db.commit()
    with SessionLocal() as db:
        assert db.scalars(select(ProcessedEvent).where(ProcessedEvent.event_id == event.id)).first() is None


def test_rows_written_by_a_consumer_carry_the_events_organisation_only(org, other_org):
    deliver(org.id, SECTION_CREATED, section_created(new_id(), new_id()))
    deliver(other_org.id, SECTION_CREATED, section_created(new_id(), new_id()))
    for model in (SectionRef, ProcessedEvent):
        assert {r.organisation_id for r in rows(org.id, model)} == {org.id}


# ---------------------------------------------------------------- rollback


def test_a_failure_after_the_marker_rolls_back_the_marker_and_the_row(org):
    period, event_id = new_id(), new_id()

    def fail(*args, **kwargs):
        raise OSError("the database went away")

    event = FakeEvent(TERM_CREATED, org.id, term_created(period), event_id=event_id)
    with organisation_scope(org.id), SessionLocal() as db:
        with pytest.raises(OSError):
            consumers._receive(db, event, fail)
        db.rollback()
    assert rows(org.id, ProcessedEvent, event_id=event_id) == []
    assert rows(org.id, TermRef, academic_period_id=period) == []
    # the redelivery is applied, because nothing was recorded
    assert deliver(org.id, TERM_CREATED, term_created(period), event_id=event_id) == "applied"


def test_a_malformed_event_after_a_good_write_in_the_same_transaction_leaves_nothing(org):
    """Two handlers in one transaction: the second refuses its event, the relay rolls the transaction back, and the
    first handler's row and marker go with it."""
    good_period = new_id()
    with organisation_scope(org.id), SessionLocal() as db:
        CONSUMERS[TERM_CREATED](db, FakeEvent(TERM_CREATED, org.id, term_created(good_period)))
        with pytest.raises(ValueError):
            CONSUMERS[TERM_CREATED](db, FakeEvent(TERM_CREATED, org.id, term_created(new_id(), code="")))
        db.rollback()
    assert rows(org.id, TermRef, academic_period_id=good_period) == []


# ---------------------------------------------------------------- what the read models make possible


def test_slots_need_an_offering_and_a_section_that_were_created_not_merely_mentioned(client, org):
    _, h = org.user(ADMIN)
    period, offering, section = new_id(), new_id(), new_id()
    t = make_timetable(client, h, period)
    ids = {"offering": offering, "section": section, "assignment": new_id()}
    deliver(org.id, OFFERING_STATUS_CHANGED, offering_status_changed(offering, "open"))  # no creation yet
    deliver(org.id, SECTION_UPDATED, section_updated(section, offering, "open"))
    r = client.put(f"{BASE}/timetables/{t['id']}/slots", json={"slots": [slot(ids)]}, headers=h)
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "unknown_course_offering")
    deliver(org.id, OFFERING_CREATED, offering_created(offering, period))
    r = client.put(f"{BASE}/timetables/{t['id']}/slots", json={"slots": [slot(ids)]}, headers=h)
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "unknown_section")
    deliver(org.id, SECTION_CREATED, section_created(section, offering))
    r = client.put(f"{BASE}/timetables/{t['id']}/slots", json={"slots": [slot(ids)]}, headers=h)
    assert (r.status_code, r.json()["detail"]["code"]) == (
        422,
        "unknown_instructor_assignment",
    )  # its consumer is not built


def test_the_organisation_clock_helper_is_utc():
    assert NOW.tzinfo == UTC and uuid.UUID(new_id())
