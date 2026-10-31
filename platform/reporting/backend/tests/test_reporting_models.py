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


def test_metric_snapshot():
    now = utcnow()
    s = MetricSnapshot(
        id=new_id(),
        organisation_id="org-1",
        metric_type="attendance",
        department_id="dept-cs",
        period="2026-10",
        data={"present": 92, "total": 100},
        captured_at=now,
    )
    assert s.metric_type == "attendance"
    assert s.department_id == "dept-cs"
    assert s.period == "2026-10"
    assert s.data["present"] == 92


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
    e1 = ReportExecution(
        id=new_id(),
        organisation_id="org-unique",
        report_definition_id="def-1",
        requested_by="user-1",
        client_token="tok-123",
    )
    db.add(e1)
    db.commit()

    e2 = ReportExecution(
        id=new_id(),
        organisation_id="org-unique",
        report_definition_id="def-1",
        requested_by="user-2",
        client_token="tok-123",
    )
    db.add(e2)
    import pytest
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
