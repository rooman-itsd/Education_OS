"""HTTP surface of tournament-events, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/tournament-events. Handlers only map HTTP to the use cases in application/service.py."""

from __future__ import annotations

from datetime import date

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, ServiceError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["tournament-events"])

LIMIT = Query(50, ge=1, le=200)
OFFSET = Query(0, ge=0)
FROM = Query(None, alias="from")
TO = Query(None, alias="to")
# The calendar is not paged (contracts/openapi.yaml), so its period is bounded instead.
CALENDAR_MAX_DAYS = 366


def _run(fn, *args):
    try:
        return fn(*args)
    except ServiceError as e:
        raise HTTPException(e.status, e.body()) from e


def _period(start: date | None, end: date | None) -> None:
    if start and end and start > end:
        raise HTTPException(400, {"code": "invalid_period", "message": "from must not be after to"})


# ---------------------------------------------------------------- tournaments


@router.get("/tournaments")
def list_tournaments(
    status: s.TournamentStatus | None = None,
    level: s.Level | None = None,
    start: date | None = FROM,
    end: date | None = TO,
    limit: int = LIMIT,
    offset: int = OFFSET,
    a: Actor = Depends(require(svc.TOURNAMENT_READ)),
    db: Session = Depends(get_db),
):
    _period(start, end)
    filters = {"status": status, "level": level, "from": start, "to": end}
    return svc.list_tournaments(db, a, filters, limit, offset)


@router.post("/tournaments", status_code=201)
def create_tournament(
    body: s.TournamentIn, a: Actor = Depends(require(svc.TOURNAMENT_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.create_tournament, db, a, s.dump(body))


@router.get("/tournaments/{tournament_id}")
def get_tournament(tournament_id: str, a: Actor = Depends(require(svc.TOURNAMENT_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_tournament, db, a, tournament_id)


@router.patch("/tournaments/{tournament_id}")
def update_tournament(
    tournament_id: str,
    body: s.TournamentPatch,
    a: Actor = Depends(require(svc.TOURNAMENT_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_tournament, db, a, tournament_id, s.dump(body, partial=True))


@router.post("/tournaments/{tournament_id}/publish")
def publish_tournament(
    tournament_id: str, a: Actor = Depends(require(svc.TOURNAMENT_PUBLISH)), db: Session = Depends(get_db)
):
    return _run(svc.publish_tournament, db, a, tournament_id)


@router.post("/tournaments/{tournament_id}/cancel")
def cancel_tournament(
    tournament_id: str,
    body: s.CancelIn,
    a: Actor = Depends(require(svc.TOURNAMENT_PUBLISH)),
    db: Session = Depends(get_db),
):
    return _run(svc.cancel_tournament, db, a, tournament_id, body.reason)


# ---------------------------------------------------------------- entries


@router.get("/tournaments/{tournament_id}/entries")
def list_entries(
    tournament_id: str,
    status: s.EntryStatus | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    a: Actor = Depends(require(svc.ENTRY_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_entries, db, a, tournament_id, status, limit, offset)


@router.post("/tournaments/{tournament_id}/entries", status_code=201)
def create_entry(
    tournament_id: str, body: s.EntryIn, a: Actor = Depends(require(svc.ENTRY_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.create_entry, db, a, tournament_id, s.dump(body))


@router.patch("/tournaments/{tournament_id}/entries/{entry_id}")
def update_entry(
    tournament_id: str,
    entry_id: str,
    body: s.EntryPatch,
    a: Actor = Depends(require(svc.ENTRY_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_entry, db, a, tournament_id, entry_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- fixtures


@router.get("/tournaments/{tournament_id}/fixtures")
def list_fixtures(
    tournament_id: str,
    status: s.FixtureStatus | None = None,
    start: date | None = FROM,
    end: date | None = TO,
    limit: int = LIMIT,
    offset: int = OFFSET,
    a: Actor = Depends(require(svc.FIXTURE_READ)),
    db: Session = Depends(get_db),
):
    _period(start, end)
    filters = {"status": status, "from": start, "to": end}
    return _run(svc.list_fixtures, db, a, tournament_id, filters, limit, offset)


@router.post("/tournaments/{tournament_id}/fixtures", status_code=201)
def schedule_fixture(
    tournament_id: str,
    body: s.FixtureIn,
    a: Actor = Depends(require(svc.FIXTURE_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.schedule_fixture, db, a, tournament_id, s.dump(body))


@router.get("/tournaments/{tournament_id}/fixtures/{fixture_id}")
def get_fixture(
    tournament_id: str, fixture_id: str, a: Actor = Depends(require(svc.FIXTURE_READ)), db: Session = Depends(get_db)
):
    return _run(svc.get_fixture, db, a, tournament_id, fixture_id)


@router.patch("/tournaments/{tournament_id}/fixtures/{fixture_id}")
def update_fixture(
    tournament_id: str,
    fixture_id: str,
    body: s.FixturePatch,
    a: Actor = Depends(require(svc.FIXTURE_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_fixture, db, a, tournament_id, fixture_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- results


@router.get("/tournaments/{tournament_id}/fixtures/{fixture_id}/result")
def get_result(
    tournament_id: str, fixture_id: str, a: Actor = Depends(require(svc.RESULT_READ)), db: Session = Depends(get_db)
):
    return _run(svc.get_result, db, a, tournament_id, fixture_id)


@router.put("/tournaments/{tournament_id}/fixtures/{fixture_id}/result")
def record_result(
    tournament_id: str,
    fixture_id: str,
    body: s.ResultIn,
    a: Actor = Depends(require(svc.RESULT_RECORD)),
    db: Session = Depends(get_db),
):
    return _run(svc.record_result, db, a, tournament_id, fixture_id, s.dump(body))


# ---------------------------------------------------------------- officials


@router.get("/tournaments/{tournament_id}/officials")
def list_officials(
    tournament_id: str,
    limit: int = LIMIT,
    offset: int = OFFSET,
    a: Actor = Depends(require(svc.OFFICIAL_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_officials, db, a, tournament_id, limit, offset)


@router.post("/tournaments/{tournament_id}/officials", status_code=201)
def assign_official(
    tournament_id: str,
    body: s.OfficialIn,
    a: Actor = Depends(require(svc.OFFICIAL_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.assign_official, db, a, tournament_id, s.dump(body))


@router.delete("/tournaments/{tournament_id}/officials/{official_id}", status_code=204)
def delete_official(
    tournament_id: str,
    official_id: str,
    a: Actor = Depends(require(svc.OFFICIAL_WRITE)),
    db: Session = Depends(get_db),
):
    _run(svc.remove_official, db, a, tournament_id, official_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- logistics


@router.get("/tournaments/{tournament_id}/logistics")
def get_logistics(tournament_id: str, a: Actor = Depends(require(svc.LOGISTICS_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_logistics, db, a, tournament_id)


@router.put("/tournaments/{tournament_id}/logistics")
def set_logistics(
    tournament_id: str,
    body: s.LogisticsIn,
    a: Actor = Depends(require(svc.LOGISTICS_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.set_logistics, db, a, tournament_id, s.dump(body))


# ---------------------------------------------------------------- calendar


@router.get("/calendar")
def get_calendar(
    start: date = Query(alias="from"),
    end: date = Query(alias="to"),
    _: Actor = Depends(require(svc.TOURNAMENT_READ)),
    db: Session = Depends(get_db),
):
    _period(start, end)
    if (end - start).days > CALENDAR_MAX_DAYS:
        raise HTTPException(
            400, {"code": "period_too_long", "message": f"the calendar covers at most {CALENDAR_MAX_DAYS} days"}
        )
    return svc.calendar(db, start, end)
