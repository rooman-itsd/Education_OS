"""Use cases of training-video-analysis (docs/prd.md, contracts/openapi.yaml). Each one applies the domain rules,
changes state, publishes the matching event of contracts/events.yaml through eos_core.events.publish and writes an
audit entry (`_audit`) in the same transaction, then commits once. Permission keys are checked by the API layer
(api/deps.require); which rows a caller may see is decided here.

Athletes see only what is theirs (docs/prd.md, contracts/permissions.yaml): a caller whose only training-video-analysis
access comes from an athlete role is `self_only`. Their athlete ids come from AthleteLink, which the consumers of
athlete-performance's athlete events keep (application/consumers.py). A self-only caller sees
- the sessions that list one of their athletes as an attendee, without the coach's notes and with only their own
  attendee id;
- the plans those sessions belong to;
- the videos of those sessions and the videos with an annotation that tags them;
- on those videos, the drill tags and the annotations that tag them or tag no one, with only their own tagged id.
Anything else answers 404, so another athlete's ids are not even confirmed. Anyone else with the read permission sees
the whole organisation. Drills are a shared catalogue.

Known dependencies, not worked around here:
- The audit SDK does not exist (packages/sdk is empty). Until it does, training_video_analysis_audit_entry stands in
  for it, shaped like platform/audit's Record, as athlete-performance's audit table is.
- Video files are held by platform/documents; this module stores the reference (video_url) and metadata only."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from eos_core import events
from eos_core.db import new_id, utcnow
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import RuleViolationError
from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from ..infrastructure.models import (
    Annotation,
    AnnotationAthlete,
    AuditEntry,
    Drill,
    DrillTag,
    Plan,
    SessionAttendee,
    TrainingSession,
    Video,
    as_utc,
    iso,
)

MODULE = "training-video-analysis"
PLAN_READ = f"{MODULE}:plan:read"
PLAN_WRITE = f"{MODULE}:plan:write"
SESSION_READ = f"{MODULE}:session:read"
SESSION_WRITE = f"{MODULE}:session:write"
DRILL_READ = f"{MODULE}:drill:read"
DRILL_WRITE = f"{MODULE}:drill:write"
VIDEO_READ = f"{MODULE}:video:read"
VIDEO_UPLOAD = f"{MODULE}:video:upload"
VIDEO_TAG = f"{MODULE}:video:tag"
ANNOTATION_WRITE = f"{MODULE}:annotation:write"

# Roles whose access is limited to the caller's own sessions and videos.
ATHLETE_ROLES = frozenset({"athlete", "training-video-analysis-athlete"})
# Free text and file links stay out of audit before/after; a change is still named in the summary.
NOT_RECORDED = frozenset(
    {
        "title",
        "description",
        "notes",
        "content",
        "drawing_markup",
        "objectives",
        "location",
        "target_focus",
        "video_url",
        "thumbnail_url",
    }
)


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


@dataclass
class Actor:
    """Who is calling. Built by the API layer from the verified token."""

    user_id: str
    organisation_id: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)
    self_only: bool = False

    def can(self, permission: str) -> bool:
        return permission in self.permissions


class ServiceError(Exception):
    """A refusal with an HTTP status and a contract error body ({code, message})."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def body(self) -> dict:
        return {"code": self.code, "message": self.message}


def _not_found(what: str) -> ServiceError:
    return ServiceError(404, "not_found", f"{what} not found in your organisation")


def _invalid(code: str, message: str) -> ServiceError:
    return ServiceError(400, code, message)


def _rule(v: RuleViolationError) -> ServiceError:
    return ServiceError(400, v.code, v.message)


def _check(fn, *args) -> None:
    """Run a domain rule; a refusal becomes a 400 with the rule's code."""
    try:
        fn(*args)
    except RuleViolationError as v:
        raise _rule(v) from v


# ---------------------------------------------------------------- helpers


def _clean(d: dict) -> dict:
    """Optional contract fields are left out rather than sent as null."""
    return {k: v for k, v in d.items() if v is not None}


def _publish(db: Session, actor: Actor, name: str, payload: dict) -> None:
    org = actor.organisation_id
    events.publish(db, f"{MODULE}.{name}", org, {"organisation_id": org, **payload}, actor=actor.user_id)


def _json(value):
    if isinstance(value, datetime | date):
        return iso(value)
    return value


def _audit(db: Session, actor: Actor, action: str, entity_type: str, row_id: str, *, before=None, after=None) -> None:
    """One audit record per state change, in the same transaction. `before` and `after` are the changed fields only
    (None for a creation's `before` and a deletion's `after`)."""
    changed = sorted(after) if before is not None and after else []
    summary = f"{entity_type.replace('_', ' ')} {row_id} {action}" + (f": {', '.join(changed)}" if changed else "")

    def recorded(fields):
        return None if fields is None else {k: _json(v) for k, v in fields.items() if k not in NOT_RECORDED}

    db.add(
        AuditEntry(
            organisation_id=actor.organisation_id,
            client_token=new_id(),
            actor=actor.user_id,
            action=f"{entity_type}.{action}",
            entity_type=entity_type,
            entity_id=row_id,
            summary=summary[:300],
            before=recorded(before),
            after=recorded(after),
            occurred_at=clock(),
        )
    )


def _commit(db: Session, duplicate_code: str = "conflict", duplicate_message: str = "the change conflicts") -> None:
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise _invalid(duplicate_code, duplicate_message) from e


def _get(db: Session, model, row_id: str | None, what: str):
    row = repo.get(db, model, row_id)
    if row is None:
        raise _not_found(what)
    return row


def _known(db: Session, model, ids, what: str) -> None:
    """Every referenced id exists in the caller's organisation; another organisation's ids are unknown here."""
    ids = {i for i in ids if i is not None}
    missing = ids - repo.ids_present(db, model, ids)
    if missing:
        raise _invalid(f"unknown_{what}", f"{what} {sorted(missing)[0]} not found in your organisation")


def _apply(row, data: dict) -> tuple[dict, dict]:
    """Set the fields that change; return (before, after) of those fields only."""
    before, after = {}, {}
    for k, v in data.items():
        current = getattr(row, k)
        if isinstance(current, datetime):
            current = as_utc(current)
        if current != v:
            before[k], after[k] = current, v
            setattr(row, k, v)
    return before, after


def _page(items: list, total: int) -> dict:
    return {"items": items, "total": total}


def _local_zone() -> ZoneInfo:
    return ZoneInfo(load_settings().timezone)


def _local_date(value: datetime) -> date:
    return as_utc(value).astimezone(_local_zone()).date()


def _local_midnight(day: date) -> datetime:
    """The UTC instant at which a local day starts."""
    return datetime.combine(day, time.min, tzinfo=_local_zone()).astimezone(UTC)


# ---------------------------------------------------------------- who may see what


def own_athletes(db: Session, actor: Actor) -> set[str]:
    """The athlete ids of a self-only caller (empty when athlete-performance has not linked them)."""
    return repo.athletes_of_user(db, actor.user_id)


def _visible_sessions(db: Session, own: set[str]):
    return TrainingSession.id.in_(repo.sessions_attended_by(db, own))


def _visible_plans(db: Session, own: set[str]):
    sessions = repo.query(db, TrainingSession).with_only_columns(TrainingSession.plan_id)
    return Plan.id.in_(sessions.where(_visible_sessions(db, own)))


def _visible_videos(db: Session, own: set[str]):
    tagged = repo.query(db, Annotation).with_only_columns(Annotation.video_id)
    tagged = tagged.where(Annotation.id.in_(repo.annotations_tagging(db, own)))
    return or_(Video.session_id.in_(repo.sessions_attended_by(db, own)), Video.id.in_(tagged))


def _visible_annotations(db: Session, own: set[str]):
    """Annotations about the caller, and general ones that tag no athlete."""
    return or_(
        Annotation.id.in_(repo.annotations_tagging(db, own)),
        Annotation.id.not_in(repo.annotations_tagging(db)),
    )


def _visible(db: Session, actor: Actor, model, row_id: str, what: str, condition) -> object:
    """The row, if the caller may see it: 404 otherwise, the same answer as for an id that does not exist."""
    if not actor.self_only:
        return _get(db, model, row_id, what)
    if not row_id:
        raise _not_found(what)
    own = own_athletes(db, actor)
    row = db.scalars(repo.query(db, model).where(model.id == row_id, condition(db, own))).first()
    if row is None:
        raise _not_found(what)
    return row


def _visible_video(db: Session, actor: Actor, video_id: str) -> Video:
    return _visible(db, actor, Video, video_id, "video", _visible_videos)


# ---------------------------------------------------------------- serialisers


def plan_out(p: Plan) -> dict:
    return _clean(
        {
            "id": p.id,
            "organisation_id": p.organisation_id,
            "title": p.title,
            "description": p.description,
            "coach_id": p.coach_id,
            "squad_id": p.squad_id,
            "start_date": iso(p.start_date),
            "end_date": iso(p.end_date),
            "status": p.status,
            "objectives": list(p.objectives or []),
            "created_at": iso(p.created_at),
            "updated_at": iso(p.updated_at),
        }
    )


def session_out(s: TrainingSession, attendees: list[str], own: set[str] | None = None) -> dict:
    """`own` is a self-only caller's athlete ids: they see only their own attendance and not the coach's notes."""
    if own is not None:
        attendees = [a for a in attendees if a in own]
    return _clean(
        {
            "id": s.id,
            "organisation_id": s.organisation_id,
            "plan_id": s.plan_id,
            "coach_id": s.coach_id,
            "title": s.title,
            "description": s.description,
            "facility_id": s.facility_id,
            "location": s.location,
            "scheduled_start": iso(s.scheduled_start),
            "scheduled_end": iso(s.scheduled_end),
            "actual_duration_minutes": s.actual_duration_minutes,
            "status": s.status,
            "attendee_ids": list(attendees),
            "drill_ids": list(s.drill_ids or []),
            "notes": None if own is not None else s.notes,
            "created_at": iso(s.created_at),
            "updated_at": iso(s.updated_at),
        }
    )


def drill_out(d: Drill) -> dict:
    return _clean(
        {
            "id": d.id,
            "organisation_id": d.organisation_id,
            "code": d.code,
            "title": d.title,
            "description": d.description,
            "category": d.category,
            "intensity": d.intensity,
            "target_focus": d.target_focus,
            "equipment_needed": list(d.equipment_needed or []),
            "standard_duration_minutes": d.standard_duration_minutes,
            "created_at": iso(d.created_at),
        }
    )


def video_out(v: Video) -> dict:
    return _clean(
        {
            "id": v.id,
            "organisation_id": v.organisation_id,
            "session_id": v.session_id,
            "uploader_id": v.uploader_id,
            "title": v.title,
            "description": v.description,
            "video_url": v.video_url,
            "thumbnail_url": v.thumbnail_url,
            "duration_seconds": v.duration_seconds,
            "resolution": v.resolution,
            "recorded_at": iso(v.recorded_at),
            "created_at": iso(v.created_at),
        }
    )


def annotation_out(a: Annotation, tagged: list[str], own: set[str] | None = None) -> dict:
    if own is not None:
        tagged = [t for t in tagged if t in own]
    return _clean(
        {
            "id": a.id,
            "video_id": a.video_id,
            "author_id": a.author_id,
            "start_timestamp": a.start_timestamp,
            "end_timestamp": a.end_timestamp,
            "content": a.content,
            "category": a.category,
            "drawing_markup": a.drawing_markup,
            "tagged_athlete_ids": list(tagged),
            "created_at": iso(a.created_at),
        }
    )


def drill_tag_out(t: DrillTag, drill_title: str | None) -> dict:
    return _clean(
        {
            "id": t.id,
            "video_id": t.video_id,
            "drill_id": t.drill_id,
            "drill_title": drill_title,
            "start_timestamp": t.start_timestamp,
            "end_timestamp": t.end_timestamp,
            "notes": t.notes,
        }
    )


def _own_or_none(db: Session, actor: Actor) -> set[str] | None:
    return own_athletes(db, actor) if actor.self_only else None


# ---------------------------------------------------------------- plans


def list_plans(db: Session, actor: Actor, filters: dict, limit: int, offset: int) -> dict:
    q = repo.query(db, Plan)
    if actor.self_only:
        q = q.where(_visible_plans(db, own_athletes(db, actor)))
    for name in ("coach_id", "status"):
        if filters.get(name):
            q = q.where(getattr(Plan, name) == filters[name])
    rows, total = repo.page(db, q, (Plan.start_date.desc(), Plan.id), limit, offset)
    return _page([plan_out(p) for p in rows], total)


def create_plan(db: Session, actor: Actor, data: dict) -> dict:
    _check(rules.check_plan_period, data["start_date"], data["end_date"])
    data = {**data, "objectives": list(data.get("objectives") or [])}
    p = Plan(organisation_id=actor.organisation_id, created_by=actor.user_id, **data)
    db.add(p)
    db.flush()
    _audit(db, actor, "created", "plan", p.id, after=data)
    _publish(
        db,
        actor,
        "plan.created",
        {
            "plan_id": p.id,
            "title": p.title,
            "coach_id": p.coach_id,
            "start_date": iso(p.start_date),
            "end_date": iso(p.end_date),
        },
    )
    _commit(db)
    return plan_out(p)


def get_plan(db: Session, actor: Actor, plan_id: str) -> dict:
    return plan_out(_visible(db, actor, Plan, plan_id, "plan", _visible_plans))


def _session_days(db: Session, plan_id: str) -> tuple[date, date] | None:
    """The local days of the plan's first and last sessions that are not cancelled."""
    q = repo.query(db, TrainingSession).where(TrainingSession.plan_id == plan_id, TrainingSession.status != "cancelled")
    first, last = db.execute(
        q.with_only_columns(func.min(TrainingSession.scheduled_start), func.max(TrainingSession.scheduled_start))
    ).one()
    if first is None:
        return None
    return _local_date(first), _local_date(last)


def update_plan(db: Session, actor: Actor, plan_id: str, data: dict) -> dict:
    p = _get(db, Plan, plan_id, "plan")
    _check(rules.check_plan_editable, p.status)
    if "status" in data:
        _check(rules.check_plan_transition, p.status, data["status"])
    start, end = data.get("start_date", p.start_date), data.get("end_date", p.end_date)
    _check(rules.check_plan_period, start, end)
    if ("start_date" in data or "end_date" in data) and (days := _session_days(db, p.id)):
        if days[0] < start or days[1] > end:
            raise _invalid("sessions_outside_plan", "the plan's sessions would fall outside its new dates")
    if "objectives" in data:
        data = {**data, "objectives": list(data["objectives"] or [])}
    before, after = _apply(p, data)
    if after:
        _audit(db, actor, "updated", "plan", p.id, before=before, after=after)
        _commit(db)
    return plan_out(p)


# ---------------------------------------------------------------- drills


def list_drills(db: Session, filters: dict, limit: int, offset: int) -> dict:
    q = repo.query(db, Drill)
    for name in ("category", "intensity"):
        if filters.get(name):
            q = q.where(getattr(Drill, name) == filters[name])
    rows, total = repo.page(db, q, (Drill.title, Drill.id), limit, offset)
    return _page([drill_out(d) for d in rows], total)


def create_drill(db: Session, actor: Actor, data: dict) -> dict:
    duplicate = f"a drill with code {data['code']!r} already exists"
    if repo.first_by(db, Drill, code=data["code"]):
        raise _invalid("duplicate_code", duplicate)
    data = {**data, "equipment_needed": list(data.get("equipment_needed") or [])}
    d = Drill(organisation_id=actor.organisation_id, **data)
    db.add(d)
    db.flush()
    _audit(db, actor, "created", "drill", d.id, after=data)
    _commit(db, "duplicate_code", duplicate)
    return drill_out(d)


def get_drill(db: Session, drill_id: str) -> dict:
    return drill_out(_get(db, Drill, drill_id, "drill"))


def update_drill(db: Session, actor: Actor, drill_id: str, data: dict) -> dict:
    d = _get(db, Drill, drill_id, "drill")
    if "equipment_needed" in data:
        data = {**data, "equipment_needed": list(data["equipment_needed"] or [])}
    before, after = _apply(d, data)
    if after:
        _audit(db, actor, "updated", "drill", d.id, before=before, after=after)
        _commit(db)
    return drill_out(d)


# ---------------------------------------------------------------- sessions


def list_sessions(db: Session, actor: Actor, filters: dict, limit: int, offset: int) -> dict:
    q = repo.query(db, TrainingSession)
    own = _own_or_none(db, actor)
    if own is not None:
        q = q.where(_visible_sessions(db, own))
    for name in ("plan_id", "coach_id", "status"):
        if filters.get(name):
            q = q.where(getattr(TrainingSession, name) == filters[name])
    if filters.get("from_date"):
        q = q.where(TrainingSession.scheduled_start >= _local_midnight(filters["from_date"]))
    if filters.get("to_date"):
        q = q.where(TrainingSession.scheduled_start < _local_midnight(filters["to_date"] + timedelta(days=1)))
    rows, total = repo.page(db, q, (TrainingSession.scheduled_start, TrainingSession.id), limit, offset)
    attendees = repo.attendees_of(db, [s.id for s in rows])
    return _page([session_out(s, attendees.get(s.id, []), own) for s in rows], total)


def _check_session_plan(db: Session, plan_id: str | None, start: datetime, *, new: bool) -> None:
    if plan_id is None:
        return
    plan = repo.get(db, Plan, plan_id)
    if plan is None:
        raise _invalid("unknown_plan", f"plan {plan_id} not found in your organisation")
    if new:
        _check(rules.check_plan_open, plan.status)
    _check(rules.check_session_in_plan, _local_date(start), plan.start_date, plan.end_date)


def schedule_session(db: Session, actor: Actor, data: dict) -> dict:
    data = {**data, "drill_ids": rules.unique(data.get("drill_ids"))}
    attendees = rules.unique(data.pop("attendee_ids", None))
    _check(rules.check_session_window, data["scheduled_start"], data["scheduled_end"])
    _check_session_plan(db, data.get("plan_id"), data["scheduled_start"], new=True)
    _known(db, Drill, data["drill_ids"], "drill")
    s = TrainingSession(organisation_id=actor.organisation_id, status="scheduled", **data)
    db.add(s)
    db.flush()
    repo.set_athletes(db, SessionAttendee, "session_id", s.id, actor.organisation_id, attendees)
    _audit(db, actor, "scheduled", "session", s.id, after={**data, "attendee_ids": attendees})
    _publish(
        db,
        actor,
        "session.scheduled",
        _clean(
            {
                "session_id": s.id,
                "plan_id": s.plan_id,
                "coach_id": s.coach_id,
                "scheduled_start": iso(s.scheduled_start),
                "location": s.location,
            }
        ),
    )
    _commit(db)
    return session_out(s, attendees)


def get_session(db: Session, actor: Actor, session_id: str) -> dict:
    s = _visible(db, actor, TrainingSession, session_id, "session", _visible_sessions)
    return session_out(s, repo.attendees_of(db, [s.id]).get(s.id, []), _own_or_none(db, actor))


def update_session(db: Session, actor: Actor, session_id: str, data: dict) -> dict:
    s = _get(db, TrainingSession, session_id, "session")
    data = dict(data)
    _check(rules.check_session_change, s.status, set(data) - {"status"})
    status = data.get("status", s.status)
    if "status" in data:
        _check(rules.check_session_transition, s.status, status)
    completing = status == "completed" and s.status != "completed"
    if data.get("actual_duration_minutes") is not None:
        _check(rules.check_duration_allowed, status)
    start = data.get("scheduled_start", as_utc(s.scheduled_start))
    end = data.get("scheduled_end", as_utc(s.scheduled_end))
    if "scheduled_start" in data or "scheduled_end" in data:
        _check(rules.check_session_window, start, end)
        _check_session_plan(db, s.plan_id, start, new=False)
    if completing:
        now = clock()
        _check(rules.check_completion, now, start)
        data["completed_at"] = now
    if "drill_ids" in data:
        data["drill_ids"] = rules.unique(data["drill_ids"])
        _known(db, Drill, data["drill_ids"], "drill")

    current = repo.attendees_of(db, [s.id]).get(s.id, [])
    attendees = rules.unique(data.pop("attendee_ids")) if "attendee_ids" in data else current
    before, after = _apply(s, data)
    if attendees != current:
        repo.set_athletes(db, SessionAttendee, "session_id", s.id, actor.organisation_id, attendees)
        before["attendee_ids"], after["attendee_ids"] = current, attendees
    if after:
        db.flush()
        after.pop("completed_at", None)
        before.pop("completed_at", None)
        _audit(db, actor, "completed" if completing else "updated", "session", s.id, before=before, after=after)
        if completing:
            _publish(
                db,
                actor,
                "session.completed",
                {
                    "session_id": s.id,
                    "completed_at": iso(s.completed_at),
                    "duration_minutes": rules.completed_duration(s.actual_duration_minutes, start, end),
                },
            )
        _commit(db)
    return session_out(s, attendees)


# ---------------------------------------------------------------- videos


def list_videos(db: Session, actor: Actor, filters: dict, limit: int, offset: int) -> dict:
    q = repo.query(db, Video)
    if actor.self_only:
        q = q.where(_visible_videos(db, own_athletes(db, actor)))
    for name in ("session_id", "uploader_id"):
        if filters.get(name):
            q = q.where(getattr(Video, name) == filters[name])
    if filters.get("annotated") is not None:
        # Any annotation counts, whoever wrote it: a video with none is waiting for review.
        has = select(Annotation.id).where(Annotation.video_id == Video.id).exists()
        q = q.where(has if filters["annotated"] else ~has)
    rows, total = repo.page(db, q, (Video.recorded_at.desc(), Video.id), limit, offset)
    return _page([video_out(v) for v in rows], total)


def register_video(db: Session, actor: Actor, data: dict) -> dict:
    _known(db, TrainingSession, [data.get("session_id")], "session")
    _check(rules.not_in_future, data["recorded_at"], clock(), "recorded_at")
    v = Video(organisation_id=actor.organisation_id, registered_by=actor.user_id, **data)
    db.add(v)
    db.flush()
    _audit(db, actor, "registered", "video", v.id, after=data)
    _publish(
        db,
        actor,
        "video.uploaded",
        _clean(
            {
                "video_id": v.id,
                "session_id": v.session_id,
                "title": v.title,
                "duration_seconds": v.duration_seconds,
                "video_url": v.video_url,
            }
        ),
    )
    _commit(db)
    return video_out(v)


def get_video(db: Session, actor: Actor, video_id: str) -> dict:
    return video_out(_visible_video(db, actor, video_id))


def update_video(db: Session, actor: Actor, video_id: str, data: dict) -> dict:
    v = _get(db, Video, video_id, "video")
    before, after = _apply(v, data)
    if after:
        _audit(db, actor, "updated", "video", v.id, before=before, after=after)
        _commit(db)
    return video_out(v)


# ---------------------------------------------------------------- annotations


def list_annotations(db: Session, actor: Actor, video_id: str) -> list[dict]:
    v = _visible_video(db, actor, video_id)
    q = repo.query(db, Annotation).where(Annotation.video_id == v.id)
    own = _own_or_none(db, actor)
    if own is not None:
        q = q.where(_visible_annotations(db, own))
    rows = list(db.scalars(q.order_by(Annotation.start_timestamp, Annotation.created_at, Annotation.id)))
    tagged = repo.tagged_athletes_of(db, [a.id for a in rows])
    return [annotation_out(a, tagged.get(a.id, []), own) for a in rows]


def _annotation(db: Session, actor: Actor, video_id: str, annotation_id: str) -> tuple[Video, Annotation]:
    v = _visible_video(db, actor, video_id)
    a = _visible(db, actor, Annotation, annotation_id, "annotation", _visible_annotations)
    if a.video_id != v.id:
        raise _not_found("annotation")
    return v, a


def add_annotation(db: Session, actor: Actor, video_id: str, data: dict) -> dict:
    v = _get(db, Video, video_id, "video")
    if data["author_id"] != actor.user_id:
        raise _invalid("not_the_author", "author_id must be the caller: an annotation is attributed to who writes it")
    _check(rules.check_annotation_time, data["start_timestamp"], data.get("end_timestamp"), v.duration_seconds)
    tagged = rules.unique(data.pop("tagged_athlete_ids", None))
    a = Annotation(organisation_id=actor.organisation_id, video_id=v.id, **data)
    db.add(a)
    db.flush()
    repo.set_athletes(db, AnnotationAthlete, "annotation_id", a.id, actor.organisation_id, tagged)
    _audit(db, actor, "added", "annotation", a.id, after={**data, "video_id": v.id, "tagged_athlete_ids": tagged})
    _publish(
        db,
        actor,
        "annotation.added",
        {
            "annotation_id": a.id,
            "video_id": v.id,
            "author_id": a.author_id,
            "start_timestamp": a.start_timestamp,
            "category": a.category,
        },
    )
    _commit(db)
    return annotation_out(a, tagged)


def get_annotation(db: Session, actor: Actor, video_id: str, annotation_id: str) -> dict:
    _, a = _annotation(db, actor, video_id, annotation_id)
    own = _own_or_none(db, actor)
    return annotation_out(a, repo.tagged_athletes_of(db, [a.id]).get(a.id, []), own)


def update_annotation(db: Session, actor: Actor, video_id: str, annotation_id: str, data: dict) -> dict:
    """Only the author changes an annotation: it stays attributed to them."""
    v, a = _annotation(db, actor, video_id, annotation_id)
    if a.author_id != actor.user_id:
        raise ServiceError(403, "not_the_author", "only the author can change an annotation")
    data = dict(data)
    start = data.get("start_timestamp", a.start_timestamp)
    end = data["end_timestamp"] if "end_timestamp" in data else a.end_timestamp
    _check(rules.check_annotation_time, start, end, v.duration_seconds)
    current = repo.tagged_athletes_of(db, [a.id]).get(a.id, [])
    tagged = rules.unique(data.pop("tagged_athlete_ids")) if "tagged_athlete_ids" in data else current
    before, after = _apply(a, data)
    if tagged != current:
        repo.set_athletes(db, AnnotationAthlete, "annotation_id", a.id, actor.organisation_id, tagged)
        before["tagged_athlete_ids"], after["tagged_athlete_ids"] = current, tagged
    if after:
        db.flush()
        _audit(db, actor, "updated", "annotation", a.id, before=before, after=after)
        _commit(db)
    return annotation_out(a, tagged)


def delete_annotation(db: Session, actor: Actor, video_id: str, annotation_id: str) -> None:
    """The author removes their annotation; anyone else holding annotation:write may too, to moderate. The audit
    entry keeps who removed it and when, not its content."""
    _, a = _annotation(db, actor, video_id, annotation_id)
    tagged = repo.tagged_athletes_of(db, [a.id]).get(a.id, [])
    before = {
        "video_id": a.video_id,
        "author_id": a.author_id,
        "start_timestamp": a.start_timestamp,
        "end_timestamp": a.end_timestamp,
        "category": a.category,
        "tagged_athlete_ids": tagged,
    }
    repo.set_athletes(db, AnnotationAthlete, "annotation_id", a.id, actor.organisation_id, [])
    db.delete(a)
    db.flush()
    _audit(db, actor, "deleted", "annotation", a.id, before=before)
    _commit(db)


# ---------------------------------------------------------------- drill tags


def list_drill_tags(db: Session, actor: Actor, video_id: str) -> list[dict]:
    v = _visible_video(db, actor, video_id)
    rows = repo.tags_of(db, v.id)
    titles = repo.drill_titles(db, [t.drill_id for t in rows])
    return [drill_tag_out(t, titles.get(t.drill_id)) for t in rows]


def tag_drill(db: Session, actor: Actor, video_id: str, data: dict) -> dict:
    v = _get(db, Video, video_id, "video")
    drill = repo.get(db, Drill, data["drill_id"])
    if drill is None:
        raise _invalid("unknown_drill", f"drill {data['drill_id']} not found in your organisation")
    _check(rules.check_segment, data["start_timestamp"], data["end_timestamp"], v.duration_seconds)
    t = DrillTag(organisation_id=actor.organisation_id, video_id=v.id, tagged_by=actor.user_id, **data)
    db.add(t)
    db.flush()
    _audit(db, actor, "tagged", "drill_tag", t.id, after={**data, "video_id": v.id})
    _publish(
        db,
        actor,
        "video.tagged",
        {
            "video_id": v.id,
            "drill_id": t.drill_id,
            "start_timestamp": t.start_timestamp,
            "end_timestamp": t.end_timestamp,
        },
    )
    _commit(db)
    return drill_tag_out(t, drill.title)
