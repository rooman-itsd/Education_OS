"""Use cases of incident-management (docs/prd.md, contracts/openapi.yaml). Each one checks the caller's permission and
the domain rules, changes state, writes an audit entry, and publishes the matching event from contracts/events.yaml to
the outbox in the same transaction. Event payloads carry ids, numbers, severity, status, dates and service labels
only; titles, descriptions, timeline text and RCA text are never published, nor copied into the audit entries.

Where the contract leaves a detail open, the choice made here is noted at the function. Choices that apply
throughout:

- Lists are newest first by when the row was created (incidents, problems), or soonest due first (actions). The
  cursor is an opaque offset; one this module did not hand out, or one past repository.MAX_OFFSET, is a 422.
- `lead` and `owner` filters take "me" or a person id (a 422 otherwise, in the API layer). `service` matches one
  affected service label exactly, ignoring case and surrounding spaces; it is one value, so a comma is part of it.
- Service labels are trimmed, blank ones dropped and repeats (ignoring case) kept once; responder ids are kept once.
- A started_at in the future (beyond FUTURE_TOLERANCE of clock skew) is a 422, and so is one after the incident's
  recorded mitigated, resolved or closed time."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import incidents as inc
from ..domain import problems as prb
from ..domain.errors import DomainRuleError
from ..domain.stats import open_counts
from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from ..infrastructure.models import (
    AuditEntry,
    CorrectiveAction,
    Incident,
    Problem,
    Rca,
    Reference,
    TimelineUpdate,
)
from .access import (
    INCIDENT_MANAGE,
    INCIDENT_READ,
    INCIDENT_REPORT,
    MODULE,
    PROBLEM_MANAGE,
    PROBLEM_READ,
    Actor,
    require,
)
from .errors import IncidentManagementError, forbidden, from_domain

INCIDENT, PROBLEM, RCA, ACTION = "incident", "problem", "rca", "action"  # number sequence kinds and audit entities

# How far ahead of the server clock a reported started_at may be, for clocks that are slightly off.
FUTURE_TOLERANCE = timedelta(minutes=5)


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


def today() -> date:
    return clock().astimezone(UTC).date()


# ---------------------------------------------------------------- helpers


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; everything stored is UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | None) -> str | None:
    return None if value is None else as_utc(value).isoformat()


def _not_found(what: str) -> IncidentManagementError:
    return IncidentManagementError(404, "not_found", f"{what} not found")


def _conflict(code: str, message: str, field: str | None = None) -> IncidentManagementError:
    return IncidentManagementError(409, code, message, field=field)


def _invalid(code: str, message: str, field: str | None = None) -> IncidentManagementError:
    return IncidentManagementError(422, code, message, field=field)


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
    """`name` is "<entity>.<verb>", such as "incident.reported"."""
    events.publish(
        db,
        f"{MODULE}.{name}",
        actor.organisation_id,
        {"organisation_id": actor.organisation_id, **payload},
        actor=actor.user_id,
    )


def _number(db: Session, actor: Actor, kind: str) -> str:
    settings = load_settings()
    prefix = settings.incident_number_prefix if kind == INCIDENT else settings.problem_number_prefix
    # Format from the PRD's examples INC-000123 and PRB-000045: the prefix, a hyphen and six digits.
    return f"{prefix}-{repo.next_number(db, actor.organisation_id, kind):06d}"


def _offset(cursor: str | None) -> int:
    try:
        return repo.decode_cursor(cursor)
    except repo.InvalidCursorError:
        raise _invalid("invalid_cursor", "the cursor is not one from a previous page", "cursor") from None


def _person(actor: Actor, value: str | None) -> str | None:
    """`lead` and `owner` filters: "me" is the caller."""
    return actor.user_id if value == "me" else value


def _labels(values: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        label = value.strip()
        if label and label.lower() not in seen:
            seen.add(label.lower())
            out.append(label)
    return out


def _has_label(labels: list[str] | None, service: str) -> bool:
    wanted = service.strip().lower()
    return any(label.lower() == wanted for label in labels or [])


def _unique(ids: list[str] | None) -> list[str]:
    return list(dict.fromkeys(i.lower() for i in ids or []))


def _incident(db: Session, incident_id: str, *, lock: bool = False) -> Incident:
    incident = (repo.locked if lock else repo.get)(db, Incident, incident_id)
    if incident is None:
        raise _not_found("incident")
    return incident


def _problem(db: Session, problem_id: str, *, lock: bool = False) -> Problem:
    problem = (repo.locked if lock else repo.get)(db, Problem, problem_id)
    if problem is None:
        raise _not_found("problem")
    return problem


def _check_started(started: datetime, incident: Incident | None) -> None:
    """started_at is not in the future, and not after a mitigated, resolved or closed time already recorded."""
    if started > clock() + FUTURE_TOLERANCE:
        raise _invalid("started_at_in_future", "started_at cannot be in the future", "started_at")
    if incident is None:
        return
    for name in ("mitigated_at", "resolved_at", "closed_at"):
        recorded = as_utc(getattr(incident, name))
        if recorded is not None and started > recorded:
            raise _invalid("started_after_" + name[:-3], f"started_at cannot be after {name}", "started_at")


def _commit(db: Session) -> None:
    db.commit()


def _fields(body: dict) -> str | None:
    """The audit reason of an edit: which fields changed, never their text."""
    return f"fields: {', '.join(sorted(body))}" if body else None


# ---------------------------------------------------------------- serialisation (contract schemas)


def incident_dict(incident: Incident) -> dict:
    return {
        "id": incident.id,
        "organisation_id": incident.organisation_id,
        "number": incident.number,
        "title": incident.title,
        "description": incident.description,
        "affected_services": list(incident.affected_services or []),
        "severity": incident.severity,
        "status": incident.status,
        "lead_id": incident.lead_id,
        "responder_ids": list(incident.responder_ids or []),
        "reported_by": incident.reported_by,
        "problem_id": incident.problem_id,
        "resolution_summary": incident.resolution_summary,
        "started_at": iso(incident.started_at),
        "mitigated_at": iso(incident.mitigated_at),
        "resolved_at": iso(incident.resolved_at),
        "closed_at": iso(incident.closed_at),
        "created_at": iso(incident.created_at),
        "updated_at": iso(incident.updated_at),
    }


def update_dict(update: TimelineUpdate) -> dict:
    return {
        "id": update.id,
        "incident_id": update.incident_id,
        "author_id": update.author_id,
        "body": update.body,
        "created_at": iso(update.created_at),
    }


def reference_dict(reference: Reference) -> dict:
    return {
        "module": reference.ref_module,
        "entity": reference.ref_entity,
        "id": reference.ref_id,
        "relation": reference.relation,
        "note": reference.note,
        "reference_id": reference.id,
        "created_by": reference.created_by,
        "created_at": iso(reference.created_at),
    }


def problem_dict(problem: Problem, incident_count: int) -> dict:
    return {
        "id": problem.id,
        "organisation_id": problem.organisation_id,
        "number": problem.number,
        "title": problem.title,
        "description": problem.description,
        "affected_services": list(problem.affected_services or []),
        "status": problem.status,
        "owner_id": problem.owner_id,
        "workaround": problem.workaround,
        "incident_count": incident_count,
        "created_at": iso(problem.created_at),
        "resolved_at": iso(problem.resolved_at),
        "closed_at": iso(problem.closed_at),
    }


def rca_dict(rca: Rca) -> dict:
    return {
        "summary": rca.summary,
        "root_cause": rca.root_cause,
        "contributing_factors": list(rca.contributing_factors or []),
        "attachment_document_ids": list(rca.attachment_document_ids or []),
        "problem_id": rca.problem_id,
        "organisation_id": rca.organisation_id,
        "status": rca.status,
        "published_at": iso(rca.published_at),
        "published_by": rca.published_by,
        "updated_at": iso(rca.updated_at),
    }


def action_dict(action: CorrectiveAction, on: date | None = None) -> dict:
    return {
        "id": action.id,
        "organisation_id": action.organisation_id,
        "problem_id": action.problem_id,
        "description": action.description,
        "owner_id": action.owner_id,
        "due_date": action.due_date.isoformat(),
        "status": action.status,
        "overdue": prb.is_overdue(action.status, action.due_date, on or today()),
        "reference": action.reference,
        "completed_at": iso(action.completed_at),
    }


# ---------------------------------------------------------------- incidents


def list_incidents(
    db: Session,
    actor: Actor,
    *,
    statuses: list[str] | None,
    severity: str | None,
    lead: str | None,
    problem_id: str | None,
    service: str | None,
    q: str | None,
    cursor: str | None,
    limit: int,
) -> dict:
    """GET /incidents, newest first. Service labels live in a JSON list, so that filter runs here rather than in the
    database."""
    require(actor, INCIDENT_READ)
    offset = _offset(cursor)
    rows = repo.incidents(
        db, statuses=statuses, severity=severity, lead_id=_person(actor, lead), problem_id=problem_id, q=q
    )
    if service:
        rows = [i for i in rows if _has_label(i.affected_services, service)]
    items, next_cursor = repo.page_of(rows, offset, limit)
    return {"items": [incident_dict(i) for i in items], "next_cursor": next_cursor}


def report_incident(db: Session, actor: Actor, body: dict) -> dict:
    """POST /incidents: status open with the next INC number. The reporter is the lead unless lead_id is given;
    started_at defaults to now. Publishes incident.reported. A blank title or description is a 422."""
    require(actor, INCIDENT_REPORT)
    _domain(inc.check_text, body["title"], "title")
    _domain(inc.check_text, body["description"], "description")
    started = body.get("started_at") or clock()
    _check_started(started, None)
    incident = Incident(
        organisation_id=actor.organisation_id,
        number=_number(db, actor, INCIDENT),
        title=body["title"],
        description=body["description"],
        affected_services=_labels(body.get("affected_services")),
        severity=body["severity"],
        status=inc.OPEN,
        lead_id=(body.get("lead_id") or actor.user_id).lower(),
        responder_ids=_unique(body.get("responder_ids")),
        reported_by=actor.user_id,
        started_at=started,
    )
    db.add(incident)
    db.flush()
    _audit(db, actor, "incident.reported", INCIDENT, incident.id)
    _publish(
        db,
        actor,
        "incident.reported",
        {
            "incident_id": incident.id,
            "number": incident.number,
            "severity": incident.severity,
            "affected_services": list(incident.affected_services),
            "lead_id": incident.lead_id,
            "responder_ids": list(incident.responder_ids),
            "started_at": iso(incident.started_at),
        },
    )
    _commit(db)
    return incident_dict(incident)


def get_incident(db: Session, actor: Actor, incident_id: str) -> dict:
    """GET /incidents/{id}: with the timeline (oldest first) and the references."""
    require(actor, INCIDENT_READ)
    incident = _incident(db, incident_id)
    return {
        **incident_dict(incident),
        "updates": [update_dict(u) for u in repo.timeline(db, incident.id)],
        "references": [reference_dict(r) for r in repo.references(db, incident.id)],
    }


def update_incident(db: Session, actor: Actor, incident_id: str, body: dict) -> dict:
    """PATCH /incidents/{id}: only the fields sent change; 409 when closed or cancelled. problem_id links the incident
    to a problem (404 when there is no such problem, 409 when it is closed) or, as null, unlinks it; linking is
    audited and publishes no event (PRD "Rules"). A severity change publishes incident.severity-changed. Fields sent
    with their current value are not counted as changes."""
    require(actor, INCIDENT_MANAGE)
    incident = _incident(db, incident_id, lock=True)
    _domain(inc.check_editable, incident.status)
    if "title" in body:
        _domain(inc.check_text, body["title"], "title")
    if "description" in body:
        _domain(inc.check_text, body["description"], "description")
    if "started_at" in body:
        _check_started(body["started_at"], incident)
    if body.get("problem_id") is not None:
        body["problem_id"] = body["problem_id"].lower()
        if body["problem_id"] != incident.problem_id:
            _domain(prb.check_can_link, _problem(db, body["problem_id"]).status)
    normalised = {"affected_services": _labels, "responder_ids": _unique, "lead_id": str.lower}
    changes = {}
    for name, value in body.items():
        value = normalised[name](value) if name in normalised else value
        current = as_utc(getattr(incident, name)) if name == "started_at" else getattr(incident, name)
        if value != current:
            changes[name] = value
    previous_severity, previous_problem = incident.severity, incident.problem_id
    for name, value in changes.items():
        setattr(incident, name, value)
    edited = {k: v for k, v in changes.items() if k != "problem_id"}
    if edited:
        _audit(db, actor, "incident.updated", INCIDENT, incident.id, _fields(edited))
    if "problem_id" in changes:
        if previous_problem is not None:
            _audit(db, actor, "incident.unlinked", INCIDENT, incident.id, f"problem {previous_problem}")
        if incident.problem_id is not None:
            _audit(db, actor, "incident.linked", INCIDENT, incident.id, f"problem {incident.problem_id}")
    if "severity" in changes:
        _publish(
            db,
            actor,
            "incident.severity-changed",
            {
                "incident_id": incident.id,
                "number": incident.number,
                "severity": incident.severity,
                "previous_severity": previous_severity,
                "status": incident.status,
                "changed_by": actor.user_id,
            },
        )
    _commit(db)
    return incident_dict(incident)


def move_incident(db: Session, actor: Actor, incident_id: str, body: dict) -> dict:
    """POST /incidents/{id}/status. mitigated records mitigated_at (the latest mitigation; it is kept when the
    incident goes back to investigating); resolved records resolved_at and the resolution_summary; closed records
    closed_at. Reopening (resolved -> investigating) clears resolved_at and resolution_summary, since a new resolution
    is needed. A note, required to cancel or reopen and optional otherwise, is saved as a timeline update. Publishes
    incident.status-changed."""
    require(actor, INCIDENT_MANAGE)
    incident = _incident(db, incident_id, lock=True)
    previous, target = incident.status, body["status"]
    note = body.get("note")
    incident.status = _domain(inc.move, previous, target, resolution_summary=body.get("resolution_summary"), note=note)
    now = clock()
    if target == inc.MITIGATED:
        incident.mitigated_at = now
    elif target == inc.RESOLVED:
        incident.resolved_at, incident.resolution_summary = now, body["resolution_summary"]
    elif target == inc.CLOSED:
        incident.closed_at = now
    elif inc.is_reopen(previous, target):
        incident.resolved_at, incident.resolution_summary = None, None
    if note and note.strip():
        db.add(
            TimelineUpdate(
                organisation_id=actor.organisation_id, incident_id=incident.id, author_id=actor.user_id, body=note
            )
        )
    action = "incident.reopened" if inc.is_reopen(previous, target) else f"incident.{target}"
    _audit(db, actor, action, INCIDENT, incident.id, f"from {previous}")
    _publish(
        db,
        actor,
        "incident.status-changed",
        {
            "incident_id": incident.id,
            "number": incident.number,
            "severity": incident.severity,
            "from_status": previous,
            "to_status": target,
            "problem_id": incident.problem_id,
            "changed_at": iso(now),
        },
    )
    _commit(db)
    return incident_dict(incident)


def add_update(db: Session, actor: Actor, incident_id: str, body: dict) -> dict:
    """POST /incidents/{id}/updates: 409 when closed or cancelled; a body of only spaces is a 422."""
    require(actor, INCIDENT_MANAGE)
    incident = _incident(db, incident_id, lock=True)
    _domain(inc.check_editable, incident.status)
    _domain(inc.check_text, body["body"], "body")
    update = TimelineUpdate(
        organisation_id=actor.organisation_id, incident_id=incident.id, author_id=actor.user_id, body=body["body"]
    )
    db.add(update)
    db.flush()
    _audit(db, actor, "incident.update_added", INCIDENT, incident.id, f"update {update.id}")
    _commit(db)
    return update_dict(update)


def add_reference(db: Session, actor: Actor, incident_id: str, body: dict) -> dict:
    """POST /incidents/{id}/references. "The same reference" is the same module, entity and id on this incident,
    whatever the relation (409). The incident row is locked first so two requests for the same record run one after
    the other; the unique index is the backstop. Like other changes, refused on a closed or cancelled incident (409)."""
    require(actor, INCIDENT_MANAGE)
    incident = _incident(db, incident_id, lock=True)
    _domain(inc.check_editable, incident.status)
    duplicate = _conflict("reference_exists", "this record is already recorded on the incident", "id")
    if repo.reference_to(db, incident.id, body["module"], body["entity"], body["id"]):
        raise duplicate
    reference = Reference(
        organisation_id=actor.organisation_id,
        incident_id=incident.id,
        ref_module=body["module"],
        ref_entity=body["entity"],
        ref_id=body["id"],
        relation=body["relation"],
        note=body.get("note"),
        created_by=actor.user_id,
    )
    db.add(reference)
    try:
        db.flush()
    except IntegrityError:  # the same record added at the same moment
        db.rollback()
        raise duplicate from None
    _audit(db, actor, "incident.reference_added", INCIDENT, incident.id, f"reference {reference.id}")
    _commit(db)
    return reference_dict(reference)


def remove_reference(db: Session, actor: Actor, incident_id: str, reference_id: str) -> None:
    """DELETE /incidents/{id}/references/{reference_id}: "Remove a reference recorded by mistake. Audited." The only
    deletion in the module. Allowed in any incident status, so a mistake can be corrected after closing."""
    require(actor, INCIDENT_MANAGE)
    incident = _incident(db, incident_id)
    reference = repo.get(db, Reference, reference_id)
    if reference is None or reference.incident_id != incident.id:
        raise _not_found("reference")
    record = f"reference {reference.id}: {reference.ref_module}/{reference.ref_entity}/{reference.ref_id}"
    db.delete(reference)
    _audit(db, actor, "incident.reference_removed", INCIDENT, incident.id, record)
    _commit(db)


def open_stats(db: Session, actor: Actor) -> dict:
    """GET /stats/open, behind the widget incident-management.open."""
    require(actor, INCIDENT_READ)
    counts = open_counts(repo.incident_states(db))
    return {
        "total_open": counts.total_open,
        "by_severity": [{"severity": c.severity, "count": c.count} for c in counts.by_severity],
        "by_status": [{"status": c.status, "count": c.count} for c in counts.by_status],
    }


# ---------------------------------------------------------------- problems


def list_problems(
    db: Session,
    actor: Actor,
    *,
    statuses: list[str] | None,
    owner: str | None,
    service: str | None,
    q: str | None,
    cursor: str | None,
    limit: int,
) -> dict:
    """GET /problems, newest first, each with the number of incidents linked to it."""
    require(actor, PROBLEM_READ)
    offset = _offset(cursor)
    rows = repo.problems(db, statuses=statuses, owner_id=_person(actor, owner), q=q)
    if service:
        rows = [p for p in rows if _has_label(p.affected_services, service)]
    items, next_cursor = repo.page_of(rows, offset, limit)
    counts = repo.incident_counts(db, [p.id for p in items])
    return {"items": [problem_dict(p, counts.get(p.id, 0)) for p in items], "next_cursor": next_cursor}


def open_problem(db: Session, actor: Actor, body: dict) -> dict:
    """POST /problems: status open with the next PRB number; owner_id defaults to the caller. events.yaml has no
    event for a new problem, so none is published."""
    require(actor, PROBLEM_MANAGE)
    _domain(inc.check_text, body["title"], "title")
    _domain(inc.check_text, body["description"], "description")
    problem = Problem(
        organisation_id=actor.organisation_id,
        number=_number(db, actor, PROBLEM),
        title=body["title"],
        description=body["description"],
        affected_services=_labels(body.get("affected_services")),
        status=prb.OPEN,
        owner_id=(body.get("owner_id") or actor.user_id).lower(),
    )
    db.add(problem)
    db.flush()
    _audit(db, actor, "problem.opened", PROBLEM, problem.id)
    _commit(db)
    return problem_dict(problem, 0)


def get_problem(db: Session, actor: Actor, problem_id: str) -> dict:
    """GET /problems/{id}: with its linked incidents (oldest first), RCA status (null without an RCA) and corrective
    actions (soonest due first)."""
    require(actor, PROBLEM_READ)
    problem = _problem(db, problem_id)
    incidents = repo.incidents_of_problem(db, problem.id)
    rca = repo.rca(db, problem.id)
    on = today()
    return {
        **problem_dict(problem, len(incidents)),
        "incidents": [incident_dict(i) for i in incidents],
        "rca_status": rca.status if rca else None,
        "actions": [action_dict(a, on) for a in repo.actions(db, problem_id=problem.id)],
    }


def update_problem(db: Session, actor: Actor, problem_id: str, body: dict) -> dict:
    """PATCH /problems/{id}: only the fields sent change; 409 when closed. A workaround of only spaces is stored as
    none, which a known error refuses (422)."""
    require(actor, PROBLEM_MANAGE)
    problem = _problem(db, problem_id, lock=True)
    _domain(prb.check_editable, problem.status)
    if "title" in body:
        _domain(inc.check_text, body["title"], "title")
    if "description" in body:
        _domain(inc.check_text, body["description"], "description")
    if "workaround" in body:
        if not body["workaround"].strip():
            body["workaround"] = None
        _domain(prb.check_workaround_kept, problem.status, body["workaround"])
    normalised = {"affected_services": _labels, "owner_id": str.lower}
    changes = {}
    for name, value in body.items():
        value = normalised[name](value) if name in normalised else value
        if value != getattr(problem, name):
            changes[name] = value
    for name, value in changes.items():
        setattr(problem, name, value)
    if changes:
        _audit(db, actor, "problem.updated", PROBLEM, problem.id, _fields(changes))
    _commit(db)
    return problem_dict(problem, len(repo.incidents_of_problem(db, problem.id)))


def move_problem(db: Session, actor: Actor, problem_id: str, body: dict) -> dict:
    """POST /problems/{id}/status. A workaround sent with the move is recorded (it is required for known_error unless
    one is already recorded); resolved needs a published RCA (409) and records resolved_at; closed records closed_at.
    Publishes problem.status-changed."""
    require(actor, PROBLEM_MANAGE)
    problem = _problem(db, problem_id, lock=True)
    rca = repo.rca(db, problem.id)
    previous, target = problem.status, body["status"]
    sent = body.get("workaround")
    workaround = sent if sent and sent.strip() else problem.workaround
    problem.status = _domain(prb.move, previous, target, workaround=workaround, rca_status=rca.status if rca else None)
    if sent and sent.strip():
        problem.workaround = sent
    now = clock()
    if target == prb.RESOLVED:
        problem.resolved_at = now
    elif target == prb.CLOSED:
        problem.closed_at = now
    _audit(db, actor, f"problem.{target}", PROBLEM, problem.id, f"from {previous}")
    _publish(
        db,
        actor,
        "problem.status-changed",
        {
            "problem_id": problem.id,
            "number": problem.number,
            "from_status": previous,
            "to_status": target,
            "affected_services": list(problem.affected_services or []),
            "changed_at": iso(now),
        },
    )
    _commit(db)
    return problem_dict(problem, len(repo.incidents_of_problem(db, problem.id)))


# ---------------------------------------------------------------- root-cause analysis


def get_rca(db: Session, actor: Actor, problem_id: str) -> dict:
    """GET /problems/{id}/rca: 404 when the problem is unknown or has no RCA drafted yet."""
    require(actor, PROBLEM_READ)
    problem = _problem(db, problem_id)
    rca = repo.rca(db, problem.id)
    if rca is None:
        raise IncidentManagementError(404, "rca_not_found", "no RCA drafted yet")
    return rca_dict(rca)


def save_rca(db: Session, actor: Actor, problem_id: str, body: dict) -> dict:
    """PUT /problems/{id}/rca: creates the draft or replaces all of it (fields not sent become empty lists); 409 once
    published. The problem row is locked first, so two first drafts at the same moment run one after the other and
    the second replaces the first instead of failing on the key; an IntegrityError is still answered with 409. A
    closed problem always has a published RCA, so it is refused by the same rule."""
    require(actor, PROBLEM_MANAGE)
    problem = _problem(db, problem_id, lock=True)
    _domain(inc.check_text, body["summary"], "summary")
    _domain(inc.check_text, body["root_cause"], "root_cause")
    rca = repo.rca(db, problem.id)
    created = rca is None
    if rca is None:
        rca = Rca(organisation_id=actor.organisation_id, problem_id=problem.id, status=prb.DRAFT)
        db.add(rca)
    else:
        _domain(prb.check_rca_editable, rca.status)
    rca.summary, rca.root_cause = body["summary"], body["root_cause"]
    rca.contributing_factors = list(body.get("contributing_factors") or [])
    rca.attachment_document_ids = list(body.get("attachment_document_ids") or [])
    rca.updated_at = clock()
    try:
        db.flush()
    except IntegrityError:  # only if the lock was bypassed
        db.rollback()
        raise _conflict("rca_conflict", "the RCA was changed at the same moment; try again") from None
    _audit(db, actor, "rca.drafted" if created else "rca.updated", RCA, problem.id)
    _commit(db)
    return rca_dict(rca)


def publish_rca(db: Session, actor: Actor, problem_id: str) -> dict:
    """POST /problems/{id}/rca/publish: draft -> published (404 without a draft, 409 when already published).
    Publishes problem.rca-published."""
    require(actor, PROBLEM_MANAGE)
    problem = _problem(db, problem_id, lock=True)
    rca = repo.rca(db, problem.id)
    if rca is None:
        raise IncidentManagementError(404, "rca_not_found", "no RCA drafted")
    rca.status = _domain(prb.publish_rca, rca.status)
    now = clock()
    rca.published_at, rca.published_by, rca.updated_at = now, actor.user_id, now
    _audit(db, actor, "rca.published", RCA, problem.id)
    _publish(
        db,
        actor,
        "problem.rca-published",
        {"problem_id": problem.id, "number": problem.number, "published_by": actor.user_id, "published_at": iso(now)},
    )
    _commit(db)
    return rca_dict(rca)


# ---------------------------------------------------------------- corrective actions


def _assigned(db: Session, actor: Actor, action: CorrectiveAction, problem: Problem) -> None:
    _publish(
        db,
        actor,
        "action.assigned",
        {
            "action_id": action.id,
            "problem_id": problem.id,
            "problem_number": problem.number,
            "owner_id": action.owner_id,
            "due_date": action.due_date.isoformat(),
        },
    )


def list_actions(
    db: Session,
    actor: Actor,
    *,
    owner: str | None,
    status: str | None,
    overdue: bool | None,
    cursor: str | None,
    limit: int,
) -> dict:
    """GET /actions, soonest due first. overdue is worked out when read: true returns open actions past their due
    date, false every other action."""
    require(actor, PROBLEM_READ)
    offset = _offset(cursor)
    on = today()
    rows = repo.actions(db, owner_id=_person(actor, owner), status=status)
    if overdue is not None:
        rows = [a for a in rows if prb.is_overdue(a.status, a.due_date, on) is overdue]
    items, next_cursor = repo.page_of(rows, offset, limit)
    return {"items": [action_dict(a, on) for a in items], "next_cursor": next_cursor}


def add_action(db: Session, actor: Actor, problem_id: str, body: dict) -> dict:
    """POST /problems/{id}/actions: 409 when the problem is closed; a due date before today is a 422. The contract
    does not tie actions to the RCA's status, so they can be added before it is published. Publishes
    action.assigned."""
    require(actor, PROBLEM_MANAGE)
    problem = _problem(db, problem_id, lock=True)
    _domain(prb.check_can_add_action, problem.status)
    _domain(inc.check_text, body["description"], "description")
    _domain(prb.check_due_date, body["due_date"], today())
    action = CorrectiveAction(
        organisation_id=actor.organisation_id,
        problem_id=problem.id,
        description=body["description"],
        owner_id=body["owner_id"].lower(),
        due_date=body["due_date"],
        status=prb.ACTION_OPEN,
        reference=body.get("reference"),
    )
    db.add(action)
    db.flush()
    _audit(db, actor, "action.created", ACTION, action.id)
    _assigned(db, actor, action, problem)
    _commit(db)
    return action_dict(action)


def update_action(db: Session, actor: Actor, problem_id: str, action_id: str, body: dict) -> dict:
    """PATCH /problems/{id}/actions/{action_id}: only the fields sent change; 409 once done or cancelled. With
    incident-management:problem:manage anything may change; with only problem:read the action's owner may send
    exactly {"status": "done"} (403 otherwise). done records completed_at; cancelled does not. Open actions of a
    closed problem can still be changed, so follow-up work can be finished after the problem closes. A new owner
    publishes action.assigned; a changed due date must be today or later (422)."""
    require(actor, PROBLEM_READ, PROBLEM_MANAGE)
    problem = _problem(db, problem_id)
    action = repo.locked(db, CorrectiveAction, action_id)
    if action is None or action.problem_id != problem.id:
        raise _not_found("action")
    if not actor.can(PROBLEM_MANAGE):
        own_done = action.owner_id == actor.user_id.lower() and body == {"status": prb.ACTION_DONE}
        if not own_done:
            raise forbidden(f"only the action's owner may mark it done without {PROBLEM_MANAGE}")
    _domain(prb.check_action_editable, action.status)
    if "description" in body:
        _domain(inc.check_text, body["description"], "description")
    if "owner_id" in body:
        body["owner_id"] = body["owner_id"].lower()
    if "due_date" in body and body["due_date"] != action.due_date:
        _domain(prb.check_due_date, body["due_date"], today())
    new_owner = "owner_id" in body and body["owner_id"] != action.owner_id
    status = body.pop("status", None)
    changes = {name: value for name, value in body.items() if value != getattr(action, name)}
    for name, value in changes.items():
        setattr(action, name, value)
    if changes:
        _audit(db, actor, "action.updated", ACTION, action.id, _fields(changes))
    if status is not None:
        action.status = status
        if status == prb.ACTION_DONE:
            action.completed_at = clock()
        _audit(db, actor, f"action.{status}", ACTION, action.id)
    if new_owner:
        _assigned(db, actor, action, problem)
    _commit(db)
    return action_dict(action)
