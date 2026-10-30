"""Use cases of skill-progress (docs/prd.md, contracts/openapi.yaml). Each one applies the domain rules, changes state,
publishes the matching event of contracts/events.yaml through eos_core.events.publish and writes an audit entry
(`_audit`) in the same transaction, then commits once. Permission keys are checked by the API layer
(api/deps.require); which rows a caller may see is decided here.

Learners see only their own records: a caller whose only skill-progress access comes from a learner role (a role
whose dashboard layout extends `student`, such as musician or medical-student) is `self_only`, and every
learner-level read is narrowed to the learner id that is their user id. Evaluators, coordinators and administrators
with the read permission see the whole organisation.

Decisions the contracts left open (docs/prd.md section 9), made here and described in the README:
- Q5 milestones: per skill, the first counted assessment is the baseline; a later one whose level ranks above every
  earlier one advances the level; the first one at the scale's highest level achieves the milestone. Both publish
  skill-progress.milestone.achieved.
- Q6 progress is recomputed (skill-progress.progress.updated) when an assessment is recorded or voided.
- Q8 overall_score and level_achieved are supplied by the evaluator; the rules check they are consistent with the
  skill's scale, not how they were computed.

Known dependencies, not worked around here:
- The audit SDK does not exist (packages/sdk is empty). Until it does, skill_progress_audit_entry stands in for it,
  shaped like platform/audit's Record, as athlete-performance's, hostel's and helpdesk's audit tables are."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from eos_core import events
from eos_core.db import new_id, utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import RuleViolationError, Scored
from ..infrastructure import repository as repo
from ..infrastructure.models import Assessment, AuditEntry, Framework, Rubric, Skill, as_utc, iso

MODULE = "skill-progress"
FRAMEWORK_READ = f"{MODULE}:framework:read"
FRAMEWORK_WRITE = f"{MODULE}:framework:write"
ASSESSMENT_READ = f"{MODULE}:assessment:read"
ASSESSMENT_RECORD = f"{MODULE}:assessment:record"
ASSESSMENT_APPROVE = f"{MODULE}:assessment:approve"
ASSESSMENT_DELETE = f"{MODULE}:assessment:delete"
PROGRESS_READ = f"{MODULE}:progress:read"

# The base role every learner role's dashboard layout extends (platform/identity/config/dashboards/student.yaml).
LEARNER_BASE_ROLE = "student"
# Free text stays out of audit before/after; a change is still named in the summary. Scales and criteria carry
# descriptions, and scores carry notes, so they are named but not copied.
NOT_RECORDED = frozenset({"description", "feedback", "evidence_urls", "criterion_scores", "criteria", "level_scale"})


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


@contextmanager
def _rules():
    """`with _rules():` turns a domain refusal into a 400 with the rule's code."""
    try:
        yield
    except RuleViolationError as v:
        raise ServiceError(400, v.code, v.message) from v


# ---------------------------------------------------------------- helpers


def _clean(d: dict) -> dict:
    """Optional contract fields are left out rather than sent as null."""
    return {k: v for k, v in d.items() if v is not None}


def _publish(db: Session, actor: Actor, name: str, payload: dict) -> None:
    org = actor.organisation_id
    events.publish(db, f"{MODULE}.{name}", org, {"organisation_id": org, **payload}, actor=actor.user_id)


def _json(value):
    if isinstance(value, datetime):
        return iso(value)
    return value


def _audit(db: Session, actor: Actor, action: str, entity_type: str, row, *, before=None, after=None) -> None:
    """One audit record per state change, in the same transaction. `before` and `after` are the changed fields only
    (None for a creation's `before`)."""
    db.flush()
    changed = sorted(after) if before is not None and after else []
    summary = f"{entity_type} {row.id} {action}" + (f": {', '.join(changed)}" if changed else "")

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


def _commit(db: Session, duplicate_code: str, duplicate_message: str) -> None:
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


def _ref(db: Session, model, row_id: str, what: str):
    """A row a request body refers to; another organisation's ids are unknown here (400)."""
    row = repo.get(db, model, row_id)
    if row is None:
        raise _invalid(f"unknown_{what}", f"{what.replace('_', ' ')} {row_id} not found in your organisation")
    return row


def _apply(row, data: dict) -> tuple[dict, dict]:
    """Set the fields that change; return (before, after) of those fields only."""
    before, after = {}, {}
    for k, v in data.items():
        if getattr(row, k) != v:
            before[k], after[k] = getattr(row, k), v
            setattr(row, k, v)
    return before, after


def _page(items: list, total: int) -> dict:
    return {"items": items, "total": total}


def _instant(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def _framework_open(framework: Framework) -> None:
    if framework.status == "archived":
        raise _invalid("framework_archived", f"framework {framework.code} is archived")


# ---------------------------------------------------------------- serialisers


def framework_out(f: Framework) -> dict:
    return _clean(
        {
            "id": f.id,
            "organisation_id": f.organisation_id,
            "code": f.code,
            "title": f.title,
            "description": f.description,
            "status": f.status,
            "created_at": iso(f.created_at),
            "updated_at": iso(f.updated_at),
        }
    )


def skill_out(s: Skill) -> dict:
    return _clean(
        {
            "id": s.id,
            "organisation_id": s.organisation_id,
            "framework_id": s.framework_id,
            "parent_skill_id": s.parent_skill_id,
            "code": s.code,
            "title": s.title,
            "description": s.description,
            "category": s.category,
            "level_scale": s.level_scale,
            "created_at": iso(s.created_at),
        }
    )


def rubric_out(r: Rubric) -> dict:
    return _clean(
        {
            "id": r.id,
            "organisation_id": r.organisation_id,
            "skill_id": r.skill_id,
            "framework_id": r.framework_id,
            "title": r.title,
            "description": r.description,
            "criteria": [dict(c) for c in r.criteria or []],
            "created_at": iso(r.created_at),
        }
    )


def assessment_out(a: Assessment) -> dict:
    return _clean(
        {
            "id": a.id,
            "organisation_id": a.organisation_id,
            "learner_id": a.learner_id,
            "evaluator_id": a.evaluator_id,
            "skill_id": a.skill_id,
            "rubric_id": a.rubric_id,
            "assessed_at": iso(a.assessed_at),
            "criterion_scores": [dict(s) for s in a.criterion_scores or []],
            "overall_score": a.overall_score,
            "level_achieved": a.level_achieved,
            "feedback": a.feedback,
            "evidence_urls": list(a.evidence_urls or []),
            "status": a.status,
        }
    )


# ---------------------------------------------------------------- frameworks


def list_frameworks(db: Session, status: str | None, limit: int, offset: int) -> dict:
    q = repo.query(db, Framework)
    if status:
        q = q.where(Framework.status == status)
    rows, total = repo.page(db, q, (Framework.code, Framework.id), limit, offset)
    return _page([framework_out(f) for f in rows], total)


def create_framework(db: Session, actor: Actor, data: dict) -> dict:
    duplicate = f"a framework with code {data['code']!r} already exists"
    if repo.first_by(db, Framework, code=data["code"]):
        raise _invalid("duplicate_code", duplicate)
    f = Framework(organisation_id=actor.organisation_id, **data)
    db.add(f)
    _audit(db, actor, "created", "framework", f, after=data)
    _publish(db, actor, "framework.created", {"framework_id": f.id, "code": f.code, "title": f.title})
    _commit(db, "duplicate_code", duplicate)
    return framework_out(f)


def get_framework(db: Session, framework_id: str) -> dict:
    return framework_out(_get(db, Framework, framework_id, "framework"))


def update_framework(db: Session, actor: Actor, framework_id: str, data: dict) -> dict:
    f = _get(db, Framework, framework_id, "framework")
    if "status" in data:
        with _rules():
            rules.check_transition(rules.FRAMEWORK_TRANSITIONS, f.status, data["status"], "framework")
    before, after = _apply(f, data)
    if after:
        _audit(
            db, actor, "status_changed" if "status" in after else "updated", "framework", f, before=before, after=after
        )
        db.commit()
    return framework_out(f)


# ---------------------------------------------------------------- skills


def list_skills(db: Session, filters: dict, limit: int, offset: int) -> dict:
    q = repo.query(db, Skill)
    for name in ("framework_id", "category", "parent_skill_id"):
        if filters.get(name):
            q = q.where(getattr(Skill, name) == filters[name])
    rows, total = repo.page(db, q, (Skill.code, Skill.id), limit, offset)
    return _page([skill_out(s) for s in rows], total)


def create_skill(db: Session, actor: Actor, data: dict) -> dict:
    framework = _ref(db, Framework, data["framework_id"], "framework")
    _framework_open(framework)
    if data.get("parent_skill_id"):
        parent = _ref(db, Skill, data["parent_skill_id"], "parent_skill")
        if parent.framework_id != framework.id:
            raise _invalid("parent_in_other_framework", "the parent skill belongs to another framework")
    with _rules():
        rules.check_scale(data["level_scale"])
    duplicate = f"framework {framework.code} already has a skill with code {data['code']!r}"
    if repo.first_by(db, Skill, framework_id=framework.id, code=data["code"]):
        raise _invalid("duplicate_code", duplicate)
    s = Skill(organisation_id=actor.organisation_id, **data)
    db.add(s)
    _audit(db, actor, "created", "skill", s, after=data)
    _publish(
        db,
        actor,
        "skill.created",
        {"skill_id": s.id, "framework_id": s.framework_id, "code": s.code, "title": s.title},
    )
    _commit(db, "duplicate_code", duplicate)
    return skill_out(s)


def get_skill(db: Session, skill_id: str) -> dict:
    return skill_out(_get(db, Skill, skill_id, "skill"))


def update_skill(db: Session, actor: Actor, skill_id: str, data: dict) -> dict:
    """A changed scale applies to assessments recorded from now on; recorded ones keep the level they were given."""
    s = _get(db, Skill, skill_id, "skill")
    if "level_scale" in data:
        with _rules():
            rules.check_scale(data["level_scale"])
    before, after = _apply(s, data)
    if after:
        _audit(db, actor, "updated", "skill", s, before=before, after=after)
        db.commit()
    return skill_out(s)


# ---------------------------------------------------------------- rubrics


def list_rubrics(db: Session, skill_id: str | None, framework_id: str | None) -> dict:
    """Every matching rubric (the contract pages nothing here). A framework's rubrics include those of its skills."""
    q = repo.query(db, Rubric)
    if skill_id:
        q = q.where(Rubric.skill_id == skill_id)
    if framework_id:
        q = q.where(Rubric.framework_id == framework_id)
    rows = list(db.scalars(q.order_by(Rubric.title, Rubric.id)))
    return _page([rubric_out(r) for r in rows], len(rows))


def create_rubric(db: Session, actor: Actor, data: dict) -> dict:
    """For a skill (its framework_id is filled in) or for a whole framework; at least one of them."""
    if not data.get("skill_id") and not data.get("framework_id"):
        raise _invalid("target_required", "a rubric is for a skill or a framework: give skill_id or framework_id")
    framework_id = data.get("framework_id")
    if data.get("skill_id"):
        skill = _ref(db, Skill, data["skill_id"], "skill")
        if framework_id and framework_id != skill.framework_id:
            raise _invalid("skill_not_in_framework", "the skill does not belong to that framework")
        framework_id = skill.framework_id
    _framework_open(_ref(db, Framework, framework_id, "framework"))
    with _rules():
        rules.check_criteria(data["criteria"])
    r = Rubric(organisation_id=actor.organisation_id, **{**data, "framework_id": framework_id})
    db.add(r)
    _audit(db, actor, "created", "rubric", r, after={**data, "framework_id": framework_id})
    _publish(db, actor, "rubric.created", _clean({"rubric_id": r.id, "skill_id": r.skill_id, "title": r.title}))
    db.commit()
    return rubric_out(r)


def get_rubric(db: Session, rubric_id: str) -> dict:
    return rubric_out(_get(db, Rubric, rubric_id, "rubric"))


# ---------------------------------------------------------------- whose records a caller may see


def _learner_filter(actor: Actor, learner_id: str | None) -> str | None:
    """The learner a list is narrowed to. A self-only caller always gets their own (or one that matches nothing)."""
    if not actor.self_only:
        return learner_id
    if learner_id and learner_id != actor.user_id:
        return "-"  # no row has this id
    return actor.user_id


def _visible_learner(actor: Actor, learner_id: str) -> None:
    """A self-only caller reads only their own records: 404 otherwise, so other learners are not even confirmed."""
    if actor.self_only and learner_id != actor.user_id:
        raise _not_found("learner")


# ---------------------------------------------------------------- assessments


def list_assessments(db: Session, actor: Actor, filters: dict, limit: int, offset: int) -> dict:
    q = repo.query(db, Assessment)
    learner_id = _learner_filter(actor, filters.get("learner_id"))
    if learner_id:
        q = q.where(Assessment.learner_id == learner_id)
    for name in ("evaluator_id", "skill_id"):
        if filters.get(name):
            q = q.where(getattr(Assessment, name) == filters[name])
    if filters.get("from_date"):
        q = q.where(Assessment.assessed_at >= _instant(filters["from_date"]))
    if filters.get("to_date"):
        q = q.where(Assessment.assessed_at < _instant(filters["to_date"] + timedelta(days=1)))
    order = (Assessment.assessed_at.desc(), Assessment.created_at.desc(), Assessment.id)
    rows, total = repo.page(db, q, order, limit, offset)
    return _page([assessment_out(a) for a in rows], total)


def _scored(rows: list[Assessment]) -> list[Scored]:
    return [
        Scored(
            id=a.id,
            skill_id=a.skill_id,
            assessed_at=as_utc(a.assessed_at),
            order=as_utc(a.created_at),
            score=a.overall_score,
            level=a.level_achieved,
            rank=a.level_rank,
            top=a.top_level,
        )
        for a in rows
    ]


def record_assessment(db: Session, actor: Actor, data: dict) -> dict:
    now = clock()
    skill = _ref(db, Skill, data["skill_id"], "skill")
    rubric = _ref(db, Rubric, data["rubric_id"], "rubric")
    framework = repo.get(db, Framework, skill.framework_id)
    if framework.status != "active":
        raise _invalid("framework_not_active", f"framework {framework.code} is {framework.status}, not active")
    if not rules.rubric_applies(rubric.skill_id, rubric.framework_id, skill.id, skill.framework_id):
        raise _invalid("rubric_not_for_skill", "the rubric is not for this skill or its framework")
    assessed_at = as_utc(data.get("assessed_at")) or now
    with _rules():
        rules.not_self_assessment(data["learner_id"], data["evaluator_id"])
        rules.not_in_future(assessed_at, now, "assessed_at")
        rules.check_criterion_scores(rubric.criteria or [], data["criterion_scores"])
        level = rules.resolve_level(skill.level_scale, data["overall_score"], data["level_achieved"])
    values = {
        **data,
        "assessed_at": assessed_at,
        "level_achieved": level["label"],
        "level_key": level["key"],
        "level_rank": level["rank"],
        "top_level": level["rank"] == rules.top_rank(skill.level_scale["levels"]),
        "evidence_urls": data.get("evidence_urls") or [],
        "status": "submitted",
        "recorded_by": actor.user_id,
        "created_at": now,  # orders assessments taken at the same time, so it comes from the same clock
    }
    a = Assessment(organisation_id=actor.organisation_id, **values)
    db.add(a)
    kept = ("learner_id", "evaluator_id", "skill_id", "rubric_id", "overall_score")
    _audit(
        db,
        actor,
        "recorded",
        "assessment",
        a,
        after={**{k: data[k] for k in kept}, "assessed_at": assessed_at, "level_achieved": a.level_achieved},
    )
    _publish(
        db,
        actor,
        "assessment.recorded",
        {
            "assessment_id": a.id,
            "learner_id": a.learner_id,
            "evaluator_id": a.evaluator_id,
            "skill_id": a.skill_id,
            "rubric_id": a.rubric_id,
            "overall_score": a.overall_score,
            "level_achieved": a.level_achieved,
            "recorded_at": iso(now),
        },
    )
    history = repo.counted_assessments(db, a.learner_id, rules.COUNTED, skill_id=skill.id)
    for step in rules.progression(_scored(history)):
        if step.assessment.id == a.id and step.kind != rules.ASSESSMENT:
            _publish(
                db,
                actor,
                "milestone.achieved",
                {
                    "learner_id": a.learner_id,
                    "skill_id": skill.id,
                    "milestone_name": rules.MILESTONE_NAMES[step.kind],
                    "level_achieved": a.level_achieved,
                    "achieved_at": iso(assessed_at),
                },
            )
    _progress_updated(db, actor, a.learner_id, skill.framework_id, now)
    db.commit()
    return assessment_out(a)


def _progress_updated(db: Session, actor: Actor, learner_id: str, framework_id: str, now: datetime) -> None:
    _publish(
        db,
        actor,
        "progress.updated",
        {"learner_id": learner_id, "framework_id": framework_id, "updated_at": iso(now)},
    )


def get_assessment(db: Session, actor: Actor, assessment_id: str) -> dict:
    a = _get(db, Assessment, assessment_id, "assessment")
    if actor.self_only and a.learner_id != actor.user_id:
        raise _not_found("assessment")
    return assessment_out(a)


def _transition(db: Session, actor: Actor, assessment_id: str, status: str) -> Assessment:
    a = _get(db, Assessment, assessment_id, "assessment")
    with _rules():
        rules.check_transition(rules.ASSESSMENT_TRANSITIONS, a.status, status, "assessment")
    if a.status == status:
        raise _invalid("invalid_transition", f"the assessment is already {status}")
    return a


def verify_assessment(db: Session, actor: Actor, assessment_id: str) -> dict:
    """A second person confirms the assessment: whoever evaluated or recorded it cannot verify it."""
    a = _transition(db, actor, assessment_id, "verified")
    if actor.user_id in (a.evaluator_id, a.recorded_by):
        raise _invalid("own_assessment", "an assessment is verified by someone other than its evaluator")
    now = clock()
    before = {"status": a.status}
    a.status, a.verified_by, a.verified_at = "verified", actor.user_id, now
    _audit(db, actor, "verified", "assessment", a, before=before, after={"status": a.status})
    db.commit()
    return assessment_out(a)


def void_assessment(db: Session, actor: Actor, assessment_id: str) -> dict:
    """The assessment stays on record but stops counting, so the learner's progress is recomputed."""
    a = _transition(db, actor, assessment_id, "voided")
    now = clock()
    before = {"status": a.status}
    a.status, a.voided_by, a.voided_at = "voided", actor.user_id, now
    _audit(db, actor, "voided", "assessment", a, before=before, after={"status": a.status})
    skill = repo.get(db, Skill, a.skill_id)
    _progress_updated(db, actor, a.learner_id, skill.framework_id, now)
    db.commit()
    return assessment_out(a)


# ---------------------------------------------------------------- progress and timeline


def learner_progress(db: Session, actor: Actor, learner_id: str, framework_id: str | None) -> dict:
    """The latest counted assessment of every skill the learner was assessed on: two queries, whatever the size."""
    _visible_learner(actor, learner_id)
    if framework_id:
        _get(db, Framework, framework_id, "framework")
    rows = repo.counted_assessments(db, learner_id, rules.COUNTED, framework_id=framework_id)
    latest = rules.latest_per_skill(_scored(rows))
    skills = repo.skills_by_id(db, latest)
    current = []
    for skill_id in sorted(latest, key=lambda i: (skills[i].title, i)):
        a, count = latest[skill_id]
        current.append(
            _clean(
                {
                    "skill_id": skill_id,
                    "skill_title": skills[skill_id].title,
                    "category": skills[skill_id].category,
                    "latest_score": a.score,
                    "latest_level": a.level,
                    "total_evaluations": count,
                    "latest_assessed_at": iso(a.assessed_at),
                }
            )
        )
    return {
        "learner_id": learner_id,
        "organisation_id": actor.organisation_id,
        "skills_evaluated": len(current),
        "current_skills": current,
    }


_TITLES = {
    rules.ASSESSMENT: "{skill}: assessed",
    rules.LEVEL_ADVANCED: "{skill}: advanced to {level}",
    rules.MILESTONE: "{skill}: reached {level}, the highest level",
}


def learner_timeline(db: Session, actor: Actor, learner_id: str, skill_id: str | None, limit: int) -> dict:
    """The learner's progression in date order (oldest first). `limit` keeps the most recent entries; `total` counts
    them all. An assessment entry's id is the assessment's; a milestone's is derived from it, so it is stable."""
    _visible_learner(actor, learner_id)
    rows = repo.counted_assessments(db, learner_id, rules.COUNTED, skill_id=skill_id)
    skills = repo.skills_by_id(db, {a.skill_id for a in rows})
    entries = []
    for step in rules.progression(_scored(rows)):
        a = step.assessment
        entry_id = a.id if step.kind == rules.ASSESSMENT else str(uuid.uuid5(uuid.UUID(a.id), step.kind))
        entries.append(
            {
                "id": entry_id,
                "event_type": step.kind,
                "occurred_at": iso(a.assessed_at),
                "skill_id": a.skill_id,
                "title": _TITLES[step.kind].format(skill=skills[a.skill_id].title, level=a.level),
                "score": a.score,
                "level": a.level,
            }
        )
    return _page(entries[-limit:], len(entries))
