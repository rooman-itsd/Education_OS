"""Use cases of athlete-performance (docs/prd.md, contracts/openapi.yaml). Each one applies the domain rules, changes
state, publishes the matching event of contracts/events.yaml through eos_core.events.publish and writes an audit
entry (`_audit`) in the same transaction, then commits once. Permission keys are checked by the API layer
(api/deps.require); which rows a caller may see is decided here.

Athletes see only their own data (contracts/permissions.yaml): a caller whose only athlete-performance access comes
from an athlete role is `self_only`, and every athlete-level read is narrowed to the athlete profile whose user_id is
theirs. Anyone else with the read permission sees the whole organisation.

Known dependencies, not worked around here:
- The shared outbox has no `version` column yet (packages/core), so events go out without the envelope version.
- The audit SDK does not exist (packages/sdk is empty). Until it does, athlete_performance_audit_entry stands in for
  it, shaped like platform/audit's Record, as academic-management's, hostel's and helpdesk's audit tables are."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from eos_core import events
from eos_core.db import new_id, utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import BenchmarkView, RuleViolationError
from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from ..infrastructure.models import (
    Assessment,
    Athlete,
    AuditEntry,
    Benchmark,
    Clearance,
    Discipline,
    FitnessTest,
    Metric,
    Result,
    as_utc,
    iso,
)

MODULE = "athlete-performance"
CATALOGUE_READ = f"{MODULE}:catalogue:read"
CATALOGUE_WRITE = f"{MODULE}:catalogue:write"
ATHLETE_READ = f"{MODULE}:athlete:read"
ATHLETE_WRITE = f"{MODULE}:athlete:write"
RESULT_READ = f"{MODULE}:result:read"
RESULT_RECORD = f"{MODULE}:result:record"
ASSESSMENT_READ = f"{MODULE}:assessment:read"
ASSESSMENT_RECORD = f"{MODULE}:assessment:record"
BENCHMARK_READ = f"{MODULE}:benchmark:read"
BENCHMARK_WRITE = f"{MODULE}:benchmark:write"
CLEARANCE_READ = f"{MODULE}:clearance:read"
CLEARANCE_WRITE = f"{MODULE}:clearance:write"
REPORT_READ = f"{MODULE}:report:read"

# Roles whose access is limited to the caller's own athlete profile.
ATHLETE_ROLES = frozenset({"athlete", "athlete-performance-athlete"})
# Free text and personal details stay out of audit before/after; a change is still named in the summary.
NOT_RECORDED = frozenset({"full_name", "date_of_birth", "notes", "description", "restrictions"})


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


def _known(db: Session, model, ids, what: str) -> None:
    """Every referenced id exists in the caller's organisation; another organisation's ids are unknown here."""
    ids = {i for i in ids if i}
    missing = ids - repo.ids_present(db, model, ids)
    if missing:
        raise _invalid(
            f"unknown_{what}", f"{what.replace('_', ' ')} {sorted(missing)[0]} not found in your organisation"
        )


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


# ---------------------------------------------------------------- who may see which athletes


def own_athlete(db: Session, actor: Actor) -> Athlete | None:
    return repo.first_by(db, Athlete, user_id=actor.user_id)


def _visible_athlete(db: Session, actor: Actor, athlete_id: str) -> Athlete:
    """The athlete, if the caller may see them: a self-only caller sees only their own profile (404 otherwise, so
    other athletes' ids are not even confirmed)."""
    athlete = _get(db, Athlete, athlete_id, "athlete")
    if actor.self_only and athlete.user_id != actor.user_id:
        raise _not_found("athlete")
    return athlete


def _athlete_filter(db: Session, actor: Actor, athlete_id: str | None) -> str | None:
    """The athlete a list is narrowed to. A self-only caller always gets their own (or one that matches nothing)."""
    if not actor.self_only:
        return athlete_id
    own = own_athlete(db, actor)
    if own is None or (athlete_id and athlete_id != own.id):
        return "-"  # no row has this id
    return own.id


# ---------------------------------------------------------------- serialisers


def discipline_out(d: Discipline) -> dict:
    return _clean(
        {
            "id": d.id,
            "organisation_id": d.organisation_id,
            "created_at": iso(d.created_at),
            "updated_at": iso(d.updated_at),
            "name": d.name,
            "category": d.category,
            "description": d.description,
            "active": d.active,
        }
    )


def metric_out(m: Metric) -> dict:
    return _clean(
        {
            "id": m.id,
            "organisation_id": m.organisation_id,
            "created_at": iso(m.created_at),
            "updated_at": iso(m.updated_at),
            "name": m.name,
            "unit": m.unit,
            "direction": m.direction,
            "discipline_id": m.discipline_id,
            "description": m.description,
        }
    )


def athlete_out(a: Athlete) -> dict:
    return _clean(
        {
            "id": a.id,
            "organisation_id": a.organisation_id,
            "created_at": iso(a.created_at),
            "updated_at": iso(a.updated_at),
            "user_id": a.user_id,
            "student_id": a.student_id,
            "full_name": a.full_name,
            "date_of_birth": iso(a.date_of_birth),
            "gender": a.gender,
            "primary_discipline_id": a.primary_discipline_id,
            "discipline_ids": list(a.discipline_ids or []),
            "coach_id": a.coach_id,
            "squad": a.squad,
            "status": a.status,
        }
    )


def result_out(r: Result) -> dict:
    return _clean(
        {
            "id": r.id,
            "organisation_id": r.organisation_id,
            "recorded_by": r.recorded_by,
            "created_at": iso(r.created_at),
            "updated_at": iso(r.updated_at),
            "athlete_id": r.athlete_id,
            "metric_id": r.metric_id,
            "value": r.value,
            "recorded_at": iso(r.recorded_at),
            "context": r.context,
            "notes": r.notes,
        }
    )


def fitness_test_out(t: FitnessTest) -> dict:
    return _clean(
        {
            "id": t.id,
            "organisation_id": t.organisation_id,
            "created_at": iso(t.created_at),
            "updated_at": iso(t.updated_at),
            "name": t.name,
            "description": t.description,
            "metric_ids": list(t.metric_ids or []),
            "discipline_id": t.discipline_id,
        }
    )


def assessment_out(a: Assessment) -> dict:
    return _clean(
        {
            "id": a.id,
            "organisation_id": a.organisation_id,
            "assessor_id": a.assessor_id,
            "created_at": iso(a.created_at),
            "updated_at": iso(a.updated_at),
            "athlete_id": a.athlete_id,
            "fitness_test_id": a.fitness_test_id,
            "assessed_on": iso(a.assessed_on),
            "measurements": [dict(m) for m in a.measurements or []],
            "notes": a.notes,
        }
    )


def benchmark_out(b: Benchmark) -> dict:
    return _clean(
        {
            "id": b.id,
            "organisation_id": b.organisation_id,
            "created_at": iso(b.created_at),
            "updated_at": iso(b.updated_at),
            "metric_id": b.metric_id,
            "discipline_id": b.discipline_id,
            "level": b.level,
            "gender": b.gender,
            "age_group": b.age_group,
            "target_value": b.target_value,
            "source": b.source,
        }
    )


def clearance_out(athlete_id: str, c: Clearance | None) -> dict:
    """Without a recorded clearance the athlete is not cleared: medical staff have not assessed them yet."""
    if c is None:
        return {"athlete_id": athlete_id, "status": "not_cleared"}
    return _clean(
        {
            "athlete_id": athlete_id,
            "status": c.status,
            "valid_until": iso(c.valid_until),
            "restrictions": c.restrictions,
            "set_by": c.set_by,
            "set_at": iso(c.set_at),
        }
    )


# ---------------------------------------------------------------- disciplines


def list_disciplines(db: Session, active: bool | None, limit: int, offset: int) -> dict:
    q = repo.query(db, Discipline)
    if active is not None:
        q = q.where(Discipline.active == active)
    rows, total = repo.page(db, q, (Discipline.name, Discipline.id), limit, offset)
    return _page([discipline_out(d) for d in rows], total)


def create_discipline(db: Session, actor: Actor, data: dict) -> dict:
    if repo.first_by(db, Discipline, name=data["name"]):
        raise _invalid("duplicate_name", f"a discipline named {data['name']!r} already exists")
    d = Discipline(organisation_id=actor.organisation_id, **data)
    db.add(d)
    _audit(db, actor, "created", "discipline", d, after=data)
    _commit(db, "duplicate_name", f"a discipline named {data['name']!r} already exists")
    return discipline_out(d)


def get_discipline(db: Session, discipline_id: str) -> dict:
    return discipline_out(_get(db, Discipline, discipline_id, "discipline"))


def update_discipline(db: Session, actor: Actor, discipline_id: str, data: dict) -> dict:
    d = _get(db, Discipline, discipline_id, "discipline")
    if "name" in data and data["name"] != d.name and repo.first_by(db, Discipline, name=data["name"]):
        raise _invalid("duplicate_name", f"a discipline named {data['name']!r} already exists")
    before, after = _apply(d, data)
    if after:
        _audit(db, actor, "updated", "discipline", d, before=before, after=after)
        _commit(db, "duplicate_name", "a discipline with this name already exists")
    return discipline_out(d)


# ---------------------------------------------------------------- metrics


def list_metrics(db: Session, discipline_id: str | None, limit: int, offset: int) -> dict:
    q = repo.query(db, Metric)
    if discipline_id:
        q = q.where(Metric.discipline_id == discipline_id)
    rows, total = repo.page(db, q, (Metric.name, Metric.id), limit, offset)
    return _page([metric_out(m) for m in rows], total)


def create_metric(db: Session, actor: Actor, data: dict) -> dict:
    _known(db, Discipline, [data.get("discipline_id")], "discipline")
    if repo.first_by(db, Metric, name=data["name"]):
        raise _invalid("duplicate_name", f"a metric named {data['name']!r} already exists")
    m = Metric(organisation_id=actor.organisation_id, **data)
    db.add(m)
    _audit(db, actor, "created", "metric", m, after=data)
    _commit(db, "duplicate_name", f"a metric named {data['name']!r} already exists")
    return metric_out(m)


def get_metric(db: Session, metric_id: str) -> dict:
    return metric_out(_get(db, Metric, metric_id, "metric"))


def update_metric(db: Session, actor: Actor, metric_id: str, data: dict) -> dict:
    m = _get(db, Metric, metric_id, "metric")
    _known(db, Discipline, [data.get("discipline_id")], "discipline")
    if "name" in data and data["name"] != m.name and repo.first_by(db, Metric, name=data["name"]):
        raise _invalid("duplicate_name", f"a metric named {data['name']!r} already exists")
    before, after = _apply(m, data)
    if after:
        _audit(db, actor, "updated", "metric", m, before=before, after=after)
        _commit(db, "duplicate_name", "a metric with this name already exists")
    return metric_out(m)


# ---------------------------------------------------------------- fitness tests


def list_fitness_tests(db: Session, limit: int, offset: int) -> dict:
    rows, total = repo.page(db, repo.query(db, FitnessTest), (FitnessTest.name, FitnessTest.id), limit, offset)
    return _page([fitness_test_out(t) for t in rows], total)


def _check_fitness_test(db: Session, metric_ids: list[str] | None, discipline_id: str | None) -> None:
    if metric_ids is not None:
        try:
            rules.check_metric_ids(metric_ids)
        except RuleViolationError as v:
            raise _rule(v) from v
        _known(db, Metric, metric_ids, "metric")
    _known(db, Discipline, [discipline_id], "discipline")


def create_fitness_test(db: Session, actor: Actor, data: dict) -> dict:
    _check_fitness_test(db, data["metric_ids"], data.get("discipline_id"))
    if repo.first_by(db, FitnessTest, name=data["name"]):
        raise _invalid("duplicate_name", f"a fitness test named {data['name']!r} already exists")
    t = FitnessTest(organisation_id=actor.organisation_id, **data)
    db.add(t)
    _audit(db, actor, "created", "fitness_test", t, after=data)
    _commit(db, "duplicate_name", f"a fitness test named {data['name']!r} already exists")
    return fitness_test_out(t)


def get_fitness_test(db: Session, fitness_test_id: str) -> dict:
    return fitness_test_out(_get(db, FitnessTest, fitness_test_id, "fitness test"))


def update_fitness_test(db: Session, actor: Actor, fitness_test_id: str, data: dict) -> dict:
    t = _get(db, FitnessTest, fitness_test_id, "fitness test")
    _check_fitness_test(db, data.get("metric_ids"), data.get("discipline_id"))
    if "name" in data and data["name"] != t.name and repo.first_by(db, FitnessTest, name=data["name"]):
        raise _invalid("duplicate_name", f"a fitness test named {data['name']!r} already exists")
    before, after = _apply(t, data)
    if after:
        _audit(db, actor, "updated", "fitness_test", t, before=before, after=after)
        _commit(db, "duplicate_name", "a fitness test with this name already exists")
    return fitness_test_out(t)


# ---------------------------------------------------------------- athletes


def list_athletes(db: Session, actor: Actor, filters: dict, limit: int, offset: int) -> dict:
    q = repo.query(db, Athlete)
    if actor.self_only:
        q = q.where(Athlete.user_id == actor.user_id)
    if filters.get("discipline_id"):
        # discipline_ids always holds the primary discipline too; JSON containment differs per database
        rows = [a for a in db.scalars(q) if filters["discipline_id"] in (a.discipline_ids or [])]
        q = q.where(Athlete.id.in_([a.id for a in rows]))
    for name in ("coach_id", "squad", "status"):
        if filters.get(name):
            q = q.where(getattr(Athlete, name) == filters[name])
    if filters.get("q"):
        q = q.where(Athlete.full_name.ilike(f"%{filters['q']}%"))
    rows, total = repo.page(db, q, (Athlete.full_name, Athlete.id), limit, offset)
    return _page([athlete_out(a) for a in rows], total)


def _check_athlete(db: Session, data: dict, now: datetime) -> None:
    _known(db, Discipline, data.get("discipline_ids") or [], "discipline")
    if data.get("date_of_birth"):
        try:
            rules.not_in_future(data["date_of_birth"], now, "date_of_birth")
        except RuleViolationError as v:
            raise _rule(v) from v


def create_athlete(db: Session, actor: Actor, data: dict) -> dict:
    data = {
        **data,
        "discipline_ids": rules.athlete_disciplines(data["primary_discipline_id"], data.get("discipline_ids")),
    }
    _check_athlete(db, data, clock())
    if data.get("user_id") and repo.first_by(db, Athlete, user_id=data["user_id"]):
        raise _invalid("duplicate_user", "this user already has an athlete profile")
    a = Athlete(organisation_id=actor.organisation_id, **data)
    db.add(a)
    _audit(db, actor, "created", "athlete", a, after=data)
    _publish(
        db,
        actor,
        "athlete.registered",
        _clean(
            {
                "athlete_id": a.id,
                "user_id": a.user_id,
                "primary_discipline_id": a.primary_discipline_id,
                "coach_id": a.coach_id,
            }
        ),
    )
    _commit(db, "duplicate_user", "this user already has an athlete profile")
    return athlete_out(a)


def get_athlete(db: Session, actor: Actor, athlete_id: str) -> dict:
    return athlete_out(_visible_athlete(db, actor, athlete_id))


def update_athlete(db: Session, actor: Actor, athlete_id: str, data: dict) -> dict:
    a = _get(db, Athlete, athlete_id, "athlete")
    if "primary_discipline_id" in data or "discipline_ids" in data:
        primary = data.get("primary_discipline_id", a.primary_discipline_id)
        # a new primary alone keeps every discipline the athlete had, the old primary included
        others = data["discipline_ids"] if "discipline_ids" in data else list(a.discipline_ids or [])
        data = {**data, "discipline_ids": rules.athlete_disciplines(primary, others)}
    _check_athlete(db, data, clock())
    if data.get("user_id") and data["user_id"] != a.user_id and repo.first_by(db, Athlete, user_id=data["user_id"]):
        raise _invalid("duplicate_user", "this user already has an athlete profile")
    before, after = _apply(a, data)
    if after:
        _audit(db, actor, "updated", "athlete", a, before=before, after=after)
        tracked = sorted(set(after) & rules.TRACKED_ATHLETE_FIELDS)
        if tracked:
            _publish(db, actor, "athlete.updated", {"athlete_id": a.id, "changed_fields": tracked, "status": a.status})
        _commit(db, "duplicate_user", "this user already has an athlete profile")
    return athlete_out(a)


# ---------------------------------------------------------------- results


def list_results(db: Session, actor: Actor, filters: dict, limit: int, offset: int) -> dict:
    q = repo.query(db, Result)
    athlete_id = _athlete_filter(db, actor, filters.get("athlete_id"))
    if athlete_id:
        q = q.where(Result.athlete_id == athlete_id)
    for name in ("metric_id", "context"):
        if filters.get(name):
            q = q.where(getattr(Result, name) == filters[name])
    if filters.get("from"):
        q = q.where(Result.recorded_at >= _instant(filters["from"]))
    if filters.get("to"):
        q = q.where(Result.recorded_at < _instant(filters["to"] + timedelta(days=1)))
    rows, total = repo.page(db, q, (Result.recorded_at.desc(), Result.id), limit, offset)
    return _page([result_out(r) for r in rows], total)


def _check_result(db: Session, data: dict) -> None:
    _known(db, Athlete, [data.get("athlete_id")], "athlete")
    _known(db, Metric, [data.get("metric_id")], "metric")
    if data.get("recorded_at"):
        try:
            rules.not_in_future(data["recorded_at"], clock(), "recorded_at")
        except RuleViolationError as v:
            raise _rule(v) from v


def record_result(db: Session, actor: Actor, data: dict) -> dict:
    _check_result(db, data)
    r = Result(organisation_id=actor.organisation_id, recorded_by=actor.user_id, **data)
    db.add(r)
    _audit(db, actor, "recorded", "result", r, after=data)
    _publish(
        db,
        actor,
        "result.recorded",
        {
            "result_id": r.id,
            "athlete_id": r.athlete_id,
            "metric_id": r.metric_id,
            "value": r.value,
            "context": r.context,
            "recorded_at": iso(r.recorded_at),
        },
    )
    db.commit()
    return result_out(r)


def get_result(db: Session, actor: Actor, result_id: str) -> dict:
    r = _get(db, Result, result_id, "result")
    if actor.self_only:
        _visible_athlete(db, actor, r.athlete_id)  # 404 for another athlete's result
    return result_out(r)


def update_result(db: Session, actor: Actor, result_id: str, data: dict) -> dict:
    """A correction. The result keeps its id; the audit entry keeps what it was."""
    r = _get(db, Result, result_id, "result")
    _check_result(db, data)
    if "recorded_at" in data:
        data = {**data, "recorded_at": as_utc(data["recorded_at"])}
        if as_utc(r.recorded_at) == data["recorded_at"]:
            data.pop("recorded_at")
    before, after = _apply(r, data)
    if after:
        _audit(db, actor, "corrected", "result", r, before=before, after=after)
        db.commit()
    return result_out(r)


# ---------------------------------------------------------------- assessments


def list_assessments(db: Session, actor: Actor, filters: dict, limit: int, offset: int) -> dict:
    q = repo.query(db, Assessment)
    athlete_id = _athlete_filter(db, actor, filters.get("athlete_id"))
    if athlete_id:
        q = q.where(Assessment.athlete_id == athlete_id)
    if filters.get("fitness_test_id"):
        q = q.where(Assessment.fitness_test_id == filters["fitness_test_id"])
    if filters.get("from"):
        q = q.where(Assessment.assessed_on >= filters["from"])
    if filters.get("to"):
        q = q.where(Assessment.assessed_on <= filters["to"])
    rows, total = repo.page(db, q, (Assessment.assessed_on.desc(), Assessment.id), limit, offset)
    return _page([assessment_out(a) for a in rows], total)


def record_assessment(db: Session, actor: Actor, data: dict) -> dict:
    _known(db, Athlete, [data["athlete_id"]], "athlete")
    test = repo.get(db, FitnessTest, data["fitness_test_id"])
    if test is None:
        raise _invalid("unknown_fitness_test", f"fitness test {data['fitness_test_id']} not found in your organisation")
    try:
        rules.check_measurements(test.metric_ids, data["measurements"])
        rules.not_in_future(data["assessed_on"], clock(), "assessed_on")
    except RuleViolationError as v:
        raise _rule(v) from v
    a = Assessment(organisation_id=actor.organisation_id, assessor_id=actor.user_id, **data)
    db.add(a)
    _audit(db, actor, "recorded", "assessment", a, after={k: v for k, v in data.items() if k != "measurements"})
    _publish(
        db,
        actor,
        "assessment.recorded",
        {
            "assessment_id": a.id,
            "athlete_id": a.athlete_id,
            "fitness_test_id": a.fitness_test_id,
            "assessed_on": iso(a.assessed_on),
        },
    )
    db.commit()
    return assessment_out(a)


def get_assessment(db: Session, actor: Actor, assessment_id: str) -> dict:
    a = _get(db, Assessment, assessment_id, "assessment")
    if actor.self_only:
        _visible_athlete(db, actor, a.athlete_id)
    return assessment_out(a)


# ---------------------------------------------------------------- benchmarks


def list_benchmarks(db: Session, filters: dict, limit: int, offset: int) -> dict:
    q = repo.query(db, Benchmark)
    for name in ("metric_id", "discipline_id"):
        if filters.get(name):
            q = q.where(getattr(Benchmark, name) == filters[name])
    rows, total = repo.page(db, q, (Benchmark.created_at, Benchmark.id), limit, offset)
    return _page([benchmark_out(b) for b in rows], total)


def _same_benchmark(db: Session, values: dict, exclude: str | None = None) -> Benchmark | None:
    """One target per metric, discipline, level, gender and age group."""
    keys = ("metric_id", "discipline_id", "level", "gender", "age_group")
    for b in repo.benchmarks_for(db, [values["metric_id"]]):
        if b.id != exclude and all(getattr(b, k) == values.get(k) for k in keys):
            return b
    return None


def create_benchmark(db: Session, actor: Actor, data: dict) -> dict:
    _known(db, Metric, [data["metric_id"]], "metric")
    _known(db, Discipline, [data.get("discipline_id")], "discipline")
    if _same_benchmark(db, data):
        raise _invalid(
            "duplicate_benchmark", "a benchmark for this metric, discipline, level, gender and age group exists"
        )
    b = Benchmark(organisation_id=actor.organisation_id, **data)
    db.add(b)
    _audit(db, actor, "set", "benchmark", b, after=data)
    _publish_benchmark(db, actor, b)
    db.commit()
    return benchmark_out(b)


def _publish_benchmark(db: Session, actor: Actor, b: Benchmark) -> None:
    payload = {"benchmark_id": b.id, "metric_id": b.metric_id, "level": b.level, "target_value": b.target_value}
    _publish(db, actor, "benchmark.set", payload)


def get_benchmark(db: Session, benchmark_id: str) -> dict:
    return benchmark_out(_get(db, Benchmark, benchmark_id, "benchmark"))


def update_benchmark(db: Session, actor: Actor, benchmark_id: str, data: dict) -> dict:
    b = _get(db, Benchmark, benchmark_id, "benchmark")
    _known(db, Metric, [data.get("metric_id")], "metric")
    _known(db, Discipline, [data.get("discipline_id")], "discipline")
    keys = ("metric_id", "discipline_id", "level", "gender", "age_group")
    if _same_benchmark(db, {k: data.get(k, getattr(b, k)) for k in keys}, exclude=b.id):
        raise _invalid(
            "duplicate_benchmark", "a benchmark for this metric, discipline, level, gender and age group exists"
        )
    before, after = _apply(b, data)
    if after:
        _audit(db, actor, "updated", "benchmark", b, before=before, after=after)
        if {"target_value", "level", "metric_id"} & set(after):
            _publish_benchmark(db, actor, b)
        db.commit()
    return benchmark_out(b)


# ---------------------------------------------------------------- history and comparison


def _points(db: Session, athlete_ids: list[str], metric_id: str | None = None) -> dict[tuple[str, str], list[dict]]:
    """Every value per (athlete, metric), oldest first: results and assessment measurements (taken at the start of
    the assessment day, UTC)."""
    out: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in repo.results_of(db, athlete_ids, metric_id):
        out[(r.athlete_id, r.metric_id)].append({"at": as_utc(r.recorded_at), "value": r.value, "source": "result"})
    for a in repo.assessments_of(db, athlete_ids):
        for m in a.measurements or []:
            if metric_id is None or m["metric_id"] == metric_id:
                out[(a.athlete_id, m["metric_id"])].append(
                    {"at": _instant(a.assessed_on), "value": m["value"], "source": "assessment"}
                )
    for series in out.values():
        series.sort(key=lambda p: p["at"])
    return out


def _views(benchmarks: list[Benchmark]) -> list[BenchmarkView]:
    return [BenchmarkView(b.id, b.metric_id, b.discipline_id, b.level, b.gender) for b in benchmarks]


def performance_history(db: Session, actor: Actor, athlete_id: str, metric_id: str, start, end) -> dict:
    athlete = _visible_athlete(db, actor, athlete_id)
    _get(db, Metric, metric_id, "metric")
    series = _points(db, [athlete.id], metric_id).get((athlete.id, metric_id), [])
    if start:
        series = [p for p in series if p["at"] >= _instant(start)]
    if end:
        series = [p for p in series if p["at"] < _instant(end + timedelta(days=1))]
    benchmarks = repo.benchmarks_for(db, [metric_id])
    best = rules.best_benchmark(_views(benchmarks), athlete.discipline_ids or [], athlete.gender)
    out = {
        "athlete_id": athlete.id,
        "metric_id": metric_id,
        "points": [{**p, "at": iso(p["at"])} for p in series],
    }
    if best:
        out["benchmark"] = benchmark_out(next(b for b in benchmarks if b.id == best.id))
    return out


def compare_with_benchmarks(db: Session, actor: Actor, athlete_id: str, level: str | None) -> dict:
    athlete = _visible_athlete(db, actor, athlete_id)
    benchmarks = repo.benchmarks_for(db)
    by_metric: dict[str, list[BenchmarkView]] = defaultdict(list)
    for v in _views(benchmarks):
        by_metric[v.metric_id].append(v)
    metrics = {m.id: m for m in db.scalars(repo.query(db, Metric).where(Metric.id.in_(list(by_metric))))}
    points = _points(db, [athlete.id])
    targets = {b.id: b.target_value for b in benchmarks}
    items = []
    for metric_id in sorted(by_metric, key=lambda m: metrics[m].name):
        best = rules.best_benchmark(by_metric[metric_id], athlete.discipline_ids or [], athlete.gender, level)
        if best is None:
            continue
        series = points.get((athlete.id, metric_id), [])
        latest = series[-1]["value"] if series else None
        direction = metrics[metric_id].direction
        target = targets[best.id]
        row = {
            "metric_id": metric_id,
            "benchmark_id": best.id,
            "latest_value": latest,
            "target_value": target,
            "gap": None if latest is None else rules.gap(latest, target, direction),
            "status": rules.comparison_status(latest, target, direction),
        }
        items.append(_clean(row))
    return {"items": items}


# ---------------------------------------------------------------- clearance


def get_clearance(db: Session, actor: Actor, athlete_id: str) -> dict:
    athlete = _visible_athlete(db, actor, athlete_id)
    return clearance_out(athlete.id, repo.first_by(db, Clearance, athlete_id=athlete.id))


def set_clearance(db: Session, actor: Actor, athlete_id: str, data: dict) -> dict:
    athlete = _get(db, Athlete, athlete_id, "athlete")
    now = clock()
    if data.get("valid_until") and data["valid_until"] < now.date():
        raise _invalid("in_past", "valid_until cannot be in the past")
    values = {
        "status": data["status"],
        "valid_until": data.get("valid_until"),
        "restrictions": data.get("restrictions"),
    }
    c = repo.first_by(db, Clearance, athlete_id=athlete.id)
    if c is None:
        c = Clearance(organisation_id=actor.organisation_id, athlete_id=athlete.id, set_by=actor.user_id, set_at=now)
        db.add(c)
        before, after = None, values
        for k, v in values.items():
            setattr(c, k, v)
    else:
        before, after = _apply(c, values)
        if not after:
            return clearance_out(athlete.id, c)
        c.set_by, c.set_at = actor.user_id, now
    _audit(db, actor, "set", "clearance", c, before=before, after=after)
    if before is None or {"status", "valid_until"} & set(after):
        payload = {"athlete_id": athlete.id, "status": c.status, "valid_until": iso(c.valid_until)}
        _publish(db, actor, "clearance.changed", _clean(payload))
    _commit(db, "conflict", "the clearance was set by someone else at the same time; try again")
    return clearance_out(athlete.id, c)


# ---------------------------------------------------------------- reports


def squad_summary(db: Session, actor: Actor, filters: dict) -> dict:
    """Active athletes in the group, with the latest value and trend of every metric they have values for."""
    q = repo.query(db, Athlete).where(Athlete.status == "active")
    for name in ("coach_id", "squad"):
        if filters.get(name):
            q = q.where(getattr(Athlete, name) == filters[name])
    athletes = [
        a
        for a in db.scalars(q.order_by(Athlete.full_name, Athlete.id))
        if not filters.get("discipline_id") or filters["discipline_id"] in (a.discipline_ids or [])
    ]
    ids = [a.id for a in athletes]
    points = _points(db, ids)
    clearances = repo.clearances_of(db, ids)
    metric_ids = {m for (_, m) in points}
    metrics = {m.id: m for m in db.scalars(repo.query(db, Metric).where(Metric.id.in_(list(metric_ids))))}
    steady = load_settings().trend_steady_percent
    items = []
    for a in athletes:
        rows = []
        for metric_id in sorted((m for (aid, m) in points if aid == a.id), key=lambda m: metrics[m].name):
            values = [p["value"] for p in points[(a.id, metric_id)]]
            rows.append(
                {
                    "metric_id": metric_id,
                    "latest_value": values[-1],
                    "trend": rules.trend(values, metrics[metric_id].direction, steady),
                }
            )
        c = clearances.get(a.id)
        items.append(
            {
                "athlete_id": a.id,
                "full_name": a.full_name,
                "clearance": c.status if c else "not_cleared",
                "metrics": rows,
            }
        )
    return {"items": items}
