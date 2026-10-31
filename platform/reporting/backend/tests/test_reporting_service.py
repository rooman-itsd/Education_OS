"""Application service tests for reporting: definitions, runs, widgets, and export integration."""

from __future__ import annotations

import pytest
from eos_core.db import utcnow
from eos_core.events import OutboxEvent
from eos_reporting.application import service
from eos_reporting.application.service import ReportingError
from eos_reporting.domain.models import STATUS_COMPLETED, MetricSnapshot
from sqlalchemy import select


def test_ensure_standard_definitions_and_listing(db, org):
    defs = service.list_definitions(db, org.id)
    assert len(defs) >= 4
    codes = {d.code for d in defs}
    assert "department-attendance" in codes
    assert "exam-results-summary" in codes
    assert "faculty-workload" in codes
    assert "fee-collection-summary" in codes

    academic_defs = service.list_definitions(db, org.id, category="academic")
    assert all(d.category == "academic" for d in academic_defs)


def test_create_custom_definition_and_refuses_duplicate(db, org):
    d = service.create_definition(
        db,
        org.id,
        code="library-circulations",
        name="Library Circulation Trends",
        category="administrative",
        description="Daily borrow and return counts",
    )
    db.commit()
    assert d.code == "library-circulations"
    assert d.is_system is False

    # Duplicate code
    with pytest.raises(ReportingError) as exc:
        service.create_definition(
            db,
            org.id,
            code="library-circulations",
            name="Another circulation report",
            category="administrative",
        )
    assert exc.value.status == 409

    # Invalid category
    with pytest.raises(ReportingError) as exc:
        service.create_definition(
            db,
            org.id,
            code="invalid-cat",
            name="Invalid Category Report",
            category="non_existent",
        )
    assert exc.value.status == 400


def test_update_custom_definition_and_protects_system_reports(db, org):
    d = service.create_definition(
        db,
        org.id,
        code="hostel-occupancy",
        name="Hostel Occupancy",
        category="administrative",
    )
    db.commit()

    updated = service.update_definition(
        db,
        org.id,
        d.id,
        name="Hostel Occupancy Analysis",
        is_active=False,
    )
    db.commit()
    assert updated.name == "Hostel Occupancy Analysis"
    assert updated.is_active is False

    # Attempting to edit system report schema
    sys_def = service.get_definition(db, org.id, "department-attendance")
    assert sys_def.is_system is True
    with pytest.raises(ReportingError) as exc:
        service.update_definition(db, org.id, sys_def.id, name="Tampered Attendance")
    assert exc.value.status == 403


def test_run_report_execution_and_idempotency(db, org):
    sys_def = service.get_definition(db, org.id, "department-attendance")
    token = "run-token-123"

    # 1. Fresh execution
    exec1, is_new1 = service.run_report(
        db,
        org.id,
        org.admin_id,
        sys_def.id,
        parameters={"department_id": "dept-cs"},
        client_token=token,
    )
    db.commit()

    assert is_new1 is True
    assert exec1.status == STATUS_COMPLETED
    assert exec1.result_summary is not None
    assert "average_attendance" in exec1.result_summary

    # Check outbox event
    events = list(
        db.execute(select(OutboxEvent).where(OutboxEvent.name == "reporting.report.executed")).scalars().all()
    )
    assert any(e.payload.get("execution_id") == exec1.id for e in events)

    # 2. Replayed execution with same client_token returns original
    exec2, is_new2 = service.run_report(
        db,
        org.id,
        org.admin_id,
        sys_def.id,
        parameters={"department_id": "dept-cs"},
        client_token=token,
    )
    assert is_new2 is False
    assert exec2.id == exec1.id


def test_export_report_csv_and_json_via_documents(db, org, memory_storage):
    sys_def = service.get_definition(db, org.id, "fee-collection-summary")
    execution, _ = service.run_report(db, org.id, org.admin_id, sys_def.id)
    db.commit()

    # 1. Export as CSV
    res_csv = service.export_report(
        db,
        org.id,
        org.admin_id,
        execution.id,
        export_format="csv",
        storage=memory_storage,
    )
    db.commit()

    assert res_csv["format"] == "csv"
    assert res_csv["filename"].endswith(".csv")
    assert "download_url" in res_csv
    assert execution.export_file_id is not None

    # Check outbox event
    events = list(
        db.execute(select(OutboxEvent).where(OutboxEvent.name == "reporting.report.exported")).scalars().all()
    )
    assert len(events) >= 1
    assert events[-1].payload["format"] == "csv"

    # 2. Export as JSON
    res_json = service.export_report(
        db,
        org.id,
        org.admin_id,
        execution.id,
        export_format="json",
        storage=memory_storage,
    )
    db.commit()
    assert res_json["format"] == "json"
    assert res_json["filename"].endswith(".json")


def test_widget_data_generation(db, org):
    # 1. When no snapshots are recorded, returns clean zeroes and empty lists
    empty_dept = service.get_department_reports_widget_data(db, org.id, department_id="dept-cs")
    assert empty_dept["department_id"] == "dept-cs"
    assert empty_dept["attendance_rate"] == 0.0
    assert empty_dept["exam_pass_rate"] == 0.0
    assert empty_dept["recent_reports"] == []

    empty_mgmt = service.get_attendance_and_results_widget_data(db, org.id)
    assert empty_mgmt["institution_average_attendance"] == 0.0
    assert empty_mgmt["departments"] == []

    # 2. Ingest real MetricSnapshot records for org
    now_period = utcnow().strftime("%Y-%m")
    snap1 = MetricSnapshot(
        organisation_id=org.id,
        metric_type="department_summary",
        department_id="dept-cs",
        period=now_period,
        data={
            "department_id": "dept-cs",
            "department_name": "Computer Science",
            "attendance_rate": 88.5,
            "pass_rate": 94.2,
            "faculty_load_average": 16.0,
            "total_students": 120,
        },
    )
    snap2 = MetricSnapshot(
        organisation_id=org.id,
        metric_type="department_summary",
        department_id="dept-ee",
        period=now_period,
        data={
            "department_id": "dept-ee",
            "department_name": "Electrical Engineering",
            "attendance_rate": 82.0,
            "pass_rate": 90.0,
            "faculty_load_average": 14.0,
            "total_students": 100,
        },
    )
    db.add_all([snap1, snap2])
    db.commit()

    # Department widget retrieves real metrics
    dept_data = service.get_department_reports_widget_data(db, org.id, department_id="dept-cs")
    assert dept_data["department_id"] == "dept-cs"
    assert dept_data["department_name"] == "Computer Science"
    assert dept_data["attendance_rate"] == 88.5
    assert dept_data["exam_pass_rate"] == 94.2
    assert dept_data["faculty_load_average"] == 16.0

    # Management widget aggregates across real department snapshots
    mgmt_data = service.get_attendance_and_results_widget_data(db, org.id)
    assert mgmt_data["institution_average_attendance"] == 85.2
    assert mgmt_data["institution_average_pass_rate"] == 92.1
    assert len(mgmt_data["departments"]) == 2


def test_csv_formula_injection_prevention():
    summary = {
        "items": [{"name": "=1+2", "cmd": "@calc", "plus": "+100", "minus": "-50", "tab": "\tdata", "normal": "safe"}]
    }
    csv_bytes = service._generate_csv(summary)
    csv_text = csv_bytes.decode("utf-8")
    assert "'=1+2" in csv_text
    assert "'@calc" in csv_text
    assert "'+100" in csv_text
    assert "'-50" in csv_text
    assert "'\tdata" in csv_text
    assert "safe" in csv_text
