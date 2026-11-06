"""Use cases of alumni. Authenticated calls arrive with the caller's organisation pinned on the session (api/deps), and
every query goes through eos_core `scoped`, so a record of another organisation answers 404 exactly like one that does
not exist. Every state change writes an audit record and publishes its alumni.* event to the eos_core outbox in the
same transaction. Event payloads carry ids only (events.yaml): no names, contact details or notes.

What a student sees: only GET /me/mentoring, which looks the caller up by (organisation_id, student_id) and returns
their own active assignment with the mentor's card (contact details included, A5) and upcoming sessions without staff
notes. Nothing else in this module answers a student."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

from eos_core import events
from eos_core.db import scoped, utcnow
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import RuleError
from ..infrastructure.models import Alumnus, Assignment, AuditEntry, MentoringSession
from .access import Actor
from .errors import AlumniError, conflict, from_rule, not_found

MODULE = "alumni"
MY_UPCOMING = 5  # sessions GET /me/mentoring returns (MyMentoring.upcoming_sessions maxItems)
ENDED_BY_ASSIGNMENT = "The assignment ended."


def clock() -> datetime:
    """Now, in UTC. Tests replace it."""
    return utcnow()


# Business dates are Indian (A7). Asia/Kolkata has kept UTC+05:30 without daylight saving since 1945, so a fixed
# offset is exact and needs no time-zone database (tzdata is not on the approved stack), as in e-office.
BUSINESS_TZ = timezone(timedelta(hours=5, minutes=30), "Asia/Kolkata")


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def business_date(moment: datetime) -> date:
    """The Indian calendar date of a moment; timestamps themselves stay UTC."""
    return _aware(moment).astimezone(BUSINESS_TZ).date()


def business_today() -> date:
    """Today in Asia/Kolkata: the date "not in the future" and the current graduation year are judged against."""
    return business_date(clock())


def _publish(db: Session, actor: Actor, name: str, payload: dict) -> None:
    org = actor.organisation_id
    events.publish(db, f"{MODULE}.{name}", org, {"organisation_id": org, **payload}, actor=actor.user_id)


def _audit(db: Session, actor: Actor, action: str, entity: str, row) -> None:
    """One audit record per state change, in the same transaction. The row is flushed first so a new one has its id."""
    db.flush()
    db.add(
        AuditEntry(
            organisation_id=row.organisation_id,
            actor=actor.user_id,
            action=action,
            entity=entity,
            entity_id=row.id,
            occurred_at=clock(),
        )
    )


def _rule(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except RuleError as e:
        raise from_rule(e) from e


def _q(db: Session, model):
    return scoped(db, select(model), model)


def _get(db: Session, model, row_id: str, what: str, *, lock: bool = False):
    q = _q(db, model).where(model.id == row_id)
    if lock:
        q = q.with_for_update()
    row = db.scalar(q)
    if row is None:
        raise not_found(what)
    return row


def _iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        value = _aware(value).astimezone(UTC)
    return value.isoformat()


def _offset(cursor: str | None) -> int:
    """The cursor is the offset this API returned as next_cursor; anything else is 400 invalid_cursor."""
    if cursor is None:
        return 0
    if not cursor.isdigit() or len(cursor) > 9:
        raise AlumniError(400, "invalid_cursor", "invalid cursor")
    return int(cursor)


def _page(db: Session, q, cursor: str | None, limit: int, render) -> dict:
    offset = _offset(cursor)
    rows = list(db.scalars(q.offset(offset).limit(limit + 1)))
    return {
        "items": [render(r) for r in rows[:limit]],
        "next_cursor": str(offset + limit) if len(rows) > limit else None,
    }


# ---------------------------------------------------------------- directory


def _active_mentees(db: Session, mentor_ids: list[str]) -> dict[str, int]:
    if not mentor_ids:
        return {}
    q = (
        scoped(db, select(Assignment.mentor_id, func.count()), Assignment)
        .where(Assignment.mentor_id.in_(mentor_ids), Assignment.status == "active")
        .group_by(Assignment.mentor_id)
    )
    return dict(db.execute(q).all())


def alumnus_dict(a: Alumnus, active_mentees: int) -> dict:
    return {
        "id": a.id,
        "organisation_id": a.organisation_id,
        "status": a.status,
        "full_name": a.full_name,
        "graduation_year": a.graduation_year,
        "programme": a.programme,
        "current_company": a.current_company,
        "current_designation": a.current_designation,
        "industry": a.industry,
        "city": a.city,
        "email": a.email,
        "phone": a.phone,
        "linkedin_url": a.linkedin_url,
        "is_mentor": a.is_mentor,
        "notes": a.notes,
        "active_mentees": active_mentees,
        "created_by": a.created_by,
        "created_at": _iso(a.created_at),
        "verified_by": a.verified_by,
        "verified_at": _iso(a.verified_at),
        "archived_at": _iso(a.archived_at),
        "archive_reason": a.archive_reason,
    }


def _render_alumnus(db: Session, a: Alumnus) -> dict:
    return alumnus_dict(a, _active_mentees(db, [a.id]).get(a.id, 0))


def list_alumni(db: Session, filters: dict, cursor: str | None, limit: int) -> dict:
    """Newest first. Without a status filter only active records are listed; archived ones need status=archived."""
    q = _q(db, Alumnus).where(Alumnus.status == (filters.get("status") or "active"))
    if filters.get("is_mentor") is not None:
        q = q.where(Alumnus.is_mentor.is_(filters["is_mentor"]))
    if filters.get("graduation_year") is not None:
        q = q.where(Alumnus.graduation_year == filters["graduation_year"])
    programme = rules.optional_text(filters.get("programme"))
    if programme:
        q = q.where(func.lower(Alumnus.programme) == programme.lower())
    text = rules.optional_text(filters.get("q"))
    if text:
        escaped = text.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        q = q.where(
            or_(
                func.lower(Alumnus.full_name).like(like, escape="\\"),
                func.lower(Alumnus.current_company).like(like, escape="\\"),
                func.lower(Alumnus.current_designation).like(like, escape="\\"),
            )
        )
    q = q.order_by(Alumnus.created_at.desc(), Alumnus.id.desc())
    page = _page(db, q, cursor, limit, lambda a: a)
    counts = _active_mentees(db, [a.id for a in page["items"]])
    page["items"] = [alumnus_dict(a, counts.get(a.id, 0)) for a in page["items"]]
    return page


def get_alumnus(db: Session, alumnus_id: str) -> dict:
    return _render_alumnus(db, _get(db, Alumnus, alumnus_id, "alumnus"))


def _alumnus_values(a: Alumnus, body: dict) -> None:
    """Every field of AlumnusInput; a field left out is cleared (PUT is a full replace, A8)."""
    a.full_name = _rule(rules.full_name, body.get("full_name"))
    a.graduation_year = _rule(rules.graduation_year, body.get("graduation_year"), business_today().year)
    for name in ("programme", "current_company", "current_designation", "industry", "city", "notes"):
        setattr(a, name, rules.optional_text(body.get(name)))
    a.email = _rule(rules.email, body.get("email"))
    a.phone = _rule(rules.phone, body.get("phone"))
    a.linkedin_url = _rule(rules.url, body.get("linkedin_url"))


def _active_count(db: Session, mentor_id: str) -> int:
    return _active_mentees(db, [mentor_id]).get(mentor_id, 0)


def add_alumnus(db: Session, actor: Actor, body: dict) -> dict:
    """A record created by staff is verified by its creator at its creation time (A2)."""
    now = clock()
    a = Alumnus(organisation_id=actor.organisation_id, status="active", created_by=actor.user_id, created_at=now)
    _alumnus_values(a, body)
    a.is_mentor = bool(body.get("is_mentor") or False)
    a.verified_by, a.verified_at = actor.user_id, now
    db.add(a)
    _audit(db, actor, "alumnus.added", "alumnus", a)
    _publish(
        db,
        actor,
        "alumnus.added",
        {
            "alumnus_id": a.id,
            "graduation_year": a.graduation_year,
            "is_mentor": a.is_mentor,
            "verified_by": a.verified_by,
        },
    )
    db.commit()
    return alumnus_dict(a, 0)


def update_alumnus(db: Session, actor: Actor, alumnus_id: str, body: dict) -> dict:
    """Edit an active record as a full replace (A8). The mentor flag is not cleared while they mentor someone."""
    a = _get(db, Alumnus, alumnus_id, "alumnus", lock=True)
    if a.status == "archived":
        raise conflict("alumnus_archived", "an archived alumnus is not edited; restore it first")
    _alumnus_values(a, body)
    is_mentor = bool(body["is_mentor"])
    if a.is_mentor and not is_mentor and _active_count(db, a.id):
        raise conflict(
            "mentor_has_active_assignments", "end this mentor's active assignments before clearing is_mentor"
        )
    a.is_mentor = is_mentor
    _audit(db, actor, "alumnus.updated", "alumnus", a)
    db.commit()
    return _render_alumnus(db, a)


def archive_alumnus(db: Session, actor: Actor, alumnus_id: str, reason: str | None) -> dict:
    a = _get(db, Alumnus, alumnus_id, "alumnus", lock=True)
    if a.status == "archived":
        raise conflict("alumnus_archived", "the alumnus is already archived")
    if _active_count(db, a.id):
        raise conflict("mentor_has_active_assignments", "end this mentor's active assignments before archiving")
    a.status, a.archived_at, a.archive_reason = "archived", clock(), rules.optional_text(reason)
    _audit(db, actor, "alumnus.archived", "alumnus", a)
    _publish(db, actor, "alumnus.archived", {"alumnus_id": a.id})
    db.commit()
    return alumnus_dict(a, 0)


def restore_alumnus(db: Session, actor: Actor, alumnus_id: str) -> dict:
    """Active again; the archive time and reason are cleared (the audit trail keeps that it was archived)."""
    a = _get(db, Alumnus, alumnus_id, "alumnus", lock=True)
    if a.status != "archived":
        raise conflict("not_archived", "only an archived alumnus is restored")
    a.status, a.archived_at, a.archive_reason = "active", None, None
    _audit(db, actor, "alumnus.restored", "alumnus", a)
    _publish(db, actor, "alumnus.restored", {"alumnus_id": a.id})
    db.commit()
    return alumnus_dict(a, 0)


# ---------------------------------------------------------------- mentoring assignments


def mentor_card(a: Alumnus) -> dict:
    """The mentor as their assigned mentee (and staff) see them: contact details, never staff notes."""
    return {
        "id": a.id,
        "full_name": a.full_name,
        "graduation_year": a.graduation_year,
        "programme": a.programme,
        "current_company": a.current_company,
        "current_designation": a.current_designation,
        "industry": a.industry,
        "city": a.city,
        "email": a.email,
        "phone": a.phone,
        "linkedin_url": a.linkedin_url,
    }


def _upcoming(db: Session, assignment_ids: list[str], now: datetime):
    """Scheduled sessions at or after now, soonest first."""
    return (
        _q(db, MentoringSession)
        .where(
            MentoringSession.assignment_id.in_(assignment_ids),
            MentoringSession.status == "scheduled",
            MentoringSession.scheduled_at >= now,
        )
        .order_by(MentoringSession.scheduled_at, MentoringSession.id)
    )


def _next_sessions(db: Session, assignment_ids: list[str]) -> dict[str, datetime]:
    if not assignment_ids:
        return {}
    out: dict[str, datetime] = {}
    for s in db.scalars(_upcoming(db, assignment_ids, clock())):
        out.setdefault(s.assignment_id, s.scheduled_at)
    return out


def _mentors(db: Session, mentor_ids: set[str]) -> dict[str, Alumnus]:
    if not mentor_ids:
        return {}
    return {a.id: a for a in db.scalars(_q(db, Alumnus).where(Alumnus.id.in_(mentor_ids)))}


def assignment_dict(x: Assignment, mentor: Alumnus, next_session_at: datetime | None) -> dict:
    return {
        "id": x.id,
        "organisation_id": x.organisation_id,
        "status": x.status,
        "mentor_id": x.mentor_id,
        "student_id": x.student_id,
        "student_name": x.student_name,
        "started_on": _iso(x.started_on),
        "focus": x.focus,
        "mentor": mentor_card(mentor),
        "ended_on": _iso(x.ended_on),
        "end_reason": x.end_reason,
        "assigned_by": x.assigned_by,
        "next_session_at": _iso(next_session_at),
    }


def _render_assignments(db: Session, rows: list[Assignment]) -> list[dict]:
    mentors = _mentors(db, {x.mentor_id for x in rows})
    nexts = _next_sessions(db, [x.id for x in rows if x.status == "active"])
    return [assignment_dict(x, mentors[x.mentor_id], nexts.get(x.id)) for x in rows]


def list_assignments(db: Session, filters: dict, cursor: str | None, limit: int) -> dict:
    """Active first, then newest."""
    q = _q(db, Assignment)
    if filters.get("status"):
        q = q.where(Assignment.status == filters["status"])
    if filters.get("mentor_id"):
        q = q.where(Assignment.mentor_id == filters["mentor_id"])
    if filters.get("student_id"):
        q = q.where(Assignment.student_id == filters["student_id"])  # scoped: (organisation_id, student_id)
    q = q.order_by(
        case((Assignment.status == "active", 0), else_=1),
        Assignment.created_at.desc(),
        Assignment.id.desc(),
    )
    page = _page(db, q, cursor, limit, lambda x: x)
    page["items"] = _render_assignments(db, page["items"])
    return page


def get_assignment(db: Session, assignment_id: str) -> dict:
    return _render_assignments(db, [_get(db, Assignment, assignment_id, "assignment")])[0]


def _active_for_student(db: Session, student_id: str) -> Assignment | None:
    """The student's active assignment in the caller's organisation: always (organisation_id, student_id)."""
    return db.scalar(_q(db, Assignment).where(Assignment.student_id == student_id, Assignment.status == "active"))


def start_assignment(db: Session, actor: Actor, body: dict) -> dict:
    """Assign an active alumnus flagged as a mentor to a student who has no active mentor. The mentor row is locked,
    so archiving the mentor or clearing their flag waits for this to finish; the partial unique index answers a
    second active assignment for the same student made concurrently."""
    mentor = _get(db, Alumnus, body["mentor_id"], "mentor", lock=True)
    if mentor.status == "archived":
        raise conflict("alumnus_archived", "an archived alumnus is not assigned")
    if not mentor.is_mentor:
        raise conflict("not_a_mentor", "the alumnus is not flagged as a mentor")
    started = _rule(rules.started_on, body.get("started_on"), business_today())
    student_id = body["student_id"]
    if _active_for_student(db, student_id) is not None:
        raise conflict("student_already_assigned", "the student already has an active mentor")
    x = Assignment(
        organisation_id=actor.organisation_id,
        mentor_id=mentor.id,
        student_id=student_id,
        student_name=rules.optional_text(body.get("student_name")),
        started_on=started,
        status="active",
        focus=rules.optional_text(body.get("focus")),
        assigned_by=actor.user_id,
        created_at=clock(),
    )
    db.add(x)
    try:
        _audit(db, actor, "assignment.started", "assignment", x)
    except IntegrityError as e:
        db.rollback()
        raise conflict("student_already_assigned", "the student already has an active mentor") from e
    _publish(
        db,
        actor,
        "mentoring-assignment.started",
        {"assignment_id": x.id, "mentor_id": x.mentor_id, "student_id": x.student_id, "started_on": _iso(started)},
    )
    db.commit()
    return assignment_dict(x, mentor, None)


def _cancel(db: Session, actor: Actor, s: MentoringSession, x: Assignment, reason: str | None) -> None:
    s.status, s.cancel_reason = "cancelled", reason
    _audit(db, actor, "session.cancelled", "session", s)
    _publish(
        db,
        actor,
        "mentoring-session.cancelled",
        {"session_id": s.id, "assignment_id": x.id, "student_id": x.student_id},
    )


def end_assignment(db: Session, actor: Actor, assignment_id: str, body: dict) -> dict:
    """End an active assignment on a date between its start and today (A7); its scheduled sessions are cancelled."""
    x = _get(db, Assignment, assignment_id, "assignment", lock=True)
    if x.status != "active":
        raise conflict("assignment_not_active", "the assignment has already ended")
    ended = _rule(rules.ended_on, body.get("ended_on"), x.started_on, business_today())
    x.status, x.ended_on, x.end_reason = "ended", ended, rules.optional_text(body.get("reason"))
    scheduled = _q(db, MentoringSession).where(
        MentoringSession.assignment_id == x.id, MentoringSession.status == "scheduled"
    )
    for s in db.scalars(scheduled.order_by(MentoringSession.scheduled_at, MentoringSession.id).with_for_update()):
        _cancel(db, actor, s, x, ENDED_BY_ASSIGNMENT)
    _audit(db, actor, "assignment.ended", "assignment", x)
    _publish(
        db,
        actor,
        "mentoring-assignment.ended",
        {"assignment_id": x.id, "mentor_id": x.mentor_id, "student_id": x.student_id, "ended_on": _iso(ended)},
    )
    db.commit()
    mentor = _get(db, Alumnus, x.mentor_id, "mentor")
    return assignment_dict(x, mentor, None)


# ---------------------------------------------------------------- sessions


def session_dict(s: MentoringSession) -> dict:
    return {
        "id": s.id,
        "organisation_id": s.organisation_id,
        "assignment_id": s.assignment_id,
        "status": s.status,
        "scheduled_at": _iso(s.scheduled_at),
        "duration_minutes": s.duration_minutes,
        "mode": s.mode,
        "location": s.location,
        "topic": s.topic,
        "notes": s.notes,
        "cancel_reason": s.cancel_reason,
        "created_by": s.created_by,
    }


def my_session_dict(s: MentoringSession) -> dict:
    """A session as the mentee sees it: no staff notes, no cancel reason."""
    return {
        "id": s.id,
        "scheduled_at": _iso(s.scheduled_at),
        "duration_minutes": s.duration_minutes,
        "mode": s.mode,
        "location": s.location,
        "topic": s.topic,
    }


def list_sessions(db: Session, assignment_id: str, limit: int) -> list[dict]:
    """Every session of the assignment, soonest first, at most `limit`."""
    x = _get(db, Assignment, assignment_id, "assignment")
    q = (
        _q(db, MentoringSession)
        .where(MentoringSession.assignment_id == x.id)
        .order_by(MentoringSession.scheduled_at, MentoringSession.id)
        .limit(limit)
    )
    return [session_dict(s) for s in db.scalars(q)]


def _session_values(s: MentoringSession, x: Assignment, body: dict) -> None:
    """Every field of SessionInput; a field left out is cleared."""
    s.scheduled_at = _rule(rules.scheduled_at, body["scheduled_at"], x.started_on, business_date)
    s.duration_minutes = _rule(rules.duration, body.get("duration_minutes"))
    s.mode = body["mode"]
    s.location = rules.optional_text(body.get("location"))
    s.topic = rules.optional_text(body.get("topic"))


def schedule_session(db: Session, actor: Actor, assignment_id: str, body: dict) -> dict:
    x = _get(db, Assignment, assignment_id, "assignment", lock=True)
    if x.status != "active":
        raise conflict("assignment_not_active", "an ended assignment gets no new sessions")
    s = MentoringSession(
        organisation_id=actor.organisation_id,
        assignment_id=x.id,
        status="scheduled",
        created_by=actor.user_id,
        created_at=clock(),
    )
    _session_values(s, x, body)
    db.add(s)
    _audit(db, actor, "session.scheduled", "session", s)
    _publish(
        db,
        actor,
        "mentoring-session.scheduled",
        {
            "session_id": s.id,
            "assignment_id": x.id,
            "student_id": x.student_id,
            "scheduled_at": _iso(s.scheduled_at),
            "mode": s.mode,
        },
    )
    db.commit()
    return session_dict(s)


def _scheduled_session(db: Session, session_id: str) -> tuple[MentoringSession, Assignment]:
    s = _get(db, MentoringSession, session_id, "session", lock=True)
    if s.status != "scheduled":
        raise conflict("session_not_scheduled", f"the session is {s.status}; only a scheduled session changes")
    x = _get(db, Assignment, s.assignment_id, "assignment")
    return s, x


def update_session(db: Session, actor: Actor, session_id: str, body: dict) -> dict:
    """Edit or move a scheduled session; a move publishes mentoring-session.rescheduled with the new time."""
    s, x = _scheduled_session(db, session_id)
    before = rules.as_utc(s.scheduled_at)
    _session_values(s, x, body)
    moved = s.scheduled_at != before
    _audit(db, actor, "session.rescheduled" if moved else "session.updated", "session", s)
    if moved:
        _publish(
            db,
            actor,
            "mentoring-session.rescheduled",
            {
                "session_id": s.id,
                "assignment_id": x.id,
                "student_id": x.student_id,
                "scheduled_at": _iso(s.scheduled_at),
            },
        )
    db.commit()
    return session_dict(s)


def complete_session(db: Session, actor: Actor, session_id: str, notes: str | None) -> dict:
    s, x = _scheduled_session(db, session_id)
    s.status, s.notes = "completed", rules.optional_text(notes)
    _audit(db, actor, "session.completed", "session", s)
    _publish(
        db,
        actor,
        "mentoring-session.completed",
        {"session_id": s.id, "assignment_id": x.id, "student_id": x.student_id},
    )
    db.commit()
    return session_dict(s)


def cancel_session(db: Session, actor: Actor, session_id: str, reason: str | None) -> dict:
    s, x = _scheduled_session(db, session_id)
    _cancel(db, actor, s, x, rules.optional_text(reason))
    db.commit()
    return session_dict(s)


# ---------------------------------------------------------------- the student's own


def my_mentoring(db: Session, actor: Actor) -> dict:
    """The caller's active assignment in their own organisation, looked up by (organisation_id, student_id), with the
    mentor's card and the next five upcoming sessions. assignment is null without an active mentor; an ended
    assignment is never shown (A5)."""
    x = _active_for_student(db, actor.user_id)
    if x is None:
        return {"assignment": None, "upcoming_sessions": []}
    mentor = _get(db, Alumnus, x.mentor_id, "mentor")
    sessions = db.scalars(_upcoming(db, [x.id], clock()).limit(MY_UPCOMING))
    return {
        "assignment": {
            "id": x.id,
            "started_on": _iso(x.started_on),
            "focus": x.focus,
            "mentor": mentor_card(mentor),
        },
        "upcoming_sessions": [my_session_dict(s) for s in sessions],
    }
