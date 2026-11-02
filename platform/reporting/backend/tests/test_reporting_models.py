"""Unit tests for reporting domain models."""

from __future__ import annotations

from eos_core.db import new_id, utcnow
from eos_reporting.domain.models import (
    ALLOWED_STATUSES,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    TABLE_NAMES,
    MetricSnapshot,
    ReportDefinition,
    ReportExecution,
)


def test_table_names_declared():
    assert "reporting_definition" in TABLE_NAMES
    assert "reporting_execution" in TABLE_NAMES
    assert "reporting_metric_snapshot" in TABLE_NAMES


def test_report_definition_defaults():
    d = ReportDefinition(
        id=new_id(),
        organisation_id="org-1",
        code="dept-attendance",
        name="Department Attendance",
        category="academic",
        is_system=False,
        is_active=True,
    )
    assert d.code == "dept-attendance"
    assert d.name == "Department Attendance"
    assert d.category == "academic"
    assert d.is_system is False
    assert d.is_active is True


def test_report_execution_states():
    assert STATUS_PENDING in ALLOWED_STATUSES
    assert STATUS_COMPLETED in ALLOWED_STATUSES
    assert STATUS_FAILED in ALLOWED_STATUSES

    e = ReportExecution(
        id=new_id(),
        organisation_id="org-1",
        report_definition_id="def-1",
        requested_by="usr-1",
        status=STATUS_PENDING,
    )
    assert e.status == STATUS_PENDING
    assert e.result_summary is None
    assert e.export_file_id is None


def test_metric_snapshot_has_the_agreed_logical_fields():
    from datetime import date
    from decimal import Decimal

    s = MetricSnapshot(
        id=new_id(),
        organisation_id="org-1",
        source_module="admissions",
        metric_key="admissions.applications_submitted",
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        dimensions={"programme_id": "p-1"},
        dimensions_key='{"programme_id":"p-1"}',
        value=Decimal("12"),
        unit="count",
        calculated_at=utcnow(),
        schema_version=1,
    )
    assert s.tenant_id == "org-1" and s.metric_key == "admissions.applications_submitted"
    assert (s.period_start, s.period_end, s.unit, s.schema_version) == (
        date(2026, 10, 1),
        date(2026, 10, 31),
        "count",
        1,
    )


def test_unique_constraint_on_definition_org_code(db):
    d1 = ReportDefinition(
        id=new_id(),
        organisation_id="org-unique",
        code="unique-code",
        name="Unique 1",
    )
    db.add(d1)
    db.commit()

    d2 = ReportDefinition(
        id=new_id(),
        organisation_id="org-unique",
        code="unique-code",
        name="Unique 2",
    )
    db.add(d2)
    import pytest
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_unique_constraint_on_execution_client_token(db):
    """client_token is unique per requester: the same user's duplicate is refused, another user's is not (it must
    never resolve to someone else's run)."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    def run(user: str) -> ReportExecution:
        return ReportExecution(
            id=new_id(),
            organisation_id="org-unique",
            report_definition_id="def-1",
            requested_by=user,
            client_token="tok-123",
        )

    db.add(run("user-1"))
    db.commit()

    db.add(run("user-2"))
    db.commit()  # another requester may use the same token

    db.add(run("user-1"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
