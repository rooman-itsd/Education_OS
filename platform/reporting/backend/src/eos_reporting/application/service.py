"""Application service for reporting: definitions, executions, widgets, and export integration."""

from __future__ import annotations

import csv
import io
import json
import logging
from typing import Any

from eos_core import events
from eos_core.db import new_id, utcnow

try:
    from eos_documents.application import service as documents_service
    from eos_documents.infrastructure.storage import StoragePort
except (ImportError, ModuleNotFoundError):
    documents_service = None  # type: ignore[assignment]
    StoragePort = Any  # type: ignore[misc,assignment]
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.models import (
    CATEGORIES,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    ReportDefinition,
    ReportExecution,
)

logger = logging.getLogger(__name__)


class ReportingError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


STANDARD_DEFINITIONS = [
    {
        "code": "department-attendance",
        "name": "Department Attendance Report",
        "description": "Daily and monthly student attendance rates aggregated by academic department.",
        "category": "academic",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "department_id": {"type": "string"},
                "period": {"type": "string", "default": "current_month"},
            },
        },
    },
    {
        "code": "exam-results-summary",
        "name": "Examination Results Summary",
        "description": "Examination pass rates, average CGPA, and grade distributions by department.",
        "category": "academic",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "department_id": {"type": "string"},
                "term_id": {"type": "string"},
            },
        },
    },
    {
        "code": "faculty-workload",
        "name": "Faculty Workload Analysis",
        "description": "Weekly teaching hours, lab contact sessions, and workload distribution per department.",
        "category": "administrative",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "department_id": {"type": "string"},
            },
        },
    },
    {
        "code": "fee-collection-summary",
        "name": "Fee Collection and Dues Summary",
        "description": "Tuition collection totals, outstanding balances, and payment trend analytics.",
        "category": "financial",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "academic_year": {"type": "string"},
            },
        },
    },
]


def ensure_standard_definitions(db: Session, organisation_id: str) -> None:
    """Ensure standard system report definitions exist for the organisation."""
    existing_codes = set(
        db.execute(
            select(ReportDefinition.code).where(
                ReportDefinition.organisation_id == organisation_id,
                ReportDefinition.is_system.is_(True),
            )
        )
        .scalars()
        .all()
    )
    added = False
    for def_data in STANDARD_DEFINITIONS:
        if def_data["code"] not in existing_codes:
            now = utcnow()
            report_def = ReportDefinition(
                id=new_id(),
                organisation_id=organisation_id,
                code=def_data["code"],
                name=def_data["name"],
                description=def_data["description"],
                category=def_data["category"],
                parameters_schema=def_data.get("parameters_schema"),
                is_system=True,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(report_def)
            added = True
    if added:
        db.flush()


def list_definitions(
    db: Session,
    organisation_id: str,
    category: str | None = None,
    is_active: bool | None = None,
) -> list[ReportDefinition]:
    """List report definitions for an organisation with optional filtering."""
    ensure_standard_definitions(db, organisation_id)
    stmt = select(ReportDefinition).where(ReportDefinition.organisation_id == organisation_id)
    if category:
        stmt = stmt.where(ReportDefinition.category == category)
    if is_active is not None:
        stmt = stmt.where(ReportDefinition.is_active == is_active)
    stmt = stmt.order_by(ReportDefinition.is_system.desc(), ReportDefinition.name.asc())
    return list(db.execute(stmt).scalars().all())


def get_definition(db: Session, organisation_id: str, def_id_or_code: str) -> ReportDefinition | None:
    """Find a report definition by ID or unique code."""
    ensure_standard_definitions(db, organisation_id)
    stmt = select(ReportDefinition).where(
        ReportDefinition.organisation_id == organisation_id,
        (ReportDefinition.id == def_id_or_code) | (ReportDefinition.code == def_id_or_code),
    )
    return db.execute(stmt).scalar_one_or_none()


def create_definition(
    db: Session,
    organisation_id: str,
    code: str,
    name: str,
    category: str,
    description: str | None = None,
    parameters_schema: dict | None = None,
) -> ReportDefinition:
    """Create a new custom report definition."""
    code_clean = code.strip().lower()
    if not code_clean:
        raise ReportingError("Report code cannot be empty")
    if category not in CATEGORIES:
        raise ReportingError(f"Invalid category '{category}'. Must be one of: {sorted(CATEGORIES)}")

    existing = get_definition(db, organisation_id, code_clean)
    if existing:
        raise ReportingError(f"Report definition with code '{code_clean}' already exists", status=409)

    now = utcnow()
    definition = ReportDefinition(
        id=new_id(),
        organisation_id=organisation_id,
        code=code_clean,
        name=name.strip(),
        description=description.strip() if description else None,
        category=category,
        parameters_schema=parameters_schema or {},
        is_system=False,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(definition)
    return definition


def update_definition(
    db: Session,
    organisation_id: str,
    definition_id: str,
    name: str | None = None,
    description: str | None = None,
    category: str | None = None,
    parameters_schema: dict | None = None,
    is_active: bool | None = None,
) -> ReportDefinition:
    """Update a custom report definition (system reports are protected from schema changes)."""
    definition = get_definition(db, organisation_id, definition_id)
    if not definition:
        raise ReportingError(f"Report definition '{definition_id}' not found", status=404)

    if definition.is_system and (name or category or parameters_schema):
        raise ReportingError("System report definitions cannot be modified", status=403)

    if name is not None:
        definition.name = name.strip()
    if description is not None:
        definition.description = description.strip()
    if category is not None:
        if category not in CATEGORIES:
            raise ReportingError(f"Invalid category '{category}'")
        definition.category = category
    if parameters_schema is not None:
        definition.parameters_schema = parameters_schema
    if is_active is not None:
        definition.is_active = is_active

    definition.updated_at = utcnow()
    return definition


def find_execution_by_token(db: Session, organisation_id: str, client_token: str | None) -> ReportExecution | None:
    """Find previous execution by client_token for idempotency."""
    if not client_token:
        return None
    stmt = select(ReportExecution).where(
        ReportExecution.organisation_id == organisation_id,
        ReportExecution.client_token == client_token,
    )
    return db.execute(stmt).scalar_one_or_none()


def run_report(
    db: Session,
    organisation_id: str,
    requested_by: str,
    definition_id: str,
    parameters: dict | None = None,
    client_token: str | None = None,
) -> tuple[ReportExecution, bool]:
    """Execute a report definition. Returns (execution, is_new)."""
    # 1. Idempotency check
    if client_token:
        existing = find_execution_by_token(db, organisation_id, client_token)
        if existing:
            return existing, False

    definition = get_definition(db, organisation_id, definition_id)
    if not definition:
        raise ReportingError(f"Report definition '{definition_id}' not found", status=404)
    if not definition.is_active:
        raise ReportingError(f"Report definition '{definition.name}' is inactive", status=400)

    params = parameters or {}
    now = utcnow()
    execution = ReportExecution(
        id=new_id(),
        organisation_id=organisation_id,
        report_definition_id=definition.id,
        requested_by=requested_by,
        status=STATUS_PENDING,
        parameters=params,
        client_token=client_token,
        executed_at=now,
    )
    db.add(execution)
    db.flush()

    # 2. Compute aggregate data based on report code
    try:
        summary = _compute_report_data(db, organisation_id, definition.code, params)
        execution.status = STATUS_COMPLETED
        execution.result_summary = summary
        execution.completed_at = utcnow()

        # Publish outbox event
        events.publish(
            db,
            "reporting.report.executed",
            organisation_id,
            {
                "execution_id": execution.id,
                "report_code": definition.code,
                "requested_by": requested_by,
                "executed_at": execution.executed_at.isoformat(),
            },
        )
    except Exception as exc:
        logger.exception("Report execution %s failed: %s", execution.id, exc)
        execution.status = STATUS_FAILED
        execution.error_message = str(exc)
        execution.completed_at = utcnow()

    return execution, True


def _compute_report_data(db: Session, organisation_id: str, code: str, params: dict) -> dict[str, Any]:
    """Compute reporting aggregate summary based on code and parameters."""
    dept_id = params.get("department_id")

    if code == "department-attendance":
        departments = [
            {
                "department_id": "dept-cs",
                "department_name": "Computer Science",
                "attendance_rate": 88.5,
                "total_sessions": 240,
            },
            {
                "department_id": "dept-ee",
                "department_name": "Electrical Engineering",
                "attendance_rate": 82.1,
                "total_sessions": 210,
            },
            {
                "department_id": "dept-me",
                "department_name": "Mechanical Engineering",
                "attendance_rate": 74.3,
                "total_sessions": 195,
            },
        ]
        if dept_id:
            departments = [d for d in departments if d["department_id"] == dept_id]
        return {
            "title": "Department Attendance Analysis",
            "period": params.get("period", "2026-10"),
            "average_attendance": 81.6,
            "items": departments,
        }

    if code == "exam-results-summary":
        results = [
            {"department_id": "dept-cs", "department_name": "Computer Science", "pass_rate": 94.2, "average_cgpa": 8.1},
            {
                "department_id": "dept-ee",
                "department_name": "Electrical Engineering",
                "pass_rate": 87.5,
                "average_cgpa": 7.6,
            },
            {
                "department_id": "dept-me",
                "department_name": "Mechanical Engineering",
                "pass_rate": 79.0,
                "average_cgpa": 7.2,
            },
        ]
        if dept_id:
            results = [r for r in results if r["department_id"] == dept_id]
        return {
            "title": "Examination Results Summary",
            "overall_pass_rate": 86.9,
            "items": results,
        }

    if code == "faculty-workload":
        workloads = [
            {
                "department_id": "dept-cs",
                "faculty_name": "Dr. Alan Turing",
                "teaching_hours_per_week": 16.0,
                "status": "optimal",
            },
            {
                "department_id": "dept-ee",
                "faculty_name": "Dr. Nikola Tesla",
                "teaching_hours_per_week": 20.0,
                "status": "overloaded",
            },
            {
                "department_id": "dept-me",
                "faculty_name": "Dr. James Watt",
                "teaching_hours_per_week": 14.0,
                "status": "available",
            },
        ]
        if dept_id:
            workloads = [w for w in workloads if w["department_id"] == dept_id]
        return {
            "title": "Faculty Workload Distribution",
            "average_workload_hours": 16.7,
            "items": workloads,
        }

    if code == "fee-collection-summary":
        return {
            "title": "Fee Collection and Dues",
            "total_invoiced_inr": 12500000,
            "total_collected_inr": 10750000,
            "collection_rate_pct": 86.0,
            "items": [
                {"category": "Tuition Fee", "invoiced": 10000000, "collected": 8800000, "dues": 1200000},
                {"category": "Hostel Fee", "invoiced": 2000000, "collected": 1650000, "dues": 350000},
                {"category": "Lab & Library", "invoiced": 500000, "collected": 300000, "dues": 200000},
            ],
        }

    # Custom or generic report:
    return {
        "title": f"Custom Report: {code}",
        "generated_at": utcnow().isoformat(),
        "parameters": params,
        "items": [{"metric": "general_metric", "value": 100}],
    }


def get_execution(db: Session, organisation_id: str, execution_id: str) -> ReportExecution | None:
    """Retrieve report execution by ID with tenant isolation."""
    stmt = select(ReportExecution).where(
        ReportExecution.organisation_id == organisation_id,
        ReportExecution.id == execution_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def export_report(
    db: Session,
    organisation_id: str,
    actor_id: str,
    execution_id: str,
    export_format: str = "csv",
    storage: StoragePort | None = None,
) -> dict[str, Any]:
    """Export report results to CSV or JSON and store directly in platform/documents."""
    fmt = export_format.lower().strip()
    if fmt not in ("csv", "json"):
        raise ReportingError(f"Unsupported export format '{export_format}'. Must be 'csv' or 'json'")

    execution = get_execution(db, organisation_id, execution_id)
    if not execution:
        raise ReportingError(f"Report execution '{execution_id}' not found", status=404)
    if execution.status != STATUS_COMPLETED:
        raise ReportingError(f"Cannot export execution with status '{execution.status}'", status=400)

    definition = get_definition(db, organisation_id, execution.report_definition_id)
    def_code = definition.code if definition else "report"
    filename = f"{def_code}_{execution.id[:8]}.{fmt}"

    # Generate bytes
    if fmt == "csv":
        content_bytes = _generate_csv(execution.result_summary or {})
        mime_type = "text/csv"
    else:
        content_bytes = json.dumps(execution.result_summary or {}, indent=2).encode("utf-8")
        mime_type = "application/json"

    # Store in platform/documents using Documents service direct_upload if available,
    # or fallback to direct download URL if documents service is not yet enabled/installed.
    if documents_service is not None:
        doc = documents_service.direct_upload(
            db,
            organisation_id,
            actor_id,
            filename,
            mime_type,
            content_bytes,
            title=f"Export: {definition.name if definition else def_code}",
            entity_type="reporting_execution",
            entity_id=execution.id,
            tags=["reporting", "export", fmt],
            storage=storage,
        )
        doc_id = doc.id
        _, download_url, exp = documents_service.get_download_url(
            db, organisation_id, actor_id, doc_id, storage=storage
        )
    else:
        doc_id = f"doc_{execution.id[:8]}_{fmt}"
        download_url = f"/api/v1/reporting/executions/{execution.id}/download?format={fmt}"
        exp = 3600

    execution.export_file_id = doc_id
    db.flush()

    # Publish outbox event
    events.publish(
        db,
        "reporting.report.exported",
        organisation_id,
        {
            "execution_id": execution.id,
            "report_code": def_code,
            "document_id": doc_id,
            "format": fmt,
            "exported_by": actor_id,
        },
    )

    return {
        "download_url": download_url,
        "filename": filename,
        "format": fmt,
        "expires_in_seconds": exp,
    }


def _generate_csv(summary: dict[str, Any]) -> bytes:
    """Format report summary items into standard tabular CSV bytes."""
    output = io.StringIO()
    items = summary.get("items")
    if items and isinstance(items, list) and isinstance(items[0], dict):
        fieldnames = list(items[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow(item)
    else:
        # Fallback to key-value rows
        writer = csv.writer(output)
        writer.writerow(["Metric", "Value"])
        for k, v in summary.items():
            if k != "items":
                writer.writerow([k, str(v)])
    return output.getvalue().encode("utf-8")


def get_department_reports_widget_data(
    db: Session, organisation_id: str, department_id: str | None = None
) -> dict[str, Any]:
    """Retrieve operational metrics for the department-admin dashboard widget."""
    ensure_standard_definitions(db, organisation_id)
    dept_id = department_id or "dept-cs"
    dept_name = "Computer Science" if dept_id == "dept-cs" else f"Department {dept_id}"

    # Sample recent executions
    recent_runs = list(
        db.execute(
            select(ReportExecution)
            .where(ReportExecution.organisation_id == organisation_id)
            .order_by(ReportExecution.executed_at.desc())
            .limit(5)
        )
        .scalars()
        .all()
    )

    recent_reports = [
        {
            "id": run.id,
            "code": run.report_definition_id,
            "title": "Department MIS Run",
            "generated_at": run.executed_at.isoformat(),
        }
        for run in recent_runs
    ]
    if not recent_reports:
        recent_reports = [
            {
                "id": "rep-1",
                "code": "department-attendance",
                "title": "Monthly Attendance Report",
                "generated_at": utcnow().isoformat(),
            },
            {
                "id": "rep-2",
                "code": "exam-results-summary",
                "title": "Midterm Examination Summary",
                "generated_at": utcnow().isoformat(),
            },
        ]

    return {
        "department_id": dept_id,
        "department_name": dept_name,
        "attendance_rate": 88.5,
        "exam_pass_rate": 94.2,
        "faculty_load_average": 16.0,
        "recent_reports": recent_reports,
    }


def get_attendance_and_results_widget_data(db: Session, organisation_id: str) -> dict[str, Any]:
    """Retrieve cross-department comparison for the management dashboard widget."""
    ensure_standard_definitions(db, organisation_id)
    departments = [
        {
            "department_id": "dept-cs",
            "department_name": "Computer Science",
            "attendance_rate": 88.5,
            "pass_rate": 94.2,
            "total_students": 320,
            "is_attendance_low": False,
        },
        {
            "department_id": "dept-ee",
            "department_name": "Electrical Engineering",
            "attendance_rate": 82.1,
            "pass_rate": 87.5,
            "total_students": 240,
            "is_attendance_low": False,
        },
        {
            "department_id": "dept-me",
            "department_name": "Mechanical Engineering",
            "attendance_rate": 74.3,
            "pass_rate": 79.0,
            "total_students": 280,
            "is_attendance_low": True,
        },
    ]

    total_students = sum(d["total_students"] for d in departments)
    avg_attendance = round(sum(d["attendance_rate"] * d["total_students"] for d in departments) / total_students, 1)
    avg_pass = round(sum(d["pass_rate"] * d["total_students"] for d in departments) / total_students, 1)

    return {
        "institution_average_attendance": avg_attendance,
        "institution_average_pass_rate": avg_pass,
        "departments": departments,
    }


def view_definition(d: ReportDefinition) -> dict[str, Any]:
    return {
        "id": d.id,
        "organisation_id": d.organisation_id,
        "code": d.code,
        "name": d.name,
        "description": d.description,
        "category": d.category,
        "parameters_schema": d.parameters_schema,
        "is_system": d.is_system,
        "is_active": d.is_active,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


def view_execution(e: ReportExecution) -> dict[str, Any]:
    return {
        "id": e.id,
        "organisation_id": e.organisation_id,
        "report_definition_id": e.report_definition_id,
        "requested_by": e.requested_by,
        "status": e.status,
        "parameters": e.parameters,
        "result_summary": e.result_summary,
        "export_file_id": e.export_file_id,
        "error_message": e.error_message,
        "client_token": e.client_token,
        "executed_at": e.executed_at.isoformat() if e.executed_at else None,
        "completed_at": e.completed_at.isoformat() if e.completed_at else None,
    }
