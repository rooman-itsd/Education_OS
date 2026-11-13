"""The offering consumers: both handlers, duplicate and out-of-order delivery, organisation isolation, malformed events and
rollback. Events are delivered through the handlers (`deliver`), with payloads shaped as academic-management publishes
them (modules/academics/academic-management/contracts/events.yaml); no read-model row is inserted by hand."""

import tomllib
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import NOW, uid  # noqa: E402
from eos_core.db import SessionLocal, init_db  # noqa: E402
from eos_core.tenant import organisation_scope  # noqa: E402
from eos_examinations.application import consumers  # noqa: E402
from eos_examinations.application.consumers import (  # noqa: E402
    APPLIED,
    CONSUMERS,
    DUPLICATE,
    IGNORED,
    OFFERING_CREATED,
    OFFERING_STATUS_CHANGED,
    STALE,
)
from eos_examinations.infrastructure import repository as repo  # noqa: E402
from eos_examinations.infrastructure.models import OfferingRef, ProcessedEvent  # noqa: E402

MODULE = Path(__file__).resolve().parents[2]


class FakeEvent:
    """The envelope the relay hands a handler (eos_event_bus.domain.models.Event): id, name, version,
    organisation_id, actor, occurred_at and payload."""

    def __init__(self, name, organisation_id, payload, *, event_id=None, occurred_at=None, version=1):
        self.id = event_id or uid()
        self.name = name
        self.version = version
        self.organisation_id = organisation_id
        self.actor = None
        self.occurred_at = occurred_at or NOW
        self.payload = payload


def deliver(organisation_id, name, payload, **envelope) -> str:
    """Run a consumer the way the relay does: in its own session, in the event's organisation, committed after the
    handler returns and rolled back if it raises. Returns the handler's outcome."""
    event = FakeEvent(name, organisation_id, payload, **envelope)
    with organisation_scope(organisation_id), SessionLocal() as db:
        try:
            outcome = CONSUMERS[name](db, event)
            db.commit()
        except BaseException:
            db.rollback()
            raise
    return outcome


def offering_created(
    offering_id=None, *, period_id=None, code="CS101", title="Programming", department_id="", credits=4
):
    """Payload of academic-management.offering.created. `department_id` defaults to a fresh id, None omits it."""
    payload = {
        "course_offering_id": offering_id or uid(),
        "course_id": uid(),
        "academic_period_id": period_id or uid(),
        "programme_ids": [uid()],
        "course_code": code,
        "course_title": title,
        "credits": credits,
        "course_type": "theory",
        "department_id": uid() if department_id == "" else department_id,
    }
    return {k: v for k, v in payload.items() if v is not None}


def status_changed(offering_id, to_status, from_status="planned"):
    return {
        "course_offering_id": offering_id,
        "from_status": from_status,
        "to_status": to_status,
        "changed_at": NOW.isoformat(),
    }


@pytest.fixture(scope="module", autouse=True)
def _tables():
    init_db()


def rows(org_id: str, model, **where) -> list:
    """The organisation's rows of a table, read the way the module reads them (scoped)."""
    with organisation_scope(org_id), SessionLocal() as db:
        query = repo.q(db, model)
        for column, value in where.items():
            query = query.where(getattr(model, column) == value)
        return list(db.scalars(query))


def one(org_id: str, model, **where):
    [row] = rows(org_id, model, **where)
    return row


def markers(org_id: str) -> int:
    return len(rows(org_id, ProcessedEvent))


# ---------------------------------------------------------------- registration


def test_the_consumers_are_exactly_the_events_of_the_manifest_and_the_entry_point():
    manifest = yaml.safe_load((MODULE / "module.yaml").read_text(encoding="utf-8"))
    assert set(CONSUMERS) == set(manifest["consumes_events"])
    assert set(CONSUMERS) == {"academic-management.offering.created", "academic-management.offering.status-changed"}
    project = tomllib.loads((MODULE / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    entry = project["project"]["entry-points"]["eos.event_consumers"]
    assert entry == {"examinations": "eos_examinations.application.consumers:CONSUMERS"}
    assert all(callable(handler) for handler in CONSUMERS.values())


def test_nothing_is_consumed_whose_payload_carries_no_values():
    for name in CONSUMERS:
        assert not name.endswith((".offering.updated", ".course.updated", ".course.created", ".course.archived"))


def test_the_published_payloads_carry_the_fields_the_handlers_read():
    contract = MODULE.parents[2] / "modules" / "academics" / "academic-management" / "contracts" / "events.yaml"
    if not contract.exists():
        pytest.skip("the academic-management contract is not in this checkout")
    events = {e["name"]: e for e in yaml.safe_load(contract.read_text(encoding="utf-8"))["events"]}
    read = {
        OFFERING_CREATED: {
            "course_offering_id",
            "course_id",
            "academic_period_id",
            "course_code",
            "course_title",
            "credits",
            "department_id",
        },
        OFFERING_STATUS_CHANGED: {"course_offering_id", "to_status"},
    }
    for name, fields in read.items():
        assert "examinations" in events[name]["consumers"], name
        assert fields <= set(events[name]["payload"]), (name, fields - set(events[name]["payload"]))


# ---------------------------------------------------------------- offering.created


def test_a_creation_fills_the_read_model_from_the_events_snapshot(org):
    payload = offering_created(code=" CS101 ", title="Programming", credits=3.5)
    assert deliver(org.id, OFFERING_CREATED, payload) == APPLIED
    row = one(org.id, OfferingRef)
    assert (row.organisation_id, row.course_offering_id, row.course_id) == (
        org.id,
        payload["course_offering_id"],
        payload["course_id"],
    )
    assert (row.academic_period_id, row.course_code, row.course_title) == (
        payload["academic_period_id"],
        "CS101",
        "Programming",
    )
    assert (row.credits, row.department_id) == (Decimal("3.50"), payload["department_id"])
    assert (row.status, row.status_as_of) == (None, None)  # offering.created carries no status


def test_a_creation_without_a_department_is_kept_with_none(org):
    deliver(org.id, OFFERING_CREATED, offering_created(department_id=None))
    assert one(org.id, OfferingRef).department_id is None


def test_a_second_creation_changes_nothing_and_keeps_the_status(org):
    offering = uid()
    deliver(org.id, OFFERING_CREATED, offering_created(offering, code="CS101"))
    deliver(org.id, OFFERING_STATUS_CHANGED, status_changed(offering, "open"))
    assert deliver(org.id, OFFERING_CREATED, offering_created(offering, code="CHANGED")) == IGNORED
    row = one(org.id, OfferingRef)
    assert (row.course_code, row.status) == ("CS101", "open")


def test_each_offering_gets_its_own_row(org):
    first, second = uid(), uid()
    deliver(org.id, OFFERING_CREATED, offering_created(first, code="A"))
    deliver(org.id, OFFERING_CREATED, offering_created(second, code="B"))
    assert {r.course_code for r in rows(org.id, OfferingRef)} == {"A", "B"}


# ---------------------------------------------------------------- offering.status-changed


def test_a_status_change_sets_the_status_and_when_it_was_known(org):
    offering = uid()
    deliver(org.id, OFFERING_CREATED, offering_created(offering))
    assert deliver(org.id, OFFERING_STATUS_CHANGED, status_changed(offering, "open")) == APPLIED
    row = one(org.id, OfferingRef)
    assert (row.status, row.course_code is not None) == ("open", True)
    assert row.status_as_of.replace(tzinfo=UTC) == NOW


def test_a_status_change_before_its_creation_leaves_a_partial_row_the_creation_completes(org):
    offering = uid()
    deliver(org.id, OFFERING_STATUS_CHANGED, status_changed(offering, "open"))
    partial = one(org.id, OfferingRef)
    assert (partial.status, partial.academic_period_id, partial.course_code, partial.credits) == (
        "open",
        None,
        None,
        None,
    )
    deliver(org.id, OFFERING_CREATED, offering_created(offering, code="CS101"))
    row = one(org.id, OfferingRef)
    assert (row.status, row.course_code, row.academic_period_id is not None) == ("open", "CS101", True)
    assert len(rows(org.id, OfferingRef)) == 1


def test_an_older_status_never_replaces_a_newer_one(org):
    offering = uid()
    deliver(
        org.id, OFFERING_STATUS_CHANGED, status_changed(offering, "in_progress"), occurred_at=NOW + timedelta(hours=1)
    )
    assert deliver(org.id, OFFERING_STATUS_CHANGED, status_changed(offering, "open"), occurred_at=NOW) == STALE
    assert one(org.id, OfferingRef).status == "in_progress"
    deliver(
        org.id, OFFERING_STATUS_CHANGED, status_changed(offering, "completed"), occurred_at=NOW + timedelta(hours=2)
    )
    assert one(org.id, OfferingRef).status == "completed"


def test_two_changes_at_the_same_instant_both_apply_and_the_later_delivery_wins(org):
    offering = uid()
    deliver(org.id, OFFERING_STATUS_CHANGED, status_changed(offering, "open"))
    assert deliver(org.id, OFFERING_STATUS_CHANGED, status_changed(offering, "cancelled")) == APPLIED
    assert one(org.id, OfferingRef).status == "cancelled"


# ---------------------------------------------------------------- idempotency and isolation


def test_the_same_delivery_twice_applies_once(org):
    payload, event_id = offering_created(), uid()
    assert deliver(org.id, OFFERING_CREATED, payload, event_id=event_id) == APPLIED
    assert deliver(org.id, OFFERING_CREATED, payload, event_id=event_id) == DUPLICATE
    assert len(rows(org.id, OfferingRef)) == 1
    assert [m.event_id for m in rows(org.id, ProcessedEvent)] == [event_id]


def test_a_repeated_status_delivery_is_a_duplicate_and_does_not_undo_a_later_status(org):
    offering, first_id = uid(), uid()
    deliver(org.id, OFFERING_STATUS_CHANGED, status_changed(offering, "open"), event_id=first_id)
    deliver(
        org.id, OFFERING_STATUS_CHANGED, status_changed(offering, "completed"), occurred_at=NOW + timedelta(hours=1)
    )
    assert deliver(org.id, OFFERING_STATUS_CHANGED, status_changed(offering, "open"), event_id=first_id) == DUPLICATE
    assert one(org.id, OfferingRef).status == "completed"


def test_the_same_envelope_id_in_two_organisations_applies_in_both(org, other_org):
    event_id, offering = uid(), uid()
    assert deliver(org.id, OFFERING_CREATED, offering_created(offering), event_id=event_id) == APPLIED
    assert deliver(other_org.id, OFFERING_CREATED, offering_created(offering), event_id=event_id) == APPLIED
    assert len(rows(org.id, OfferingRef)) == len(rows(other_org.id, OfferingRef)) == 1


def test_an_event_changes_only_its_own_organisation(org, other_org):
    offering = uid()
    deliver(org.id, OFFERING_CREATED, offering_created(offering, code="MINE"))
    deliver(other_org.id, OFFERING_CREATED, offering_created(offering, code="THEIRS"))
    deliver(org.id, OFFERING_STATUS_CHANGED, status_changed(offering, "open"))
    assert one(org.id, OfferingRef).course_code == "MINE" and one(org.id, OfferingRef).status == "open"
    assert one(other_org.id, OfferingRef).course_code == "THEIRS" and one(other_org.id, OfferingRef).status is None
    assert [r.organisation_id for r in rows(org.id, OfferingRef)] == [org.id]


def test_an_event_for_an_unscoped_session_is_refused_not_written_elsewhere(org, other_org):
    event = FakeEvent(OFFERING_CREATED, org.id, offering_created())
    with organisation_scope(other_org.id), SessionLocal() as db:
        with pytest.raises(RuntimeError, match="not scoped to the event's organisation"):
            CONSUMERS[OFFERING_CREATED](db, event)
        db.rollback()
    assert rows(org.id, OfferingRef) == [] and rows(other_org.id, OfferingRef) == []


def test_an_event_without_an_organisation_is_ignored(org):
    event = FakeEvent(OFFERING_CREATED, None, offering_created())
    with organisation_scope(org.id), SessionLocal() as db:
        assert CONSUMERS[OFFERING_CREATED](db, event) == IGNORED
        db.commit()
    assert rows(org.id, OfferingRef) == [] and markers(org.id) == 0


# ---------------------------------------------------------------- malformed events and rollback


@pytest.mark.parametrize(
    "change",
    [
        {"course_offering_id": None},
        {"course_offering_id": "not-a-uuid"},
        {"course_id": None},
        {"academic_period_id": 7},
        {"course_code": None},
        {"course_code": "  "},
        {"course_code": "X" * 41},
        {"course_title": None},
        {"course_title": "T" * 201},
        {"credits": None},
        {"credits": "four"},
        {"credits": True},
        {"credits": -1},
        {"credits": 10000},
        {"department_id": "dept"},
    ],
)
def test_a_malformed_creation_is_refused_and_writes_nothing(org, change):
    payload = {**offering_created(), **change}
    payload = {k: v for k, v in payload.items() if v is not None}
    with pytest.raises(ValueError):
        deliver(org.id, OFFERING_CREATED, payload)
    assert rows(org.id, OfferingRef) == [] and markers(org.id) == 0


@pytest.mark.parametrize(
    "change",
    [
        {"course_offering_id": None},
        {"course_offering_id": "x"},
        {"to_status": None},
        {"to_status": " "},
        {"to_status": "s" * 21},
    ],
)
def test_a_malformed_status_change_is_refused_and_writes_nothing(org, change):
    payload = {**status_changed(uid(), "open"), **change}
    payload = {k: v for k, v in payload.items() if v is not None}
    with pytest.raises(ValueError):
        deliver(org.id, OFFERING_STATUS_CHANGED, payload)
    assert rows(org.id, OfferingRef) == [] and markers(org.id) == 0


def test_a_payload_that_is_not_an_object_is_refused(org):
    with pytest.raises(ValueError, match="payload must be an object"):
        deliver(org.id, OFFERING_CREATED, ["not", "an", "object"])
    assert markers(org.id) == 0


def test_an_envelope_without_a_zoned_time_is_refused(org):
    with pytest.raises(ValueError, match="occurred_at"):
        deliver(org.id, OFFERING_CREATED, offering_created(), occurred_at=datetime(2026, 11, 5, 9, 0))
    assert rows(org.id, OfferingRef) == [] and markers(org.id) == 0


def test_an_unsupported_envelope_version_is_refused(org):
    with pytest.raises(consumers.UnsupportedEventVersionError):
        deliver(org.id, OFFERING_CREATED, offering_created(), version=2)
    assert rows(org.id, OfferingRef) == [] and markers(org.id) == 0


def test_a_failure_after_the_marker_and_the_row_are_written_rolls_both_back_and_the_redelivery_applies(
    org, monkeypatch
):
    payload, event_id = offering_created(), uid()
    real = consumers._offering_row

    def row_then_failure(db, organisation, offering_id):
        real(db, organisation, offering_id)
        db.flush()  # the row and the marker are both in the transaction now
        raise RuntimeError("store down")

    monkeypatch.setattr(consumers, "_offering_row", row_then_failure)
    with pytest.raises(RuntimeError, match="store down"):
        deliver(org.id, OFFERING_CREATED, payload, event_id=event_id)
    assert rows(org.id, OfferingRef) == [] and markers(org.id) == 0

    monkeypatch.setattr(consumers, "_offering_row", real)
    assert deliver(org.id, OFFERING_CREATED, payload, event_id=event_id) == APPLIED
    assert len(rows(org.id, OfferingRef)) == 1 and markers(org.id) == 1


def test_a_second_delivery_racing_for_one_envelope_id_is_settled_by_the_unique_constraint(org):
    from sqlalchemy.exc import IntegrityError

    event_id = uid()
    with organisation_scope(org.id), SessionLocal() as db:
        db.add(ProcessedEvent(organisation_id=org.id, event_id=event_id, name=OFFERING_CREATED))
        db.commit()
    with organisation_scope(org.id), SessionLocal() as db:
        db.add(ProcessedEvent(organisation_id=org.id, event_id=event_id, name=OFFERING_CREATED))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


# ---------------------------------------------------------------- what the module reads from it


def test_the_department_filter_of_the_module_finds_an_offering_once_its_creation_is_delivered(org):
    department, offering = uid(), uid()
    deliver(org.id, OFFERING_CREATED, offering_created(offering, department_id=department))
    deliver(org.id, OFFERING_CREATED, offering_created(department_id=uid()))
    with organisation_scope(org.id), SessionLocal() as db:
        found = db.scalars(
            repo.q(db, OfferingRef)
            .where(OfferingRef.department_id == department)
            .with_only_columns(OfferingRef.course_offering_id)
        ).all()
    assert found == [offering]


def test_an_unrelated_uuid_has_no_row(org):
    assert rows(org.id, OfferingRef, course_offering_id=str(uuid.uuid4())) == []
