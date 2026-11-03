"""Application service for reporting: definitions, executions, widgets, and export integration."""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import UTC, date, datetime
from typing import Any

from eos_core import events
from eos_core.db import new_id, utcnow
from sqlalchemy.exc import IntegrityError

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
    MetricSnapshot,
    ReportDefinition,
    ReportExecution,
)
from . import ingest, metrics

logger = logging.getLogger(__name__)


FINANCIAL = "financial"


def summary_needs_execute(definition: ReportDefinition | None) -> bool:
    """Financial report data (fee collection, dues) is for roles that may run and export reports
    (reporting:report:execute). reporting:report:read covers academic and administrative summaries only."""
    return definition is not None and definition.category == FINANCIAL


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
            try:
                with db.begin_nested():
                    db.add(report_def)
                    db.flush()
            except IntegrityError:
                pass


def list_definitions(
    db: Session,
    organisation_id: str,
    category: str | None = None,
    is_active: bool | None = None,
) -> list[ReportDefinition]:
    """List report definitions for an organisation with optional filtering (read-only)."""
    stmt = select(ReportDefinition).where(ReportDefinition.organisation_id == organisation_id)
    if category:
        stmt = stmt.where(ReportDefinition.category == category)
    if is_active is not None:
        stmt = stmt.where(ReportDefinition.is_active == is_active)
    stmt = stmt.order_by(ReportDefinition.is_system.desc(), ReportDefinition.name.asc())
    return list(db.execute(stmt).scalars().all())


def get_definition(db: Session, organisation_id: str, def_id_or_code: str) -> ReportDefinition | None:
    """Find a report definition by ID or unique code (read-only)."""
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

    if definition.is_system and (name is not None or category is not None or parameters_schema is not None):
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


def find_execution_by_token(
    db: Session, organisation_id: str, requested_by: str, client_token: str | None
) -> ReportExecution | None:
    """The caller's own earlier run with this client_token. Tokens are per requester: another user's run with the
    same token is never returned (it would hand them that run's data)."""
    if not client_token:
        return None
    stmt = select(ReportExecution).where(
        ReportExecution.organisation_id == organisation_id,
        ReportExecution.requested_by == requested_by,
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
        existing = find_execution_by_token(db, organisation_id, requested_by, client_token)
        if existing:
            return existing, False

    definition = get_definition(db, organisation_id, definition_id)
    if not definition:
        ensure_standard_definitions(db, organisation_id)
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
        execution.error_message = _sanitize_error_message(exc)
        execution.completed_at = utcnow()

    return execution, True


def _sanitize_error_message(exc: Exception) -> str:
    """Return a safe error message without leaking sensitive internal details."""
    msg = str(exc).strip().split("\n")[0]
    return f"Report computation failed: {msg[:200]}"


REPORT_METRICS = {
    "faculty-workload": ("academics.faculty_contact_hours",),
    "fee-collection-summary": (
        "finance.fees_invoiced",
        "finance.fees_collected",
        "finance.refunds_issued",
        "finance.concessions_approved",
    ),
}
REPORT_UNAVAILABLE = {"department-attendance": "attendance", "exam-results-summary": "exam_results"}


def _period_bounds(period: str) -> tuple[date, date]:
    try:
        year, month = (int(x) for x in period.split("-")[:2])
        return ingest.month_of(datetime(year, month, 1, tzinfo=UTC))
    except (ValueError, TypeError) as e:
        raise ReportingError(f"period must be YYYY-MM, not {period!r}") from e


def metric_rows(
    db: Session, organisation_id: str, metric_key: str, start: date, end: date, department_id: str | None = None
) -> list[MetricSnapshot]:
    """The metric's snapshots (current schema version) for every month from start to end, this organisation only."""
    metric = metrics.BY_KEY[metric_key]
    stmt = select(MetricSnapshot).where(
        MetricSnapshot.organisation_id == organisation_id,
        MetricSnapshot.metric_key == metric_key,
        MetricSnapshot.schema_version == metric.version,
        MetricSnapshot.period_start >= start,
        MetricSnapshot.period_end <= end,
    )
    rows = list(db.execute(stmt.order_by(MetricSnapshot.period_start)).scalars().all())
    if department_id:
        rows = [r for r in rows if (r.dimensions or {}).get("department_id") == department_id]
    return rows


def view_snapshot(row: MetricSnapshot) -> dict[str, Any]:
    return {
        "id": row.id,
        "tenant_id": row.organisation_id,
        "source_module": row.source_module,
        "metric_key": row.metric_key,
        "period_start": row.period_start.isoformat(),
        "period_end": row.period_end.isoformat(),
        "dimensions": row.dimensions or {},
        "value": float(row.value),
        "unit": row.unit,
        "calculated_at": row.calculated_at.isoformat() if row.calculated_at else None,
        "schema_version": row.schema_version,
    }


def _compute_report_data(db: Session, organisation_id: str, code: str, params: dict) -> dict[str, Any]:
    """A report from the ingested MetricSnapshot data (application/ingest.py) for the month in `period`. A report
    whose source module publishes nothing yet says so (available: false), rather than reporting zeros as data."""
    dept_id = params.get("department_id")
    period = params.get("period") or utcnow().strftime("%Y-%m")
    if code in REPORT_UNAVAILABLE:
        reason = metrics.UNAVAILABLE[REPORT_UNAVAILABLE[code]]
        return {"title": f"Report: {code}", "period": period, "available": False, "reason": reason, "items": []}
    start, end = _period_bounds(period)
    if code == "faculty-workload":
        # Contact hours currently assigned: every assignment and release up to the end of the period
        rows = metric_rows(db, organisation_id, "academics.faculty_contact_hours", date(1970, 1, 1), end, dept_id)
        by_department: dict[str, float] = {}
        for r in rows:
            d = (r.dimensions or {}).get("department_id", ingest.UNKNOWN)
            by_department[d] = by_department.get(d, 0.0) + float(r.value)
        items = [{"department_id": d, "contact_hours": round(h, 2)} for d, h in sorted(by_department.items())]
        return {
            "title": "Faculty Workload Analysis",
            "period": period,
            "available": True,
            "unit": "hours",
            "items": items,
        }
    keys = REPORT_METRICS.get(code) or ((code,) if code in metrics.BY_KEY else ())
    items = [view_snapshot(r) for key in keys for r in metric_rows(db, organisation_id, key, start, end, dept_id)]
    totals: dict[str, float] = {}
    for item in items:
        totals[item["metric_key"]] = round(totals.get(item["metric_key"], 0.0) + item["value"], 4)
    return {"title": f"Report: {code}", "period": period, "available": True, "totals": totals, "items": items}


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
        db.flush()  # direct_upload only adds the row; get_download_url selects it
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


def _sanitize_csv_cell(val: Any) -> Any:
    """Guard against CSV formula injection (=, +, -, @, tab, CR)."""
    if isinstance(val, str) and val.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{val}"
    return val


def _generate_csv(summary: dict[str, Any]) -> bytes:
    """Format report summary items into standard tabular CSV bytes with formula injection protection."""
    output = io.StringIO()
    items = summary.get("items")
    if items and isinstance(items, list) and isinstance(items[0], dict):
        fieldnames = [_sanitize_csv_cell(k) for k in items[0].keys()]
        writer = csv.writer(output)
        writer.writerow(fieldnames)
        for item in items:
            writer.writerow([_sanitize_csv_cell(v) for v in item.values()])
    else:
        # Fallback to key-value rows
        writer = csv.writer(output)
        writer.writerow(["Metric", "Value"])
        for k, v in summary.items():
            if k != "items":
                writer.writerow([_sanitize_csv_cell(k), _sanitize_csv_cell(str(v))])
    return output.getvalue().encode("utf-8")


def get_execution_export_content(execution: ReportExecution, export_format: str) -> tuple[str, bytes, str]:
    """Return (filename, content_bytes, media_type) for direct download of an execution."""
    fmt = export_format.lower().strip()
    if fmt not in ("csv", "json"):
        raise ReportingError(f"Unsupported export format '{export_format}'. Must be 'csv' or 'json'", status=400)
    filename = f"report_{execution.id[:8]}.{fmt}"
    if fmt == "csv":
        content = _generate_csv(execution.result_summary or {})
        media_type = "text/csv"
    else:
        content = json.dumps(execution.result_summary or {}, indent=2).encode("utf-8")
        media_type = "application/json"
    return filename, content, media_type


def get_department_reports_widget_data(
    db: Session, organisation_id: str, department_id: str | None = None, include_financial: bool = False
) -> dict[str, Any]:
    """Retrieve operational metrics for department-admin widget from real MetricSnapshot data (read-only).
    Financial runs are listed only when include_financial (the caller holds reporting:report:execute)."""
    dept_id = department_id or ""

    # Real recent executions, with their definition's code and name
    stmt = (
        select(ReportExecution, ReportDefinition)
        .join(ReportDefinition, ReportDefinition.id == ReportExecution.report_definition_id)
        .where(ReportExecution.organisation_id == organisation_id, ReportDefinition.organisation_id == organisation_id)
    )
    if not include_financial:
        stmt = stmt.where(ReportDefinition.category != FINANCIAL)
    recent_runs = db.execute(stmt.order_by(ReportExecution.executed_at.desc()).limit(5)).all()
    recent_reports = [
        {
            "id": run.id,
            "code": definition.code,
            "title": definition.name,
            "generated_at": run.executed_at.isoformat(),
        }
        for run, definition in recent_runs
    ]

    # Faculty contact hours from the ingested academics metric; attendance and pass rates have no source yet
    _, end = ingest.month_of(utcnow())
    hours = sum(
        float(r.value)
        for r in metric_rows(
            db, organisation_id, "academics.faculty_contact_hours", date(1970, 1, 1), end, dept_id or None
        )
    )
    return {
        "department_id": dept_id,
        "department_name": f"Department {dept_id}" if dept_id else "All departments",
        "attendance_rate": 0.0,
        "exam_pass_rate": 0.0,
        "faculty_load_average": 0.0,
        "faculty_contact_hours": round(hours, 2),
        "recent_reports": recent_reports,
        "unavailable": sorted(metrics.UNAVAILABLE),
    }


def get_attendance_and_results_widget_data(db: Session, organisation_id: str) -> dict[str, Any]:
    """Cross-department attendance and results for management. Neither has a source yet (metrics.UNAVAILABLE):
    the widget gets an empty comparison and says why, instead of zeros presented as institution averages."""
    return {
        "institution_average_attendance": 0.0,
        "institution_average_pass_rate": 0.0,
        "departments": [],
        "unavailable": sorted(metrics.UNAVAILABLE),
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
