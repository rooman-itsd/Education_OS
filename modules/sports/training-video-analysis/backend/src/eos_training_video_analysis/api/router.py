"""HTTP surface of training-video-analysis, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/training-video-analysis. Handlers only map HTTP to the use cases in application/service.py."""

from __future__ import annotations

from datetime import date

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, ServiceError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["training-video-analysis"])

LIMIT = Query(50, ge=1, le=200)
OFFSET = Query(0, ge=0)


def _id():
    """An optional UUID filter; a fresh Query per parameter (FastAPI binds a Query object to one parameter)."""
    return Query(None, pattern=s.UUID_PATTERN)


def _run(fn, *args):
    try:
        return fn(*args)
    except ServiceError as e:
        raise HTTPException(e.status, e.body()) from e


# ---------------------------------------------------------------- plans


@router.get("/plans")
def list_training_plans(
    coach_id: str | None = _id(),
    status: s.PlanStatus | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    a: Actor = Depends(require(svc.PLAN_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_plans(db, a, {"coach_id": coach_id, "status": status}, limit, offset)


@router.post("/plans", status_code=201)
def create_training_plan(body: s.PlanIn, a: Actor = Depends(require(svc.PLAN_WRITE)), db: Session = Depends(get_db)):
    return _run(svc.create_plan, db, a, s.dump(body))


@router.get("/plans/{plan_id}")
def get_training_plan(plan_id: str, a: Actor = Depends(require(svc.PLAN_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_plan, db, a, plan_id)


@router.patch("/plans/{plan_id}")
def update_training_plan(
    plan_id: str, body: s.PlanPatch, a: Actor = Depends(require(svc.PLAN_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.update_plan, db, a, plan_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- sessions


@router.get("/sessions")
def list_training_sessions(
    plan_id: str | None = _id(),
    coach_id: str | None = _id(),
    from_date: date | None = None,
    to_date: date | None = None,
    status: s.SessionStatus | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    a: Actor = Depends(require(svc.SESSION_READ)),
    db: Session = Depends(get_db),
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(400, {"code": "invalid_period", "message": "from_date must not be after to_date"})
    filters = {
        "plan_id": plan_id,
        "coach_id": coach_id,
        "from_date": from_date,
        "to_date": to_date,
        "status": status,
    }
    return svc.list_sessions(db, a, filters, limit, offset)


@router.post("/sessions", status_code=201)
def schedule_training_session(
    body: s.SessionIn, a: Actor = Depends(require(svc.SESSION_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.schedule_session, db, a, s.dump(body))


@router.get("/sessions/{session_id}")
def get_training_session(session_id: str, a: Actor = Depends(require(svc.SESSION_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_session, db, a, session_id)


@router.patch("/sessions/{session_id}")
def update_training_session(
    session_id: str,
    body: s.SessionPatch,
    a: Actor = Depends(require(svc.SESSION_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_session, db, a, session_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- drills


@router.get("/drills")
def list_drills(
    category: str | None = None,
    intensity: s.Intensity | None = None,
    limit: int = Query(100, ge=1, le=200),
    offset: int = OFFSET,
    _: Actor = Depends(require(svc.DRILL_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_drills(db, {"category": category, "intensity": intensity}, limit, offset)


@router.post("/drills", status_code=201)
def create_drill(body: s.DrillIn, a: Actor = Depends(require(svc.DRILL_WRITE)), db: Session = Depends(get_db)):
    return _run(svc.create_drill, db, a, s.dump(body))


@router.get("/drills/{drill_id}")
def get_drill(drill_id: str, _: Actor = Depends(require(svc.DRILL_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_drill, db, drill_id)


@router.patch("/drills/{drill_id}")
def update_drill(
    drill_id: str, body: s.DrillPatch, a: Actor = Depends(require(svc.DRILL_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.update_drill, db, a, drill_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- videos


@router.get("/videos")
def list_training_videos(
    session_id: str | None = _id(),
    uploader_id: str | None = _id(),
    annotated: bool | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    a: Actor = Depends(require(svc.VIDEO_READ)),
    db: Session = Depends(get_db),
):
    filters = {"session_id": session_id, "uploader_id": uploader_id, "annotated": annotated}
    return svc.list_videos(db, a, filters, limit, offset)


@router.post("/videos", status_code=201)
def register_training_video(
    body: s.VideoIn, a: Actor = Depends(require(svc.VIDEO_UPLOAD)), db: Session = Depends(get_db)
):
    return _run(svc.register_video, db, a, s.dump(body))


@router.get("/videos/{video_id}")
def get_training_video(video_id: str, a: Actor = Depends(require(svc.VIDEO_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_video, db, a, video_id)


@router.patch("/videos/{video_id}")
def update_training_video(
    video_id: str, body: s.VideoPatch, a: Actor = Depends(require(svc.VIDEO_UPLOAD)), db: Session = Depends(get_db)
):
    return _run(svc.update_video, db, a, video_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- annotations


@router.get("/videos/{video_id}/annotations")
def list_video_annotations(video_id: str, a: Actor = Depends(require(svc.VIDEO_READ)), db: Session = Depends(get_db)):
    return _run(svc.list_annotations, db, a, video_id)


@router.post("/videos/{video_id}/annotations", status_code=201)
def add_video_annotation(
    video_id: str,
    body: s.AnnotationIn,
    a: Actor = Depends(require(svc.ANNOTATION_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.add_annotation, db, a, video_id, s.dump(body))


@router.get("/videos/{video_id}/annotations/{annotation_id}")
def get_video_annotation(
    video_id: str, annotation_id: str, a: Actor = Depends(require(svc.VIDEO_READ)), db: Session = Depends(get_db)
):
    return _run(svc.get_annotation, db, a, video_id, annotation_id)


@router.patch("/videos/{video_id}/annotations/{annotation_id}")
def update_video_annotation(
    video_id: str,
    annotation_id: str,
    body: s.AnnotationPatch,
    a: Actor = Depends(require(svc.ANNOTATION_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_annotation, db, a, video_id, annotation_id, s.dump(body, partial=True))


@router.delete("/videos/{video_id}/annotations/{annotation_id}", status_code=204)
def delete_video_annotation(
    video_id: str,
    annotation_id: str,
    a: Actor = Depends(require(svc.ANNOTATION_WRITE)),
    db: Session = Depends(get_db),
):
    _run(svc.delete_annotation, db, a, video_id, annotation_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- drill tags


@router.get("/videos/{video_id}/drill-tags")
def list_video_drill_tags(video_id: str, a: Actor = Depends(require(svc.VIDEO_READ)), db: Session = Depends(get_db)):
    return _run(svc.list_drill_tags, db, a, video_id)


@router.post("/videos/{video_id}/drill-tags", status_code=201)
def tag_drill_in_video(
    video_id: str, body: s.DrillTagIn, a: Actor = Depends(require(svc.VIDEO_TAG)), db: Session = Depends(get_db)
):
    return _run(svc.tag_drill, db, a, video_id, s.dump(body))
