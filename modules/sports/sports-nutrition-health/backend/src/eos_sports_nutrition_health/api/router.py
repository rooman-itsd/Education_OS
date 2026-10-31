"""HTTP surface of sports-nutrition-health, as described in contracts/openapi.yaml. The host app mounts `router`
under /api/v1/sports-nutrition-health. Handlers only map HTTP to the use cases in application/service.py."""

from __future__ import annotations

from datetime import date

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, ServiceError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["sports-nutrition-health"])

LIMIT = Query(50, ge=1, le=200)
OFFSET = Query(0, ge=0)


def _run(fn, *args):
    try:
        return fn(*args)
    except ServiceError as e:
        raise HTTPException(e.status, e.body()) from e


# ---------------------------------------------------------------- nutrition plans


@router.get("/nutrition-plans")
def list_nutrition_plans(
    athlete_id: str | None = None,
    status: s.PlanStatus | None = None,
    review_due_before: date | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    a: Actor = Depends(require(svc.PLAN_READ)),
    db: Session = Depends(get_db),
):
    filters = {"athlete_id": athlete_id, "status": status, "review_due_before": review_due_before}
    return svc.list_plans(db, a, filters, limit, offset)


@router.post("/nutrition-plans", status_code=201)
def create_nutrition_plan(body: s.PlanIn, a: Actor = Depends(require(svc.PLAN_WRITE)), db: Session = Depends(get_db)):
    return _run(svc.create_plan, db, a, s.dump(body))


@router.get("/nutrition-plans/{plan_id}")
def get_nutrition_plan(plan_id: str, a: Actor = Depends(require(svc.PLAN_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_plan, db, a, plan_id)


@router.patch("/nutrition-plans/{plan_id}")
def update_nutrition_plan(
    plan_id: str, body: s.PlanPatch, a: Actor = Depends(require(svc.PLAN_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.update_plan, db, a, plan_id, s.dump(body, partial=True))


@router.get("/nutrition-plans/{plan_id}/reviews")
def list_plan_reviews(
    plan_id: str,
    limit: int = LIMIT,
    offset: int = OFFSET,
    a: Actor = Depends(require(svc.PLAN_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_reviews, db, a, plan_id, limit, offset)


@router.post("/nutrition-plans/{plan_id}/reviews", status_code=201)
def record_plan_review(
    plan_id: str, body: s.ReviewIn, a: Actor = Depends(require(svc.PLAN_REVIEW)), db: Session = Depends(get_db)
):
    return _run(svc.record_review, db, a, plan_id, s.dump(body))


# ---------------------------------------------------------------- health records


@router.get("/health-records")
def list_health_records(
    athlete_id: str | None = None,
    record_type: s.RecordType | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    a: Actor = Depends(require(svc.HEALTH_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_health_records(db, a, {"athlete_id": athlete_id, "record_type": record_type}, limit, offset)


@router.post("/health-records", status_code=201)
def create_health_record(
    body: s.HealthRecordIn, a: Actor = Depends(require(svc.HEALTH_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.create_health_record, db, a, s.dump(body))


@router.get("/health-records/{record_id}")
def get_health_record(record_id: str, a: Actor = Depends(require(svc.HEALTH_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_health_record, db, a, record_id)


@router.patch("/health-records/{record_id}")
def update_health_record(
    record_id: str,
    body: s.HealthRecordPatch,
    a: Actor = Depends(require(svc.HEALTH_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_health_record, db, a, record_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- injuries


@router.get("/injuries")
def list_injurys(
    athlete_id: str | None = None,
    status: s.InjuryStatus | None = None,
    severity: s.Severity | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    a: Actor = Depends(require(svc.INJURY_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_injuries(db, a, {"athlete_id": athlete_id, "status": status, "severity": severity}, limit, offset)


@router.post("/injuries", status_code=201)
def report_injury(body: s.InjuryIn, a: Actor = Depends(require(svc.INJURY_WRITE)), db: Session = Depends(get_db)):
    return _run(svc.report_injury, db, a, s.dump(body))


@router.get("/injuries/{injury_id}")
def get_injury(injury_id: str, a: Actor = Depends(require(svc.INJURY_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_injury, db, a, injury_id)


@router.patch("/injuries/{injury_id}")
def update_injury(
    injury_id: str, body: s.InjuryPatch, a: Actor = Depends(require(svc.INJURY_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.update_injury, db, a, injury_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- appointments


@router.get("/appointments")
def list_appointments(
    athlete_id: str | None = None,
    practitioner_id: str | None = None,
    on: date | None = Query(None, description="Appointments scheduled on this day (UTC)"),
    status: s.AppointmentStatus | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    a: Actor = Depends(require(svc.APPOINTMENT_READ)),
    db: Session = Depends(get_db),
):
    filters = {"athlete_id": athlete_id, "practitioner_id": practitioner_id, "on": on, "status": status}
    return svc.list_appointments(db, a, filters, limit, offset)


@router.post("/appointments", status_code=201)
def schedule_appointment(
    body: s.AppointmentIn, a: Actor = Depends(require(svc.APPOINTMENT_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.schedule_appointment, db, a, s.dump(body))


@router.get("/appointments/{appointment_id}")
def get_appointment(
    appointment_id: str, a: Actor = Depends(require(svc.APPOINTMENT_READ)), db: Session = Depends(get_db)
):
    return _run(svc.get_appointment, db, a, appointment_id)


@router.patch("/appointments/{appointment_id}")
def update_appointment(
    appointment_id: str,
    body: s.AppointmentPatch,
    a: Actor = Depends(require(svc.APPOINTMENT_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_appointment, db, a, appointment_id, s.dump(body, partial=True))
