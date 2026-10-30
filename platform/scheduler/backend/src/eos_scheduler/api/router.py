"""HTTP surface of scheduler, following contracts/openapi.yaml. Job definitions are read-only here: they are
declared in code by the module that handles them."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Literal

from eos_core.db import get_db
from eos_core.tenant import platform_scope
from eos_identity.api.deps import Principal, require
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..application import jobs as jobs_module
from ..application import schedules
from ..infrastructure.config import SchedulerConfig

router = APIRouter(tags=["scheduler"])

ADMIN = "platform:scheduler:admin"


class NewScheduleIn(BaseModel):
    job: str = Field(max_length=120)
    cron: str | None = Field(None, max_length=120)
    timezone: str | None = Field(None, max_length=64)
    run_at: datetime | None = None
    arguments: dict = Field(default_factory=dict)
    enabled: bool = True
    allow_overlap: bool = False
    catch_up: Literal["once", "never"] | None = None
    organisation_id: str | None = Field(None, max_length=36, description="Super admin only, for organisation jobs")


class ScheduleChangeIn(BaseModel):
    cron: str | None = Field(None, max_length=120)
    timezone: str | None = Field(None, max_length=64)
    run_at: datetime | None = None
    arguments: dict | None = None
    enabled: bool | None = None
    allow_overlap: bool | None = None
    catch_up: Literal["once", "never"] | None = None


@contextmanager
def _http_errors() -> Iterator[None]:
    try:
        yield
    except schedules.SchedulerError as e:
        raise HTTPException(e.status, e.detail) from e


@contextmanager
def _scope(p: Principal) -> Iterator[schedules.Scope]:
    """The super admin works in platform scope (every organisation and platform jobs); anyone else in their own."""
    if p.super_admin and p.can(ADMIN):
        with platform_scope():
            yield schedules.Scope(None, platform=True)
        return
    if not p.organisation_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this endpoint needs an organisation user")
    yield schedules.Scope(p.organisation_id)


@router.get("/jobs")
def list_jobs(
    module: str | None = None,
    scope: Literal["platform", "organisation"] | None = None,
    p: Principal = Depends(require("scheduler:job:read")),
):
    found = [j for j in jobs_module.discover().values() if (not module or j.module == module)]
    found = [j for j in found if not scope or j.scope == scope]
    return {"items": [j.out() for j in sorted(found, key=lambda j: j.key)]}


@router.get("/schedules")
def list_schedules(
    job: str | None = None,
    organisation_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    p: Principal = Depends(require("scheduler:schedule:read")),
    db: Session = Depends(get_db),
):
    with _scope(p) as scope:
        rows, total = schedules.list_schedules(
            db, scope, job=job, organisation_id=organisation_id, limit=limit, offset=offset
        )
        return {"items": [schedules.schedule_out(s) for s in rows], "total": total}


@router.post("/schedules", status_code=201)
def create_schedule(
    body: NewScheduleIn, p: Principal = Depends(require("scheduler:schedule:write")), db: Session = Depends(get_db)
):
    with _scope(p) as scope, _http_errors():
        made = schedules.create(
            db, jobs_module.discover(), scope, SchedulerConfig.from_env(), body.model_dump(), actor=p.user_id
        )
        return schedules.schedule_out(made)


@router.get("/schedules/{schedule_id}")
def get_schedule(
    schedule_id: str, p: Principal = Depends(require("scheduler:schedule:read")), db: Session = Depends(get_db)
):
    with _scope(p) as scope, _http_errors():
        return schedules.schedule_out(schedules.get(db, scope, schedule_id))


@router.patch("/schedules/{schedule_id}")
def change_schedule(
    schedule_id: str,
    body: ScheduleChangeIn,
    p: Principal = Depends(require("scheduler:schedule:write")),
    db: Session = Depends(get_db),
):
    with _scope(p) as scope, _http_errors():
        changed = schedules.change(db, scope, schedule_id, body.model_dump(exclude_unset=True), actor=p.user_id)
        return schedules.schedule_out(changed)


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: str, p: Principal = Depends(require("scheduler:schedule:write")), db: Session = Depends(get_db)
):
    with _scope(p) as scope, _http_errors():
        schedules.remove(db, scope, schedule_id, actor=p.user_id)
    return Response(status_code=204)


@router.post("/schedules/{schedule_id}/run", status_code=202)
def run_schedule_now(
    schedule_id: str, p: Principal = Depends(require("scheduler:run:trigger")), db: Session = Depends(get_db)
):
    with _scope(p) as scope, _http_errors():
        run = schedules.run_now(db, jobs_module.discover(), scope, schedule_id, actor=p.user_id)
        return schedules.run_out(run)


@router.get("/runs")
def list_runs(
    schedule_id: str | None = None,
    job: str | None = None,
    status_: Literal["running", "succeeded", "failed", "skipped"] | None = Query(None, alias="status"),
    organisation_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    p: Principal = Depends(require("scheduler:run:read")),
    db: Session = Depends(get_db),
):
    with _scope(p) as scope:
        rows, total = schedules.list_runs(
            db,
            scope,
            schedule_id=schedule_id,
            job=job,
            status=status_,
            organisation_id=organisation_id,
            limit=limit,
            offset=offset,
        )
        return {"items": [schedules.run_out(r) for r in rows], "total": total}


@router.get("/runs/{run_id}")
def get_run(run_id: str, p: Principal = Depends(require("scheduler:run:read")), db: Session = Depends(get_db)):
    with _scope(p) as scope, _http_errors():
        return schedules.run_out(schedules.get_run(db, scope, run_id))
