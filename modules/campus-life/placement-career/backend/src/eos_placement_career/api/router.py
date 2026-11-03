"""HTTP surface of contracts/openapi.yaml. The host app mounts `router` under /api/v1/placement-career. Handlers only
map HTTP to the application layer; errors render as {"detail": {"code", "message", "field"?}}."""

from __future__ import annotations

from datetime import date

from eos_core.db import get_db
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..application import access as p
from ..application import applications, companies, drives, openings, reports
from ..application.access import Actor
from ..application.errors import PlacementError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["placement-career"])

DRIVE_STATUS = "^(draft|scheduled|completed|cancelled)$"
OPENING_STATUS = "^(draft|open|closed|cancelled)$"
APPLICATION_STATUS = "^(applied|shortlisted|in_process|offered|accepted|declined|rejected|withdrawn)$"


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except PlacementError as e:
        raise HTTPException(e.status, e.body()) from e


Limit = Query(default=50, ge=1, le=200)
Reason = Body(default=None)


def _reason(body: s.ReasonInput | None) -> str | None:
    return body.reason if body else None


# ---------------------------------------------------------------- companies


@router.get("/companies")
def list_companies(
    active: bool | None = None,
    q: str | None = Query(default=None, max_length=200),
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.COMPANY_READ)),
    db: Session = Depends(get_db),
):
    return _run(companies.list_companies, db, a, active, q, cursor, limit)


@router.post("/companies", status_code=201)
def create_company(body: s.CompanyInput, a: Actor = Depends(require(p.COMPANY_MANAGE)), db: Session = Depends(get_db)):
    return _run(companies.create_company, db, a, s.dump(body))


@router.get("/companies/{company_id}")
def get_company(company_id: str, a: Actor = Depends(require(p.COMPANY_READ)), db: Session = Depends(get_db)):
    return _run(companies.get_company, db, a, company_id)


@router.put("/companies/{company_id}")
def update_company(
    company_id: str,
    body: s.CompanyInput,
    a: Actor = Depends(require(p.COMPANY_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(companies.update_company, db, a, company_id, s.dump(body))


# ---------------------------------------------------------------- drives


@router.get("/drives")
def list_drives(
    status: str | None = Query(default=None, pattern=DRIVE_STATUS),
    company_id: str | None = None,
    day_from: date | None = Query(default=None, alias="from"),
    day_to: date | None = Query(default=None, alias="to"),
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.OPENING_READ)),
    db: Session = Depends(get_db),
):
    return _run(drives.list_drives, db, a, status, company_id, day_from, day_to, cursor, limit)


@router.post("/drives", status_code=201)
def create_drive(body: s.DriveInput, a: Actor = Depends(require(p.DRIVE_MANAGE)), db: Session = Depends(get_db)):
    return _run(drives.create_drive, db, a, s.dump(body))


@router.get("/drives/{drive_id}")
def get_drive(drive_id: str, a: Actor = Depends(require(p.OPENING_READ)), db: Session = Depends(get_db)):
    return _run(drives.get_drive, db, a, drive_id)


@router.put("/drives/{drive_id}")
def update_drive(
    drive_id: str, body: s.DriveInput, a: Actor = Depends(require(p.DRIVE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(drives.update_drive, db, a, drive_id, s.dump(body))


@router.post("/drives/{drive_id}/schedule")
def schedule_drive(drive_id: str, a: Actor = Depends(require(p.DRIVE_MANAGE)), db: Session = Depends(get_db)):
    return _run(drives.schedule_drive, db, a, drive_id)


@router.post("/drives/{drive_id}/complete")
def complete_drive(drive_id: str, a: Actor = Depends(require(p.DRIVE_MANAGE)), db: Session = Depends(get_db)):
    return _run(drives.complete_drive, db, a, drive_id)


@router.post("/drives/{drive_id}/cancel")
def cancel_drive(
    drive_id: str,
    body: s.ReasonInput | None = Reason,
    a: Actor = Depends(require(p.DRIVE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(drives.cancel_drive, db, a, drive_id, _reason(body))


# ---------------------------------------------------------------- openings


@router.get("/openings")
def list_openings(
    status: str | None = Query(default=None, pattern=OPENING_STATUS),
    drive_id: str | None = None,
    company_id: str | None = None,
    without_drive: bool | None = None,
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.OPENING_READ)),
    db: Session = Depends(get_db),
):
    filters = {"status": status, "drive_id": drive_id, "company_id": company_id, "without_drive": without_drive}
    return _run(openings.list_openings, db, a, filters, cursor, limit)


@router.post("/openings", status_code=201)
def create_opening(body: s.OpeningInput, a: Actor = Depends(require(p.OPENING_MANAGE)), db: Session = Depends(get_db)):
    return _run(openings.create_opening, db, a, s.dump(body))


@router.get("/openings/{opening_id}")
def get_opening(opening_id: str, a: Actor = Depends(require(p.OPENING_READ)), db: Session = Depends(get_db)):
    return _run(openings.get_opening, db, a, opening_id)


@router.put("/openings/{opening_id}")
def update_opening(
    opening_id: str,
    body: s.OpeningInput,
    a: Actor = Depends(require(p.OPENING_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(openings.update_opening, db, a, opening_id, s.dump(body))


@router.post("/openings/{opening_id}/publish")
def publish_opening(opening_id: str, a: Actor = Depends(require(p.OPENING_MANAGE)), db: Session = Depends(get_db)):
    return _run(openings.publish_opening, db, a, opening_id)


@router.post("/openings/{opening_id}/close")
def close_opening(opening_id: str, a: Actor = Depends(require(p.OPENING_MANAGE)), db: Session = Depends(get_db)):
    return _run(openings.close_opening, db, a, opening_id)


@router.post("/openings/{opening_id}/cancel")
def cancel_opening(
    opening_id: str,
    body: s.ReasonInput | None = Reason,
    a: Actor = Depends(require(p.OPENING_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(openings.cancel_opening, db, a, opening_id, _reason(body))


# ---------------------------------------------------------------- applications (the officer)


@router.get("/applications")
def list_applications(
    opening_id: str | None = None,
    drive_id: str | None = None,
    status: str | None = Query(default=None, pattern=APPLICATION_STATUS),
    student_id: str | None = None,
    student_placed: bool | None = None,
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.APPLICATION_READ)),
    db: Session = Depends(get_db),
):
    filters = {
        "opening_id": opening_id,
        "drive_id": drive_id,
        "status": status,
        "student_id": student_id,
        "student_placed": student_placed,
    }
    return _run(applications.list_applications, db, filters, cursor, limit)


@router.get("/applications/{application_id}")
def get_application(
    application_id: str, a: Actor = Depends(require(p.APPLICATION_READ)), db: Session = Depends(get_db)
):
    return _run(applications.get_application, db, application_id)


@router.post("/applications/{application_id}/status")
def change_status(
    application_id: str,
    body: s.StatusChange,
    a: Actor = Depends(require(p.APPLICATION_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(applications.change_status, db, a, application_id, s.dump(body))


# ---------------------------------------------------------------- the student's own


@router.get("/me/openings")
def my_openings(
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.SELF_READ)),
    db: Session = Depends(get_db),
):
    return _run(applications.my_openings, db, a, cursor, limit)


@router.get("/me/applications")
def my_applications(
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.SELF_READ)),
    db: Session = Depends(get_db),
):
    return _run(applications.my_applications, db, a, cursor, limit)


@router.post("/me/applications", status_code=201)
def apply(body: s.ApplicationInput, a: Actor = Depends(require(p.SELF_APPLY)), db: Session = Depends(get_db)):
    return _run(applications.apply, db, a, s.dump(body))


@router.post("/me/applications/{application_id}/withdraw")
def withdraw(application_id: str, a: Actor = Depends(require(p.SELF_APPLY)), db: Session = Depends(get_db)):
    return _run(applications.withdraw, db, a, application_id)


# ---------------------------------------------------------------- reports


@router.get("/reports/drives-upcoming")
def drives_upcoming(
    limit: int = Query(default=10, ge=1, le=50),
    a: Actor = Depends(require(p.REPORT_READ)),
    db: Session = Depends(get_db),
):
    return _run(reports.drives_upcoming, db, limit)


@router.get("/reports/openings-summary")
def openings_summary(
    limit: int = Query(default=5, ge=1, le=50),
    a: Actor = Depends(require(p.REPORT_READ)),
    db: Session = Depends(get_db),
):
    return _run(reports.openings_summary, db, limit)
