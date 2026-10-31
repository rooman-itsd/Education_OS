"""FastAPI router for reporting: definitions, execution, export, and widgets."""

from __future__ import annotations

from typing import Any

from eos_core.db import get_db
from eos_identity.api.deps import Principal, require
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..application import service
from ..application.service import ReportingError

router = APIRouter(tags=["reporting"])

REPORT_READ = "reporting:report:read"
REPORT_EXECUTE = "reporting:report:execute"
REPORT_MANAGE = "reporting:report:manage"


class CreateDefinitionInput(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=1000)
    parameters_schema: dict[str, Any] | None = None


class UpdateDefinitionInput(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    category: str | None = Field(default=None, max_length=64)
    parameters_schema: dict[str, Any] | None = None
    is_active: bool | None = None


class RunReportInput(BaseModel):
    parameters: dict[str, Any] | None = None
    client_token: str | None = Field(default=None, max_length=120)


def _err(e: ReportingError) -> HTTPException:
    return HTTPException(status_code=e.status, detail={"code": "reporting_error", "message": e.message})


@router.get("/definitions")
def list_definitions(
    category: str | None = None,
    is_active: bool | None = None,
    p: Principal = Depends(require(REPORT_READ)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, detail={"code": "bad_request", "message": "organisation_id required"})
    defs = service.list_definitions(db, p.organisation_id, category=category, is_active=is_active)
    db.commit()
    return [service.view_definition(d) for d in defs]


@router.post("/definitions", status_code=201)
def create_definition(
    body: CreateDefinitionInput,
    p: Principal = Depends(require(REPORT_MANAGE)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, detail={"code": "bad_request", "message": "organisation_id required"})
    try:
        defn = service.create_definition(
            db,
            p.organisation_id,
            code=body.code,
            name=body.name,
            category=body.category,
            description=body.description,
            parameters_schema=body.parameters_schema,
        )
        db.commit()
        return service.view_definition(defn)
    except ReportingError as e:
        db.rollback()
        raise _err(e) from e


@router.get("/definitions/{id}")
def get_definition(
    id: str,
    p: Principal = Depends(require(REPORT_READ)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, detail={"code": "bad_request", "message": "organisation_id required"})
    defn = service.get_definition(db, p.organisation_id, id)
    if not defn:
        raise HTTPException(404, detail={"code": "not_found", "message": f"Report definition '{id}' not found"})
    return service.view_definition(defn)


@router.put("/definitions/{id}")
def update_definition(
    id: str,
    body: UpdateDefinitionInput,
    p: Principal = Depends(require(REPORT_MANAGE)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, detail={"code": "bad_request", "message": "organisation_id required"})
    try:
        defn = service.update_definition(
            db,
            p.organisation_id,
            definition_id=id,
            name=body.name,
            description=body.description,
            category=body.category,
            parameters_schema=body.parameters_schema,
            is_active=body.is_active,
        )
        db.commit()
        return service.view_definition(defn)
    except ReportingError as e:
        db.rollback()
        raise _err(e) from e


@router.post("/definitions/{id}/run")
def run_report(
    id: str,
    body: RunReportInput | None = None,
    p: Principal = Depends(require(REPORT_EXECUTE)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, detail={"code": "bad_request", "message": "organisation_id required"})

    params = (body.parameters if body else None) or {}
    client_token = body.client_token if body else None

    try:
        execution, is_new = service.run_report(
            db,
            p.organisation_id,
            requested_by=p.user_id,
            definition_id=id,
            parameters=params,
            client_token=client_token,
        )
        db.commit()
        return JSONResponse(service.view_execution(execution), status_code=201 if is_new else 200)
    except ReportingError as e:
        db.rollback()
        raise _err(e) from e
    except IntegrityError:
        db.rollback()
        existing = service.find_execution_by_token(db, p.organisation_id, client_token)
        if existing:
            return JSONResponse(service.view_execution(existing), status_code=200)
        raise


@router.get("/executions/{id}")
def get_execution(
    id: str,
    p: Principal = Depends(require(REPORT_READ)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, detail={"code": "bad_request", "message": "organisation_id required"})
    execution = service.get_execution(db, p.organisation_id, id)
    if not execution:
        raise HTTPException(404, detail={"code": "not_found", "message": f"Execution '{id}' not found"})
    return service.view_execution(execution)


@router.get("/executions/{id}/export")
def export_report(
    id: str,
    format: str = Query("csv", pattern="^(csv|json)$"),
    p: Principal = Depends(require(REPORT_EXECUTE)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, detail={"code": "bad_request", "message": "organisation_id required"})
    try:
        res = service.export_report(
            db,
            p.organisation_id,
            actor_id=p.user_id,
            execution_id=id,
            export_format=format,
        )
        db.commit()
        return res
    except ReportingError as e:
        db.rollback()
        raise _err(e) from e


@router.get("/widgets/department-reports")
def get_department_reports_widget(
    department_id: str | None = None,
    p: Principal = Depends(require(REPORT_READ)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, detail={"code": "bad_request", "message": "organisation_id required"})
    return service.get_department_reports_widget_data(db, p.organisation_id, department_id=department_id)


@router.get("/widgets/attendance-and-results")
def get_attendance_and_results_widget(
    p: Principal = Depends(require(REPORT_READ)),
    db: Session = Depends(get_db),
):
    if not p.organisation_id:
        raise HTTPException(400, detail={"code": "bad_request", "message": "organisation_id required"})
    return service.get_attendance_and_results_widget_data(db, p.organisation_id)
