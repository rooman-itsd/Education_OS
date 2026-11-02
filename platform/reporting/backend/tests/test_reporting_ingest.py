"""MetricSnapshot ingestion through the event bus (decision on #317): admissions, academics and finance events become
facts and snapshots; idempotent, tenant-isolated, recalculable, validated, aggregate-only, and financial metrics
behind reporting:report:execute. examinations and timetable-attendance publish nothing yet: reported unavailable."""

from __future__ import annotations

import tomllib
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from eos_core.db import SessionLocal
from eos_core.tenant import organisation_scope
from eos_reporting.application import ingest, metrics
from eos_reporting.application.metrics import InvalidPayloadError
from eos_reporting.domain.models import MetricFact, MetricSnapshot
from sqlalchemy import select

MODULE = Path(__file__).resolve().parents[2]
OCT = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
NOV = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)


def ev(name, org, payload, at=OCT, event_id=None):
    return SimpleNamespace(
        id=event_id or str(uuid.uuid4()), name=name, organisation_id=org, payload=payload, occurred_at=at
    )


def deliver(e) -> None:
    """As the relay does: a session of its own, in the event's organisation."""
    with organisation_scope(e.organisation_id), SessionLocal() as db:
        ingest.CONSUMERS[e.name](db, e)
        db.commit()


def cells(org, key) -> list[MetricSnapshot]:
    with organisation_scope(org), SessionLocal() as db:
        return list(db.scalars(select(MetricSnapshot).where(
            MetricSnapshot.organisation_id == org, MetricSnapshot.metric_key == key).order_by(MetricSnapshot.period_start)))  # fmt: skip


def facts(org) -> list[MetricFact]:
    with organisation_scope(org), SessionLocal() as db:
        return list(db.scalars(select(MetricFact).where(MetricFact.organisation_id == org)))


def submitted(org, programme="prog-1", year="2026-27", at=OCT):
    return ev("admissions.application.submitted", org, {
        "organisation_id": org, "application_id": str(uuid.uuid4()), "reference_number": "APP-1",
        "programme_id": programme, "academic_year": year, "applicant_email": "someone@example.com"}, at)  # fmt: skip


def test_admissions_events_become_monthly_snapshots_by_programme_and_year():
    org = str(uuid.uuid4())
    for _ in range(3):
        deliver(submitted(org))
    deliver(submitted(org, programme="prog-2"))
    deliver(submitted(org, at=NOV))
    rows = cells(org, "admissions.applications_submitted")
    got = {(r.period_start, r.dimensions["programme_id"]): r.value for r in rows}
    assert got == {
        (date(2026, 10, 1), "prog-1"): Decimal(3),
        (date(2026, 10, 1), "prog-2"): Decimal(1),
        (date(2026, 11, 1), "prog-1"): Decimal(1),
    }
    r = rows[0]
    assert (r.tenant_id, r.source_module, r.unit, r.schema_version, r.period_end) == (
        org, "admissions", "count", 1, date(2026, 10, 31))  # fmt: skip


def test_a_redelivered_event_is_ingested_once():
    org = str(uuid.uuid4())
    e = submitted(org)
    deliver(e)
    deliver(e)
    (row,) = cells(org, "admissions.applications_submitted")
    assert row.value == 1 and len(facts(org)) == 1


def test_no_personal_information_reaches_a_fact_or_snapshot():
    org = str(uuid.uuid4())
    deliver(submitted(org))
    deliver(ev("admissions.application.accepted", org, {
        "organisation_id": org, "application_id": "a1", "reference_number": "R", "programme_id": "prog-1",
        "academic_year": "2026-27", "applicant_first_name": "Asha", "applicant_last_name": "Rao",
        "applicant_email": "asha@example.com", "user_id": "u-9"}))  # fmt: skip
    deliver(ev("fees-accounts.payment.received", org, {
        "organisation_id": org, "payment_id": "p1", "invoice_id": "i1", "person_id": "student-7",
        "amount": "1500.00", "mode": "upi", "receipt_id": "r1"}))  # fmt: skip
    text = repr([(f.dimensions, f.source_ref) for f in facts(org)])
    for personal in ("Asha", "Rao", "asha@example.com", "someone@example.com", "u-9", "student-7"):
        assert personal not in text


def test_finance_events_net_out_voids_and_keep_amounts_exact():
    org = str(uuid.uuid4())
    deliver(
        ev(
            "fees-accounts.payment.received",
            org,
            {
                "payment_id": "p1",
                "invoice_id": "i",
                "person_id": "x",
                "amount": "1500.50",
                "mode": "upi",
                "receipt_id": "r",
            },
        )
    )
    deliver(
        ev(
            "fees-accounts.payment.received",
            org,
            {
                "payment_id": "p2",
                "invoice_id": "i",
                "person_id": "x",
                "amount": "999.25",
                "mode": "upi",
                "receipt_id": "r",
            },
        )
    )
    deliver(
        ev(
            "fees-accounts.payment.voided",
            org,
            {"payment_id": "p2", "invoice_id": "i", "person_id": "x", "amount": "999.25", "reason": "bounced"},
        )
    )
    total = sum(r.value for r in cells(org, "finance.fees_collected"))
    assert total == Decimal("1500.50")


def test_faculty_contact_hours_follow_the_offerings_department_and_are_released_when_an_assignment_ends():
    org = str(uuid.uuid4())
    deliver(
        ev(
            "academic-management.offering.created",
            org,
            {"course_offering_id": "off-1", "course_id": "c", "academic_period_id": "t1", "department_id": "dept-cs"},
        )
    )
    deliver(ev("academic-management.faculty-assignment.created", org, {
        "instructor_assignment_id": "ia-1", "course_offering_id": "off-1", "faculty_id": "f1", "role": "primary",
        "contact_hours": 6}))  # fmt: skip
    deliver(ev("academic-management.faculty-assignment.created", org, {
        "instructor_assignment_id": "ia-2", "course_offering_id": "off-unknown", "faculty_id": "f2",
        "role": "primary", "contact_hours": 3}))  # fmt: skip
    deliver(ev("academic-management.faculty-assignment.ended", org, {
        "instructor_assignment_id": "ia-1", "course_offering_id": "off-1", "faculty_id": "f1",
        "ended_at": NOV.isoformat()}, at=NOV))  # fmt: skip
    by_month = {
        (r.period_start, r.dimensions["department_id"]): r.value for r in cells(org, "academics.faculty_contact_hours")
    }
    assert by_month == {
        (date(2026, 10, 1), "dept-cs"): Decimal(6),
        (date(2026, 10, 1), "unknown"): Decimal(3),  # an offering created before ingestion started
        (date(2026, 11, 1), "dept-cs"): Decimal(-6),  # released
    }


@pytest.mark.parametrize(
    "name, payload",
    [
        ("admissions.application.submitted", {"application_id": "a", "academic_year": "2026-27"}),  # no programme
        ("fees-accounts.payment.received", {"payment_id": "p", "amount": "not-a-number"}),
        ("fees-accounts.refund.issued", {"refund_id": "r", "amount": "-5"}),
        ("academic-management.faculty-assignment.created", {"instructor_assignment_id": "ia", "contact_hours": 2}),
    ],
)
def test_a_malformed_event_raises_so_the_relay_retries_and_dead_letters_it(name, payload):
    org = str(uuid.uuid4())
    with pytest.raises(InvalidPayloadError):
        deliver(ev(name, org, payload))
    assert facts(org) == []


def test_each_organisation_sees_only_its_own_metrics():
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    deliver(submitted(a))
    deliver(submitted(b))
    deliver(submitted(b))
    assert [r.value for r in cells(a, "admissions.applications_submitted")] == [1]
    assert [r.value for r in cells(b, "admissions.applications_submitted")] == [2]


def test_historical_recalculation_rebuilds_a_range_from_the_facts():
    org = str(uuid.uuid4())
    for _ in range(2):
        deliver(submitted(org))
    deliver(submitted(org, at=NOV))
    with organisation_scope(org), SessionLocal() as db:  # a cell lost or corrupted
        for row in db.scalars(select(MetricSnapshot).where(MetricSnapshot.organisation_id == org)):
            row.value = Decimal(999)
        db.commit()
    with organisation_scope(org), SessionLocal() as db:
        written = ingest.recalculate(db, org, date(2026, 10, 1), date(2026, 11, 30))
        db.commit()
    assert written == 2
    assert [r.value for r in cells(org, "admissions.applications_submitted")] == [2, 1]


def test_the_definitions_are_versioned_and_wired_to_the_event_bus():
    assert all(
        m.version >= 1 and m.unit and m.category in ("academic", "administrative", "financial") for m in metrics.METRICS
    )
    assert {m.source_module for m in metrics.METRICS} == {"admissions", "academic-management", "fees-accounts"}
    assert all(m.category == "financial" for m in metrics.METRICS if m.source_module == "fees-accounts")
    pyproject = tomllib.loads((MODULE / "backend" / "pyproject.toml").read_text())
    assert pyproject["project"]["entry-points"]["eos.event_consumers"] == {
        "reporting": "eos_reporting.application.ingest:CONSUMERS"
    }
    assert set(ingest.CONSUMERS) == set(metrics.source_events())
    contract = yaml.safe_load((MODULE / "contracts" / "events.yaml").read_text())
    assert set(contract["consumes"]) == set(metrics.source_events())


def test_every_source_event_is_one_its_module_publishes():
    """No invented event names: each is declared in its source module's own contract."""
    root = MODULE.parents[1]
    contracts = {
        "admissions": root / "modules/student-lifecycle/admissions/contracts/events.yaml",
        "academic-management": root / "modules/academics/academic-management/contracts/events.yaml",
        "fees-accounts": root / "modules/finance-operations/fees-accounts/contracts/events.yaml",
    }
    declared = set()
    for path in contracts.values():
        declared |= {e["name"] for e in yaml.safe_load(path.read_text())["events"]}
    assert set(metrics.source_events()) <= declared
