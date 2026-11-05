"""Use cases of iqac-accreditation (docs/prd.md, contracts/openapi.yaml). Each one checks the caller's permission and
the domain rules, changes state, writes an audit entry, and publishes the matching event from contracts/events.yaml to
the outbox in the same transaction. Event payloads carry ids, the metric code, statuses and times only; values,
narratives, evidence and review comments are never published.

Where the contract leaves a detail open, the choice made here is noted at the function. Choices that hold for the
whole module:

- Dates are accepted from 1900-01-01 to 2199-12-31 everywhere (domain.accreditation.MIN_DATE and MAX_DATE). The only
  date sum is today + IQAC_ACCREDITATION_DUE_SOON_DAYS (at most 366); overdue and due soon are worked out by
  subtraction, so nothing can overflow.
- A response is overdue while pending or returned and past due_on; an action item while open or in progress and past
  due_on. Due today is not overdue.
- Owners are not notified yet: platform/notification has no SDK in packages/sdk (README "Needs from the host repo").
  Assignments, returns and new or reassigned action items are audited and name their owner, so the notices can be added
  there.
- "Open cycle" (a framework used by one cannot be deactivated) means a cycle that is not closed.
- A cycle with no responses can be submitted: "every response is accepted" holds for none.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import accreditation as rules
from ..domain.errors import DomainRuleError
from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from ..infrastructure.models import (
    ActionItem,
    AuditEntry,
    Cycle,
    Evidence,
    Framework,
    Metric,
    Response,
)
from .access import (
    ACTION_ITEM_MANAGE,
    ACTION_ITEM_UPDATE_OWN,
    CYCLE_MANAGE,
    DATA_READ,
    FRAMEWORK_MANAGE,
    MODULE,
    RESPONSE_SUBMIT,
    STATS_READ,
    Actor,
    require,
)
from .errors import IqacAccreditationError, forbidden, from_domain

# Audit entities.
FRAMEWORK, METRIC, CYCLE, RESPONSE, EVIDENCE, ACTION_ITEM = (
    "framework",
    "metric",
    "cycle",
    "response",
    "evidence",
    "action-item",
)
FRAMEWORK_READERS = (DATA_READ, FRAMEWORK_MANAGE, RESPONSE_SUBMIT)


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


def today() -> date:
    return clock().astimezone(UTC).date()


# ---------------------------------------------------------------- helpers


def _not_found(what: str) -> IqacAccreditationError:
    return IqacAccreditationError(404, "not_found", f"{what} not found")


def _conflict(code: str, message: str, field: str | None = None) -> IqacAccreditationError:
    return IqacAccreditationError(409, code, message, field=field)


def _invalid(code: str, message: str, field: str | None = None) -> IqacAccreditationError:
    return IqacAccreditationError(422, code, message, field=field)


def _domain(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except DomainRuleError as err:
        raise from_domain(err) from err


def _audit(db: Session, actor: Actor, action: str, entity: str, entity_id: str, reason: str | None = None) -> None:
    db.add(
        AuditEntry(
            organisation_id=actor.organisation_id,
            actor=actor.user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            reason=reason,
            occurred_at=clock(),
        )
    )


def _publish(db: Session, actor: Actor, name: str, payload: dict) -> None:
    events.publish(
        db,
        f"{MODULE}.{name}",
        actor.organisation_id,
        {"organisation_id": actor.organisation_id, **payload},
        actor=actor.user_id,
    )


def _flush_unique(db: Session, error: IqacAccreditationError) -> None:
    """Write now, so a duplicate that slipped past the check (two requests at once) is a 409, not a 500."""
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise error from None


def _get(db: Session, model, row_id: str, what: str, *, lock: bool = False):
    row = repo.get(db, model, row_id, lock=lock)
    if row is None:
        raise _not_found(what)
    return row


def _iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return value.isoformat()


def _without_none(data: dict, keys: tuple[str, ...]) -> dict:
    """The contract types these properties as plain strings, not nullable: they are left out when empty."""
    return {k: v for k, v in data.items() if k not in keys or v is not None}


def _page(rows: list[dict], more: bool, offset: int, limit: int) -> dict:
    return {"items": rows, "next_cursor": repo.encode_cursor(offset + limit) if more else None}


def _offset(cursor: str | None) -> int:
    try:
        return repo.decode_cursor(cursor)
    except ValueError:
        raise _invalid("invalid_cursor", "cursor is not one this API returned", "cursor") from None


def _owner_filter(owner: str | None, actor: Actor, sees_all: bool) -> tuple[str | None, bool]:
    """(owner id to filter by, nothing can match). owner=me means the caller. A caller who sees only their own asking
    for another owner gets an empty page, not a 403."""
    owner_id = actor.user_id if owner == "me" else owner
    if sees_all:
        return owner_id, False
    return actor.user_id, bool(owner_id and owner_id != actor.user_id)


# ---------------------------------------------------------------- serialisation (contract schemas)


def framework_dict(f: Framework) -> dict:
    return _without_none(
        {
            "id": f.id,
            "organisation_id": f.organisation_id,
            "code": f.code,
            "name": f.name,
            "description": f.description,
            "active": f.active,
        },
        ("description",),
    )


def metric_dict(m: Metric) -> dict:
    return _without_none(
        {
            "id": m.id,
            "organisation_id": m.organisation_id,
            "framework_id": m.framework_id,
            "code": m.code,
            "title": m.title,
            "criterion": m.criterion,
            "kind": m.kind,
            "unit": m.unit,
            "guidance": m.guidance,
            "active": m.active,
        },
        ("criterion", "unit", "guidance"),
    )


def cycle_dict(c: Cycle) -> dict:
    return {
        "id": c.id,
        "organisation_id": c.organisation_id,
        "framework_id": c.framework_id,
        "name": c.name,
        "period_start": c.period_start.isoformat(),
        "period_end": c.period_end.isoformat(),
        "status": c.status,
        "submitted_on": _iso(c.submitted_on),
        "closed_at": _iso(c.closed_at),
    }


def response_dict(r: Response, metric_code: str | None, on: date) -> dict:
    out = {
        "id": r.id,
        "organisation_id": r.organisation_id,
        "cycle_id": r.cycle_id,
        "metric_id": r.metric_id,
        "owner_id": r.owner_id,
        "due_on": r.due_on.isoformat(),
        "status": r.status,
        "value": r.value,
        "narrative": r.narrative,
        "review_comment": r.review_comment,
        "submitted_at": _iso(r.submitted_at),
        "reviewed_by": r.reviewed_by,
        "reviewed_at": _iso(r.reviewed_at),
        "overdue": rules.is_response_overdue(r.status, r.due_on, on),
    }
    if metric_code is not None:
        out["metric_code"] = metric_code
    return out


def evidence_dict(e: Evidence) -> dict:
    return _without_none(
        {
            "id": e.id,
            "response_id": e.response_id,
            "title": e.title,
            "kind": e.kind,
            "url": e.url,
            "reference": e.reference,
            "note": e.note,
            "added_by": e.added_by,
            "added_at": _iso(e.added_at),
        },
        ("url", "reference", "note"),
    )


def action_item_dict(a: ActionItem, on: date) -> dict:
    return {
        "id": a.id,
        "organisation_id": a.organisation_id,
        "title": a.title,
        "description": a.description,
        "source": a.source,
        "cycle_id": a.cycle_id,
        "metric_id": a.metric_id,
        "owner_id": a.owner_id,
        "due_on": a.due_on.isoformat(),
        "status": a.status,
        "overdue": rules.is_action_overdue(a.status, a.due_on, on),
        "completed_at": _iso(a.completed_at),
    }


def _responses(db: Session, rows: list[Response]) -> list[dict]:
    codes = repo.metrics_by_id(db, {r.metric_id for r in rows})
    on = today()
    return [response_dict(r, codes[r.metric_id].code if r.metric_id in codes else None, on) for r in rows]


# ---------------------------------------------------------------- frameworks


def list_frameworks(db: Session, actor: Actor, *, active: bool | None) -> list[dict]:
    """GET /frameworks, by code."""
    require(actor, *FRAMEWORK_READERS)
    return [framework_dict(f) for f in repo.frameworks(db, active)]


def _code_taken(what: str) -> IqacAccreditationError:
    return _conflict("code_taken", f"that code is already used by another {what}", "code")


def create_framework(db: Session, actor: Actor, body: dict) -> dict:
    """POST /frameworks. active defaults to true."""
    require(actor, FRAMEWORK_MANAGE)
    if repo.framework_with_code(db, body["code"]) is not None:
        raise _code_taken("framework")
    framework = Framework(
        organisation_id=actor.organisation_id,
        code=body["code"],
        name=body["name"],
        description=body.get("description"),
        active=body.get("active", True),
    )
    db.add(framework)
    _flush_unique(db, _code_taken("framework"))
    _audit(db, actor, "framework.created", FRAMEWORK, framework.id)
    db.commit()
    return framework_dict(framework)


def update_framework(db: Session, actor: Actor, framework_id: str, body: dict) -> dict:
    """PATCH /frameworks/{id}: only the fields sent change (the contract's FrameworkInput requires code and name; a
    PATCH here accepts any of them). A framework used by an open cycle cannot be deactivated (409). An inactive
    framework may be made active again. An empty body changes nothing and is not audited."""
    require(actor, FRAMEWORK_MANAGE)
    framework = _get(db, Framework, framework_id, "framework", lock=True)
    if not body:
        return framework_dict(framework)
    deactivated = framework.active and body.get("active") is False
    if deactivated and repo.framework_in_open_cycle(db, framework.id):
        raise _conflict("framework_in_open_cycle", "the framework is used by an open cycle", "active")
    if "code" in body and body["code"] != framework.code and repo.framework_with_code(db, body["code"]) is not None:
        raise _code_taken("framework")
    for name, value in body.items():
        setattr(framework, name, value)
    _flush_unique(db, _code_taken("framework"))
    _audit(db, actor, "framework.deactivated" if deactivated else "framework.updated", FRAMEWORK, framework.id)
    db.commit()
    return framework_dict(framework)


# ---------------------------------------------------------------- metrics


def list_metrics(
    db: Session, actor: Actor, framework_id: str, *, criterion: str | None, active: bool | None
) -> list[dict]:
    """GET /frameworks/{id}/metrics, by code. criterion matches the whole label, ignoring case."""
    require(actor, *FRAMEWORK_READERS)
    _get(db, Framework, framework_id, "framework")
    return [metric_dict(m) for m in repo.metrics(db, framework_id, criterion=criterion, active=active)]


def create_metric(db: Session, actor: Actor, framework_id: str, body: dict) -> dict:
    """POST /frameworks/{id}/metrics. active defaults to true. A metric may be added to an inactive framework; it can
    be assigned only once a cycle exists, and a cycle needs an active framework."""
    require(actor, FRAMEWORK_MANAGE)
    framework = _get(db, Framework, framework_id, "framework", lock=True)
    taken = _conflict("code_taken", "that code is already used by another metric of this framework", "code")
    if repo.metric_with_code(db, framework.id, body["code"]) is not None:
        raise taken
    metric = Metric(
        organisation_id=actor.organisation_id,
        framework_id=framework.id,
        code=body["code"],
        title=body["title"],
        criterion=body.get("criterion"),
        kind=body["kind"],
        unit=body.get("unit"),
        guidance=body.get("guidance"),
        active=body.get("active", True),
    )
    db.add(metric)
    _flush_unique(db, taken)
    _audit(db, actor, "metric.created", METRIC, metric.id)
    db.commit()
    return metric_dict(metric)


def update_metric(db: Session, actor: Actor, metric_id: str, body: dict) -> dict:
    """PATCH /metrics/{id}: only the fields sent change; the code and the kind do not. Existing responses keep their
    values and are not touched. An empty body changes nothing and is not audited."""
    require(actor, FRAMEWORK_MANAGE)
    metric = _get(db, Metric, metric_id, "metric", lock=True)
    if not body:
        return metric_dict(metric)
    deactivated = metric.active and body.get("active") is False
    for name, value in body.items():
        setattr(metric, name, value)
    _audit(db, actor, "metric.deactivated" if deactivated else "metric.updated", METRIC, metric.id)
    db.commit()
    return metric_dict(metric)


# ---------------------------------------------------------------- cycles


def list_cycles(db: Session, actor: Actor, *, framework_id: str | None, status: str | None) -> list[dict]:
    """GET /cycles, newest first."""
    require(actor, DATA_READ, CYCLE_MANAGE)
    return [cycle_dict(c) for c in repo.cycles(db, framework_id=framework_id, status=status)]


def create_cycle(db: Session, actor: Actor, body: dict) -> dict:
    """POST /cycles: status planning. An unknown framework is 422 like an inactive one: the framework is a value of
    the request, not the address of it."""
    require(actor, CYCLE_MANAGE)
    framework = repo.get(db, Framework, body["framework_id"], lock=True)
    if framework is None:
        raise _invalid("framework_not_found", "the framework does not exist", "framework_id")
    _domain(rules.check_framework_active, framework.active)
    _domain(rules.check_period, body["period_start"], body["period_end"])
    cycle = Cycle(
        organisation_id=actor.organisation_id,
        framework_id=framework.id,
        name=body["name"],
        period_start=body["period_start"],
        period_end=body["period_end"],
        status=rules.PLANNING,
    )
    db.add(cycle)
    db.flush()
    _audit(db, actor, "cycle.created", CYCLE, cycle.id)
    db.commit()
    return cycle_dict(cycle)


def get_cycle(db: Session, actor: Actor, cycle_id: str) -> dict:
    """GET /cycles/{id} with response_counts: pending, submitted, returned, accepted, and overdue (a count of the
    pending and returned ones past due, not a status)."""
    require(actor, DATA_READ, CYCLE_MANAGE)
    cycle = _get(db, Cycle, cycle_id, "cycle")
    return {**cycle_dict(cycle), "response_counts": repo.response_counts(db, cycle.id, today())}


def update_cycle(db: Session, actor: Actor, cycle_id: str, body: dict) -> dict:
    """PATCH /cycles/{id}: name and period, while planning (409 otherwise). The period as changed must still end after
    it starts. An empty body changes nothing and is not audited."""
    require(actor, CYCLE_MANAGE)
    cycle = _get(db, Cycle, cycle_id, "cycle", lock=True)
    _domain(rules.check_cycle_planning, cycle.status)
    if not body:
        return cycle_dict(cycle)
    _domain(rules.check_period, body.get("period_start", cycle.period_start), body.get("period_end", cycle.period_end))
    for name, value in body.items():
        setattr(cycle, name, value)
    _audit(db, actor, "cycle.updated", CYCLE, cycle.id)
    db.commit()
    return cycle_dict(cycle)


def move_cycle(db: Session, actor: Actor, cycle_id: str, body: dict) -> dict:
    """POST /cycles/{id}/status: planning -> collecting -> under_review -> submitted -> closed. submitted needs
    submitted_on (422) and every response accepted (409); submitted_on sent with another status is ignored. Publishes
    iqac-accreditation.cycle.status-changed."""
    require(actor, CYCLE_MANAGE)
    cycle = _get(db, Cycle, cycle_id, "cycle", lock=True)
    target, submitted_on = body["status"], body.get("submitted_on")
    all_accepted = target != rules.SUBMITTED_CYCLE or not repo.has_unaccepted_response(db, cycle.id)
    _domain(rules.cycle_move, cycle.status, target, submitted_on, all_accepted)
    previous, now = cycle.status, clock()
    cycle.status = target
    if target == rules.SUBMITTED_CYCLE:
        cycle.submitted_on = submitted_on
    if target == rules.CLOSED:
        cycle.closed_at = now
    _audit(db, actor, "cycle.status-changed", CYCLE, cycle.id, f"{previous} -> {target}")
    _publish(
        db,
        actor,
        "cycle.status-changed",
        {
            "cycle_id": cycle.id,
            "framework_id": cycle.framework_id,
            "from_status": previous,
            "to_status": target,
            "changed_at": _iso(now),
        },
    )
    db.commit()
    return cycle_dict(cycle)


def assign_metrics(db: Session, actor: Actor, cycle_id: str, body: dict) -> list[dict]:
    """POST /cycles/{id}/assignments: one pending response per metric, all or none. 409 when the cycle is not planning
    or collecting, or a metric is already assigned in it (also twice in one request); 422 for a metric that is not
    an active metric of the cycle's framework. The owner is any person id: it is not checked against identity."""
    require(actor, CYCLE_MANAGE)
    cycle = _get(db, Cycle, cycle_id, "cycle", lock=True)
    _domain(rules.check_assignable, cycle.status)
    items = body["assignments"]
    metrics = repo.metrics_by_id(db, {a["metric_id"] for a in items})
    for item in items:
        metric = metrics.get(item["metric_id"])
        if metric is None:
            raise _invalid("metric_not_found", "the metric does not exist", "metric_id")
        _domain(rules.check_metric_assignable, metric.framework_id, cycle.framework_id, metric.active)
        _domain(rules.check_date, item["due_on"], "due_on")
    taken = _conflict("metric_already_assigned", "a metric is already assigned in this cycle", "metric_id")
    wanted = [a["metric_id"] for a in items]
    if len(set(wanted)) != len(wanted) or repo.assigned_metric_ids(db, cycle.id) & set(wanted):
        raise taken
    rows = [
        Response(
            organisation_id=actor.organisation_id,
            cycle_id=cycle.id,
            metric_id=item["metric_id"],
            owner_id=item["owner_id"],
            due_on=item["due_on"],
            status=rules.PENDING,
        )
        for item in items
    ]
    db.add_all(rows)
    _flush_unique(db, taken)
    for row in rows:
        _audit(db, actor, "response.assigned", RESPONSE, row.id)
    db.commit()
    return _responses(db, rows)


# ---------------------------------------------------------------- responses


def list_responses(
    db: Session,
    actor: Actor,
    *,
    cycle_id: str | None,
    owner: str | None,
    status: str | None,
    overdue: bool | None,
    cursor: str | None,
    limit: int,
) -> dict:
    """GET /responses, soonest due first. With data:read or cycle:manage every response; with only response:submit
    the caller's own. owner=me means the caller."""
    require(actor, DATA_READ, CYCLE_MANAGE, RESPONSE_SUBMIT)
    offset = _offset(cursor)
    owner_id, nothing = _owner_filter(owner, actor, actor.sees_all_responses())
    if nothing:
        return _page([], False, offset, limit)
    rows, more = repo.responses_page(
        db,
        today=today(),
        cycle_id=cycle_id,
        owner_id=owner_id,
        status=status,
        overdue=overdue,
        offset=offset,
        limit=limit,
    )
    return _page(_responses(db, rows), more, offset, limit)


def _visible_response(db: Session, actor: Actor, response_id: str, *, lock: bool = False) -> Response:
    """The response, if the caller may see it: all with data:read or cycle:manage, else only their own. Another's
    response is "not found" (contract: "Not found or not visible to the caller")."""
    response = repo.get(db, Response, response_id, lock=lock)
    if response is None or not (actor.sees_all_responses() or response.owner_id == actor.user_id):
        raise _not_found("response")
    return response


def _own_response(db: Session, actor: Actor, response_id: str, *, lock: bool = False) -> Response:
    """The caller's own response; anyone else's is "not found" to them."""
    response = repo.get(db, Response, response_id, lock=lock)
    if response is None or response.owner_id != actor.user_id:
        raise _not_found("response")
    return response


def get_response(db: Session, actor: Actor, response_id: str) -> dict:
    """GET /responses/{id} with its evidence, oldest first."""
    require(actor, DATA_READ, CYCLE_MANAGE, RESPONSE_SUBMIT)
    response = _visible_response(db, actor, response_id)
    evidence = repo.evidence_of(db, [response.id])[response.id]
    return {**_responses(db, [response])[0], "evidence": [evidence_dict(e) for e in evidence]}


def _editable_response(db: Session, actor: Actor, response_id: str) -> tuple[Response, Metric]:
    """The caller's own response, locked, if it can still be filled in: pending or returned, in a cycle that is
    collecting or under review."""
    require(actor, RESPONSE_SUBMIT)
    response = _own_response(db, actor, response_id, lock=True)
    _domain(rules.check_response_editable, response.status)
    cycle = _get(db, Cycle, response.cycle_id, "cycle")
    _domain(rules.check_cycle_responding, cycle.status)
    return response, _get(db, Metric, response.metric_id, "metric")


def save_response(db: Session, actor: Actor, response_id: str, body: dict) -> dict:
    """PUT /responses/{id}: sets the value and the narrative sent; one left out keeps its stored value and null clears
    it. A value on a qualitative metric is 422. The status does not change (a returned response stays returned until
    it is submitted again)."""
    response, metric = _editable_response(db, actor, response_id)
    _domain(rules.check_value_allowed, metric.kind, body.get("value"))
    for name in ("value", "narrative"):
        if name in body:
            setattr(response, name, body[name])
    _audit(db, actor, "response.saved", RESPONSE, response.id)
    db.commit()
    return response_dict(response, metric.code, today())


def submit_response(db: Session, actor: Actor, response_id: str) -> dict:
    """POST /responses/{id}/submit: pending or returned -> submitted. 422 when a quantitative metric has no value or a
    qualitative one no narrative. The earlier review comment is kept until the next review."""
    response, metric = _editable_response(db, actor, response_id)
    _domain(rules.check_ready_to_submit, metric.kind, response.value, response.narrative)
    response.status = rules.SUBMITTED
    response.submitted_at = clock()
    _audit(db, actor, "response.submitted", RESPONSE, response.id)
    db.commit()
    return response_dict(response, metric.code, today())


def review_response(db: Session, actor: Actor, response_id: str, body: dict) -> dict:
    """POST /responses/{id}/review: accept (submitted -> accepted, publishes iqac-accreditation.response.accepted) or
    return with a comment (submitted -> returned). 409 when not submitted, then 422 for a return without a comment. A
    comment sent with an accept is kept; an accept without one clears an earlier return comment."""
    require(actor, CYCLE_MANAGE)
    response = _get(db, Response, response_id, "response", lock=True)
    _domain(rules.check_submitted, response.status)
    comment = (body.get("comment") or "").strip() or None
    accept = body["decision"] == "accept"
    if not accept:
        _domain(rules.check_return_comment, comment)
    metric = _get(db, Metric, response.metric_id, "metric")
    now = clock()
    response.status = rules.ACCEPTED if accept else rules.RETURNED
    response.review_comment = comment
    response.reviewed_by = actor.user_id
    response.reviewed_at = now
    _audit(db, actor, "response.accepted" if accept else "response.returned", RESPONSE, response.id, comment)
    if accept:
        _publish(
            db,
            actor,
            "response.accepted",
            {
                "response_id": response.id,
                "cycle_id": response.cycle_id,
                "metric_id": response.metric_id,
                "metric_code": metric.code,
                "accepted_at": _iso(now),
            },
        )
    db.commit()
    return response_dict(response, metric.code, today())


def add_evidence(db: Session, actor: Actor, response_id: str, body: dict) -> dict:
    """POST /responses/{id}/evidence: a link or a reference on the caller's own response while it is not accepted (409).
    Stored as given; a reference is not checked against the other module. The audit entry names the evidence, not its
    content."""
    require(actor, RESPONSE_SUBMIT)
    response = _own_response(db, actor, response_id, lock=True)
    _domain(rules.check_not_accepted, response.status)
    _domain(rules.check_evidence, body["kind"], body.get("url"), body.get("reference"))
    evidence = Evidence(
        organisation_id=actor.organisation_id,
        response_id=response.id,
        title=body["title"],
        kind=body["kind"],
        url=body.get("url"),
        reference=body.get("reference"),
        note=body.get("note"),
        added_by=actor.user_id,
        added_at=clock(),
    )
    db.add(evidence)
    db.flush()
    _audit(db, actor, "evidence.added", EVIDENCE, evidence.id, f"response {response.id}")
    db.commit()
    return evidence_dict(evidence)


def remove_evidence(db: Session, actor: Actor, response_id: str, evidence_id: str) -> None:
    """DELETE /responses/{id}/evidence/{evidence_id}: evidence added by mistake, while the response is not accepted.
    The row is removed; the audit entry stays."""
    require(actor, RESPONSE_SUBMIT)
    response = _own_response(db, actor, response_id, lock=True)
    evidence = repo.evidence_of_response(db, response.id, evidence_id, lock=True)
    if evidence is None:
        raise _not_found("evidence")
    _domain(rules.check_not_accepted, response.status)
    db.delete(evidence)
    _audit(db, actor, "evidence.removed", EVIDENCE, evidence.id, f"response {response.id}")
    db.commit()


# ---------------------------------------------------------------- action items


def _check_links(db: Session, cycle_id: str | None, metric_id: str | None) -> None:
    """422 for a cycle or metric that does not exist: they are values of the request."""
    if cycle_id is not None and repo.get(db, Cycle, cycle_id) is None:
        raise _invalid("cycle_not_found", "the cycle does not exist", "cycle_id")
    if metric_id is not None and repo.get(db, Metric, metric_id) is None:
        raise _invalid("metric_not_found", "the metric does not exist", "metric_id")


def list_action_items(
    db: Session,
    actor: Actor,
    *,
    status: str | None,
    owner: str | None,
    cycle_id: str | None,
    overdue: bool | None,
    cursor: str | None,
    limit: int,
) -> dict:
    """GET /action-items, soonest due first. With data:read or action-item:manage every item; with only
    action-item:update-own the caller's own. owner=me means the caller."""
    require(actor, DATA_READ, ACTION_ITEM_MANAGE, ACTION_ITEM_UPDATE_OWN)
    offset = _offset(cursor)
    owner_id, nothing = _owner_filter(owner, actor, actor.sees_all_action_items())
    if nothing:
        return _page([], False, offset, limit)
    rows, more = repo.action_items_page(
        db,
        today=today(),
        status=status,
        owner_id=owner_id,
        cycle_id=cycle_id,
        overdue=overdue,
        offset=offset,
        limit=limit,
    )
    on = today()
    return _page([action_item_dict(a, on) for a in rows], more, offset, limit)


def create_action_item(db: Session, actor: Actor, body: dict) -> dict:
    """POST /action-items: status open. cycle_id and metric_id, when given, must exist (422). The owner is any person
    id."""
    require(actor, ACTION_ITEM_MANAGE)
    _check_links(db, body.get("cycle_id"), body.get("metric_id"))
    _domain(rules.check_date, body["due_on"], "due_on")
    item = ActionItem(
        organisation_id=actor.organisation_id,
        title=body["title"],
        description=body.get("description"),
        source=body.get("source"),
        cycle_id=body.get("cycle_id"),
        metric_id=body.get("metric_id"),
        owner_id=body["owner_id"],
        due_on=body["due_on"],
        status=rules.OPEN,
    )
    db.add(item)
    db.flush()
    _audit(db, actor, "action-item.created", ACTION_ITEM, item.id)
    db.commit()
    return action_item_dict(item, today())


def update_action_item(db: Session, actor: Actor, item_id: str, body: dict) -> dict:
    """PATCH /action-items/{id}. action-item:manage may change any field and cancel; action-item:update-own lets the
    owner move their own item open -> in_progress -> done, and nothing else (403 for another field or for cancelling;
    another's item is not found). A done or cancelled item cannot change (409). `note` is kept in the audit entry of
    a status change and ignored otherwise. An empty body changes nothing and is not audited."""
    require(actor, ACTION_ITEM_MANAGE, ACTION_ITEM_UPDATE_OWN)
    item = _get(db, ActionItem, item_id, "action item", lock=True)
    manager = actor.can(ACTION_ITEM_MANAGE)
    if not manager and item.owner_id != actor.user_id:
        raise _not_found("action item")
    if not manager:
        if set(body) - {"status", "note"}:
            raise forbidden("an owner may change only the status of their action item")
        if body.get("status") == rules.CANCELLED:
            raise forbidden(f"cancelling an action item needs {ACTION_ITEM_MANAGE}")
    if not body:
        return action_item_dict(item, today())
    _domain(rules.check_action_live, item.status)
    if "due_on" in body:
        _domain(rules.check_date, body["due_on"], "due_on")
    now, previous = clock(), item.status
    target = body.get("status")
    if target is not None:
        _domain(rules.action_move, previous, target)
    changed = {k: v for k, v in body.items() if k in ("title", "description", "source", "owner_id", "due_on")}
    reassigned = "owner_id" in changed and changed["owner_id"] != item.owner_id
    for name, value in changed.items():
        setattr(item, name, value)
    if changed:
        _audit(db, actor, "action-item.updated", ACTION_ITEM, item.id)
    if reassigned:
        _audit(db, actor, "action-item.reassigned", ACTION_ITEM, item.id, f"owner {changed['owner_id']}")
    if target is not None:
        item.status = target
        if target == rules.DONE:
            item.completed_at = now
        note = (body.get("note") or "").strip()
        _audit(
            db,
            actor,
            "action-item.status-changed",
            ACTION_ITEM,
            item.id,
            f"{previous} -> {target}" + (f": {note}" if note else ""),
        )
    db.commit()
    return action_item_dict(item, today())


# ---------------------------------------------------------------- widget


def action_item_stats(db: Session, actor: Actor) -> dict:
    """GET /stats/action-items: every action item of the organisation, not only the caller's. due_soon counts open and
    in-progress items due from today up to due_soon_days ahead; soonest lists up to ten of them, soonest due first."""
    require(actor, STATS_READ)
    days = load_settings().due_soon_days
    on = today()
    counts = repo.action_item_counts(db, on, on + timedelta(days=days))
    soonest = [
        {
            "id": a.id,
            "title": a.title,
            "owner_id": a.owner_id,
            "due_on": a.due_on.isoformat(),
            "status": a.status,
            "overdue": rules.is_action_overdue(a.status, a.due_on, on),
        }
        for a in repo.soonest_action_items(db, 10)
    ]
    return {**counts, "due_soon_days": days, "soonest": soonest}
