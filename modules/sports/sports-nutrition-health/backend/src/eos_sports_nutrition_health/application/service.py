"""Use cases of sports-nutrition-health (docs/prd.md, contracts/openapi.yaml). Each one applies the domain rules,
changes state, publishes the matching event of contracts/events.yaml through eos_core.events.publish and writes an
audit entry (`_audit`) in the same transaction, then commits once. Permission keys are checked by the API layer
(api/deps.require); which rows and fields a caller may see is decided here.

Confidentiality (PRD §5):
- Health records need health-record:read, which only medical roles hold.
- An injury's clinical_notes are returned only to callers with health-record:read; coaches and athletes see the
  injury, its status and expected return.
- An appointment's notes are clinical: returned to and written by medical roles, and by a nutritionist only for
  nutrition appointments. An injury's clinical_notes are written only with health-record:write.
- Events carry ids, statuses and dates only; audit entries never copy clinical or free-text fields (NOT_RECORDED).

Athletes see only their own plans, injuries and appointments: a caller whose only access comes from an athlete role
is `self_only`, and reads are narrowed to the athlete ids linked to their user (AthleteLink, learnt from
athlete-performance.athlete.registered in consumers.py). Until that event reaches this module, an athlete sees
nothing, never someone else's rows.

Known dependencies, not worked around here:
- The audit SDK does not exist (packages/sdk is empty). Until it does, sports_nutrition_health_audit_entry stands in
  for it, shaped like platform/audit's Record.
- Athlete ids are athlete-performance's and are not checked here: this module has no copy of the athlete list."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from eos_core import events
from eos_core.db import new_id, utcnow
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import RuleViolationError
from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from ..infrastructure.models import Appointment, AuditEntry, HealthRecord, Injury, Plan, PlanReview, as_utc, iso

MODULE = "sports-nutrition-health"
PLAN_READ = f"{MODULE}:plan:read"
PLAN_WRITE = f"{MODULE}:plan:write"
PLAN_REVIEW = f"{MODULE}:plan:review"
HEALTH_READ = f"{MODULE}:health-record:read"
HEALTH_WRITE = f"{MODULE}:health-record:write"
INJURY_READ = f"{MODULE}:injury:read"
INJURY_WRITE = f"{MODULE}:injury:write"
APPOINTMENT_READ = f"{MODULE}:appointment:read"
APPOINTMENT_WRITE = f"{MODULE}:appointment:write"

# Roles whose access is limited to the caller's own athlete records.
ATHLETE_ROLES = frozenset({"athlete", "sports-nutrition-health-athlete"})
# Clinical and free-text fields stay out of audit before/after; a change is still named in the summary.
NOT_RECORDED = frozenset(
    {"title", "details", "clinical_notes", "notes", "body_part", "injury_type", "meals", "body_weight_kg"}
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


def _forbidden(message: str) -> ServiceError:
    return ServiceError(403, "forbidden", message)


def _may_see_notes(actor: Actor, appointment_type: str) -> bool:
    """Appointment notes are clinical: medical roles see them; a nutritionist sees those of nutrition sessions."""
    return actor.can(HEALTH_READ) or (appointment_type == "nutrition" and actor.can(PLAN_WRITE))


def _may_write_notes(actor: Actor, appointment_type: str) -> bool:
    return actor.can(HEALTH_WRITE) or (appointment_type == "nutrition" and actor.can(PLAN_WRITE))


def _check_clinical_notes(actor: Actor, data: dict, *, partial: bool) -> None:
    """Writing or clearing an injury's clinical notes is a health-record change: refused without health-record:write,
    which is also what it takes to read them. A new injury carries every field, so there only actual notes count; an
    update carries only the fields sent, so sending the field at all (null included) counts."""
    sent = "clinical_notes" in data if partial else data.get("clinical_notes") is not None
    if sent and not actor.can(HEALTH_WRITE):
        raise _forbidden(f"clinical_notes require {HEALTH_WRITE}")


def _rules(fn, *args) -> None:
    try:
        fn(*args)
    except RuleViolationError as v:
        raise _invalid(v.code, v.message) from v


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


def _audit(db: Session, actor: Actor, action: str, entity_type: str, row, *, before=None, after=None) -> None:
    """One audit record per state change, in the same transaction. `before` and `after` are the changed fields only
    (None for a creation's `before`)."""
    db.flush()
    changed = sorted(after) if before is not None and after else []
    summary = f"{entity_type.replace('_', ' ')} {row.id} {action}" + (f": {', '.join(changed)}" if changed else "")

    def recorded(fields):
        return None if fields is None else {k: _json(v) for k, v in fields.items() if k not in NOT_RECORDED}

    db.add(
        AuditEntry(
            organisation_id=actor.organisation_id,
            client_token=new_id(),
            actor=actor.user_id,
            action=f"{entity_type}.{action}",
            entity_type=entity_type,
            entity_id=row.id,
            summary=summary[:300],
            before=recorded(before),
            after=recorded(after),
            occurred_at=clock(),
        )
    )


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


def _day(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


# ---------------------------------------------------------------- who may see which rows


def _own_athletes(db: Session, actor: Actor) -> set[str] | None:
    """None when the caller sees the organisation; otherwise the athlete ids that are theirs (possibly none)."""
    return repo.athletes_of_user(db, actor.user_id) if actor.self_only else None


def _narrow(db: Session, actor: Actor, q, model, athlete_id: str | None):
    own = _own_athletes(db, actor)
    if own is not None:
        q = q.where(model.athlete_id.in_(own))
    if athlete_id:
        q = q.where(model.athlete_id == athlete_id)
    return q


def _visible(db: Session, actor: Actor, model, row_id: str, what: str):
    """The row, if the caller may see it: another athlete's row is 404, so its id is not even confirmed."""
    row = repo.get(db, model, row_id)
    own = _own_athletes(db, actor) if row is not None else None
    if row is None or (own is not None and row.athlete_id not in own):
        raise _not_found(what)
    return row


# ---------------------------------------------------------------- serialisers


def plan_out(p: Plan) -> dict:
    return _clean(
        {
            "id": p.id,
            "organisation_id": p.organisation_id,
            "nutritionist_id": p.nutritionist_id,
            "created_at": iso(p.created_at),
            "updated_at": iso(p.updated_at),
            "athlete_id": p.athlete_id,
            "title": p.title,
            "goal": p.goal,
            "daily_calories": p.daily_calories,
            "protein_g": p.protein_g,
            "carbohydrate_g": p.carbohydrate_g,
            "fat_g": p.fat_g,
            "meals": [dict(m) for m in p.meals or []],
            "start_date": iso(p.start_date),
            "end_date": iso(p.end_date),
            "review_due_on": iso(p.review_due_on),
            "status": p.status,
        }
    )


def review_out(r: PlanReview) -> dict:
    return _clean(
        {
            "id": r.id,
            "organisation_id": r.organisation_id,
            "reviewed_by": r.reviewed_by,
            "created_at": iso(r.created_at),
            "updated_at": iso(r.updated_at),
            "reviewed_on": iso(r.reviewed_on),
            "outcome": r.outcome,
            "body_weight_kg": r.body_weight_kg,
            "next_review_on": iso(r.next_review_on),
            "notes": r.notes,
        }
    )


def health_record_out(h: HealthRecord) -> dict:
    return _clean(
        {
            "id": h.id,
            "organisation_id": h.organisation_id,
            "recorded_by": h.recorded_by,
            "created_at": iso(h.created_at),
            "updated_at": iso(h.updated_at),
            "athlete_id": h.athlete_id,
            "record_type": h.record_type,
            "title": h.title,
            "details": h.details,
            "recorded_on": iso(h.recorded_on),
        }
    )


def injury_out(i: Injury, actor: Actor) -> dict:
    return _clean(
        {
            "id": i.id,
            "organisation_id": i.organisation_id,
            "reported_by": i.reported_by,
            "created_at": iso(i.created_at),
            "updated_at": iso(i.updated_at),
            "athlete_id": i.athlete_id,
            "body_part": i.body_part,
            "injury_type": i.injury_type,
            "severity": i.severity,
            "occurred_on": iso(i.occurred_on),
            "context": i.context,
            "status": i.status,
            "expected_return_on": iso(i.expected_return_on),
            "clinical_notes": i.clinical_notes if actor.can(HEALTH_READ) else None,
        }
    )


def appointment_out(a: Appointment, actor: Actor) -> dict:
    return _clean(
        {
            "id": a.id,
            "organisation_id": a.organisation_id,
            "created_at": iso(a.created_at),
            "updated_at": iso(a.updated_at),
            "athlete_id": a.athlete_id,
            "practitioner_id": a.practitioner_id,
            "appointment_type": a.appointment_type,
            "injury_id": a.injury_id,
            "scheduled_at": iso(a.scheduled_at),
            "duration_minutes": a.duration_minutes,
            "status": a.status,
            "notes": a.notes if _may_see_notes(actor, a.appointment_type) else None,
        }
    )


# ---------------------------------------------------------------- nutrition plans


def list_plans(db: Session, actor: Actor, filters: dict, limit: int, offset: int) -> dict:
    q = _narrow(db, actor, repo.query(db, Plan), Plan, filters.get("athlete_id"))
    if filters.get("status"):
        q = q.where(Plan.status == filters["status"])
    if filters.get("review_due_before"):
        q = q.where(
            Plan.review_due_on.is_not(None),
            Plan.review_due_on <= filters["review_due_before"],
            Plan.status.not_in(rules.CLOSED_PLAN),
        )
    rows, total = repo.page(db, q, (Plan.start_date.desc(), Plan.created_at.desc(), Plan.id), limit, offset)
    return _page([plan_out(p) for p in rows], total)


def _check_plan_dates(values: dict) -> None:
    _rules(rules.not_before, values.get("end_date"), values.get("start_date"), "end_date", "start_date")
    _rules(rules.not_before, values.get("review_due_on"), values.get("start_date"), "review_due_on", "start_date")


def create_plan(db: Session, actor: Actor, data: dict) -> dict:
    _check_plan_dates(data)
    p = Plan(organisation_id=actor.organisation_id, nutritionist_id=actor.user_id, **data)
    db.add(p)
    _audit(db, actor, "created", "plan", p, after=data)
    _publish(
        db,
        actor,
        "plan.created",
        {
            "plan_id": p.id,
            "athlete_id": p.athlete_id,
            "goal": p.goal,
            "start_date": iso(p.start_date),
            "review_due_on": iso(p.review_due_on),
        },
    )
    db.commit()
    return plan_out(p)


def get_plan(db: Session, actor: Actor, plan_id: str) -> dict:
    return plan_out(_visible(db, actor, Plan, plan_id, "nutrition plan"))


def update_plan(db: Session, actor: Actor, plan_id: str, data: dict) -> dict:
    """A closed plan (completed or archived) only moves between those two; it is never reopened."""
    p = _get_plan(db, plan_id)
    if p.status in rules.CLOSED_PLAN and (
        set(data) - {"status"} or data.get("status", p.status) not in rules.CLOSED_PLAN
    ):
        _rules(rules.check_plan_open, p.status)
    if data.get("status") in rules.CLOSED_PLAN:
        data = {**data, "review_due_on": None}  # a closed plan is never due for review
    keys = ("start_date", "end_date", "review_due_on")
    _check_plan_dates({k: data.get(k, getattr(p, k)) for k in keys})
    before, after = _apply(p, data)
    if after:
        _audit(db, actor, "updated", "plan", p, before=before, after=after)
        db.commit()
    return plan_out(p)


def _get_plan(db: Session, plan_id: str) -> Plan:
    p = repo.get(db, Plan, plan_id)
    if p is None:
        raise _not_found("nutrition plan")
    return p


def list_reviews(db: Session, actor: Actor, plan_id: str, limit: int, offset: int) -> dict:
    p = _visible(db, actor, Plan, plan_id, "nutrition plan")
    q = repo.query(db, PlanReview).where(PlanReview.plan_id == p.id)
    order = (PlanReview.reviewed_on.desc(), PlanReview.created_at.desc(), PlanReview.id)
    rows, total = repo.page(db, q, order, limit, offset)
    return _page([review_out(r) for r in rows], total)


def record_review(db: Session, actor: Actor, plan_id: str, data: dict) -> dict:
    p = _get_plan(db, plan_id)
    _rules(rules.check_reviewable, p.status)
    _rules(rules.not_in_future, data["reviewed_on"], clock(), "reviewed_on")
    _rules(rules.not_before, data["reviewed_on"], p.start_date, "reviewed_on", "the plan's start_date")
    _rules(rules.not_before, data.get("next_review_on"), data["reviewed_on"], "next_review_on", "reviewed_on")
    r = PlanReview(
        organisation_id=actor.organisation_id, plan_id=p.id, reviewed_by=actor.user_id, created_at=clock(), **data
    )
    db.add(r)
    _audit(db, actor, "recorded", "plan_review", r, after=data)
    before, after = _apply(p, rules.plan_after_review(data["outcome"], data.get("next_review_on")))
    if after:
        _audit(db, actor, "reviewed", "plan", p, before=before, after=after)
    _publish(
        db,
        actor,
        "plan.reviewed",
        {
            "plan_id": p.id,
            "athlete_id": p.athlete_id,
            "outcome": r.outcome,
            "next_review_on": iso(r.next_review_on),
        },
    )
    db.commit()
    return review_out(r)


# ---------------------------------------------------------------- health records


def list_health_records(db: Session, actor: Actor, filters: dict, limit: int, offset: int) -> dict:
    q = _narrow(db, actor, repo.query(db, HealthRecord), HealthRecord, filters.get("athlete_id"))
    if filters.get("record_type"):
        q = q.where(HealthRecord.record_type == filters["record_type"])
    order = (HealthRecord.recorded_on.desc(), HealthRecord.created_at.desc(), HealthRecord.id)
    rows, total = repo.page(db, q, order, limit, offset)
    return _page([health_record_out(h) for h in rows], total)


def create_health_record(db: Session, actor: Actor, data: dict) -> dict:
    _rules(rules.not_in_future, data["recorded_on"], clock(), "recorded_on")
    h = HealthRecord(organisation_id=actor.organisation_id, recorded_by=actor.user_id, **data)
    db.add(h)
    _audit(db, actor, "created", "health_record", h, after=data)
    db.commit()
    return health_record_out(h)


def get_health_record(db: Session, actor: Actor, record_id: str) -> dict:
    return health_record_out(_visible(db, actor, HealthRecord, record_id, "health record"))


def update_health_record(db: Session, actor: Actor, record_id: str, data: dict) -> dict:
    h = repo.get(db, HealthRecord, record_id)
    if h is None:
        raise _not_found("health record")
    if "recorded_on" in data:
        _rules(rules.not_in_future, data["recorded_on"], clock(), "recorded_on")
    before, after = _apply(h, data)
    if after:
        _audit(db, actor, "updated", "health_record", h, before=before, after=after)
        db.commit()
    return health_record_out(h)


# ---------------------------------------------------------------- injuries


def list_injuries(db: Session, actor: Actor, filters: dict, limit: int, offset: int) -> dict:
    q = _narrow(db, actor, repo.query(db, Injury), Injury, filters.get("athlete_id"))
    for name in ("status", "severity"):
        if filters.get(name):
            q = q.where(getattr(Injury, name) == filters[name])
    rows, total = repo.page(db, q, (Injury.occurred_on.desc(), Injury.created_at.desc(), Injury.id), limit, offset)
    return _page([injury_out(i, actor) for i in rows], total)


def _check_injury(values: dict, now: datetime) -> None:
    _rules(rules.not_in_future, values["occurred_on"], now, "occurred_on")
    _rules(
        rules.not_before, values.get("expected_return_on"), values["occurred_on"], "expected_return_on", "occurred_on"
    )


def _publish_resolved(db: Session, actor: Actor, i: Injury) -> None:
    payload = {"injury_id": i.id, "athlete_id": i.athlete_id, "resolved_on": iso(i.resolved_on)}
    _publish(db, actor, "injury.resolved", payload)


def report_injury(db: Session, actor: Actor, data: dict) -> dict:
    _check_clinical_notes(actor, data, partial=False)
    now = clock()
    _check_injury(data, now)
    i = Injury(organisation_id=actor.organisation_id, reported_by=actor.user_id, **data)
    if i.status == "resolved":
        i.resolved_on = now.date()
    db.add(i)
    _audit(db, actor, "reported", "injury", i, after=data)
    _publish(
        db,
        actor,
        "injury.reported",
        {
            "injury_id": i.id,
            "athlete_id": i.athlete_id,
            "severity": i.severity,
            "occurred_on": iso(i.occurred_on),
            "expected_return_on": iso(i.expected_return_on),
        },
    )
    if i.status == "resolved":
        _publish_resolved(db, actor, i)
    db.commit()
    return injury_out(i, actor)


def get_injury(db: Session, actor: Actor, injury_id: str) -> dict:
    return injury_out(_visible(db, actor, Injury, injury_id, "injury"), actor)


def update_injury(db: Session, actor: Actor, injury_id: str, data: dict) -> dict:
    """Resolving sets resolved_on to today and publishes injury.resolved; reopening clears it."""
    i = repo.get(db, Injury, injury_id)
    if i is None:
        raise _not_found("injury")
    _check_clinical_notes(actor, data, partial=True)
    now = clock()
    keys = ("occurred_on", "expected_return_on")
    _check_injury({k: data.get(k, getattr(i, k)) for k in keys}, now)
    was = i.status
    before, after = _apply(i, data)
    if not after:
        return injury_out(i, actor)
    if i.status == "resolved" and was != "resolved":
        i.resolved_on = now.date()
    elif i.status != "resolved" and was == "resolved":
        i.resolved_on = None
    _audit(db, actor, "updated", "injury", i, before=before, after=after)
    if i.status == "resolved" and was != "resolved":
        _publish_resolved(db, actor, i)
    db.commit()
    return injury_out(i, actor)


# ---------------------------------------------------------------- appointments


def list_appointments(db: Session, actor: Actor, filters: dict, limit: int, offset: int) -> dict:
    q = _narrow(db, actor, repo.query(db, Appointment), Appointment, filters.get("athlete_id"))
    for name in ("practitioner_id", "status"):
        if filters.get(name):
            q = q.where(getattr(Appointment, name) == filters[name])
    if filters.get("on"):
        start, end = _day(filters["on"])
        q = q.where(Appointment.scheduled_at >= start, Appointment.scheduled_at < end)
    rows, total = repo.page(db, q, (Appointment.scheduled_at, Appointment.id), limit, offset)
    return _page([appointment_out(a, actor) for a in rows], total)


def _check_injury_link(db: Session, injury_id: str | None, athlete_id: str) -> None:
    if injury_id is None:
        return
    injury = repo.get(db, Injury, injury_id)
    if injury is None:
        raise _invalid("unknown_injury", f"injury {injury_id} not found in your organisation")
    if injury.athlete_id != athlete_id:
        raise _invalid("injury_of_another_athlete", "the injury belongs to a different athlete")


def _publish_completed(db: Session, actor: Actor, a: Appointment) -> None:
    payload = {
        "appointment_id": a.id,
        "athlete_id": a.athlete_id,
        "appointment_type": a.appointment_type,
        "completed_at": iso(a.completed_at),
    }
    _publish(db, actor, "appointment.completed", payload)


def schedule_appointment(db: Session, actor: Actor, data: dict) -> dict:
    now = clock()
    _rules(rules.check_new_appointment, data["status"])
    if data.get("notes") is not None and not _may_write_notes(actor, data["appointment_type"]):
        raise _forbidden(f"notes on a {data['appointment_type']} appointment require {HEALTH_WRITE}")
    _check_injury_link(db, data.get("injury_id"), data["athlete_id"])
    if data["status"] == "completed":
        _rules(rules.check_held, data["scheduled_at"], now)
    else:
        _rules(rules.check_upcoming, data["scheduled_at"], now)
    if data.get("duration_minutes") is None:
        data = {**data, "duration_minutes": load_settings().default_appointment_minutes}
    a = Appointment(organisation_id=actor.organisation_id, **data)
    if a.status == "completed":
        a.completed_at = now
    db.add(a)
    _audit(db, actor, "scheduled", "appointment", a, after=data)
    if a.status == "scheduled":
        payload = {
            "appointment_id": a.id,
            "athlete_id": a.athlete_id,
            "practitioner_id": a.practitioner_id,
            "appointment_type": a.appointment_type,
            "scheduled_at": iso(a.scheduled_at),
        }
        _publish(db, actor, "appointment.scheduled", payload)
    else:
        _publish_completed(db, actor, a)
    db.commit()
    return appointment_out(a, actor)


def get_appointment(db: Session, actor: Actor, appointment_id: str) -> dict:
    return appointment_out(_visible(db, actor, Appointment, appointment_id, "appointment"), actor)


def update_appointment(db: Session, actor: Actor, appointment_id: str, data: dict) -> dict:
    a = repo.get(db, Appointment, appointment_id)
    if a is None:
        raise _not_found("appointment")
    now = clock()
    changes = {k: v for k, v in data.items() if (as_utc(getattr(a, k)) if k == "scheduled_at" else getattr(a, k)) != v}
    _rules(rules.check_appointment_change, a.status, changes)
    if "notes" in changes and not _may_write_notes(actor, data.get("appointment_type", a.appointment_type)):
        raise _forbidden(f"notes on a {a.appointment_type} appointment require {HEALTH_WRITE}")
    if "injury_id" in changes or "athlete_id" in changes:
        _check_injury_link(db, data.get("injury_id", a.injury_id), data.get("athlete_id", a.athlete_id))
    when = data.get("scheduled_at", as_utc(a.scheduled_at))
    if changes.get("status") in ("completed", "no_show"):
        _rules(rules.check_held, when, now, changes["status"])
    elif "scheduled_at" in changes and changes.get("status", a.status) == "scheduled":
        _rules(rules.check_upcoming, when, now)
    before, after = _apply(a, changes)
    if not after:
        return appointment_out(a, actor)
    if after.get("status") == "completed":
        a.completed_at = now
    _audit(db, actor, "updated", "appointment", a, before=before, after=after)
    if after.get("status") == "completed":
        _publish_completed(db, actor, a)
    db.commit()
    return appointment_out(a, actor)
