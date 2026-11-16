"""Use cases of regulatory-reports (docs/prd.md, contracts/openapi.yaml). Each one checks the caller's permission and
the domain rules, changes state, writes an audit entry, and publishes the matching event from contracts/events.yaml to
the outbox in the same transaction. Event payloads carry ids, the period label and dates only; preparation notes,
links, review comments and submission and acknowledgement references are never published.

Where the contract leaves a detail open, the choice made here is noted at the function. Choices that hold for the
whole module:

- Recurrence is a label only (contract Recurrence: "Informational only; filings are not created automatically"; PRD
  open question 3). No next period or due date is ever worked out from it, so there is no date arithmetic on it.
- Dates are accepted from 1900-01-01 to 2199-12-31 everywhere (domain.filings.MIN_DATE and MAX_DATE). The only date
  sum is today + REGULATORY_REPORTS_DUE_SOON_DAYS (at most 366), and overdue and due soon are worked out by
  subtraction, so nothing can overflow.
- Overdue and due soon apply to filings not yet submitted (open, in_preparation, under_review). A not_applicable
  filing is never overdue. A filing due today is due soon, not overdue.
- Owners are not notified yet: platform/notification has no SDK in packages/sdk (README "Needs from the host repo").
  Filing creation and returns are audited, and the filing names its owner, so the notices can be added there.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import due as due_rules
from ..domain import filings as rules
from ..domain.errors import DomainRuleError
from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from ..infrastructure.models import AuditEntry, Filing, Obligation
from .access import (
    DATA_READ,
    FILING_MANAGE,
    FILING_PREPARE,
    MODULE,
    OBLIGATION_MANAGE,
    STATS_READ,
    Actor,
    require,
    require_all,
)
from .errors import RegulatoryReportsError, forbidden, from_domain

OBLIGATION, FILING = "obligation", "filing"  # audit entities


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


def today() -> date:
    return clock().astimezone(UTC).date()


# ---------------------------------------------------------------- helpers


def _not_found(what: str) -> RegulatoryReportsError:
    return RegulatoryReportsError(404, "not_found", f"{what} not found")


def _conflict(code: str, message: str, field: str | None = None) -> RegulatoryReportsError:
    return RegulatoryReportsError(409, code, message, field=field)


def _invalid(code: str, message: str, field: str | None = None) -> RegulatoryReportsError:
    return RegulatoryReportsError(422, code, message, field=field)


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
        f"{MODULE}.filing.{name}",
        actor.organisation_id,
        {"organisation_id": actor.organisation_id, **payload},
        actor=actor.user_id,
    )


def _obligation(db: Session, obligation_id: str, *, lock: bool = False) -> Obligation:
    obligation = repo.get(db, Obligation, obligation_id, lock=lock)
    if obligation is None:
        raise _not_found("obligation")
    return obligation


def _filing(db: Session, actor: Actor, filing_id: str, *, lock: bool = False) -> Filing:
    """The filing, if the caller may see it: all with data:read or filing:manage, else only their own. Another's
    filing is "not found" to a preparer (contract: "Not found or not visible to the caller")."""
    filing = repo.get(db, Filing, filing_id, lock=lock)
    if filing is None or not (actor.sees_all_filings() or filing.owner_id == actor.user_id):
        raise _not_found("filing")
    return filing


def _period_taken() -> RegulatoryReportsError:
    return _conflict("period_label_taken", "this obligation already has a filing for that period label", "period_label")


def _flush_unique(db: Session) -> None:
    """Flush; a concurrent request that took the same period label first is a 409, not a 500."""
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _period_taken() from None


# ---------------------------------------------------------------- serialisation (contract schemas)


def obligation_dict(obligation: Obligation) -> dict:
    return {
        "id": obligation.id,
        "organisation_id": obligation.organisation_id,
        "title": obligation.title,
        "authority": obligation.authority,
        "portal_url": obligation.portal_url,
        "description": obligation.description,
        "recurrence": obligation.recurrence,
        "default_owner_id": obligation.default_owner_id,
        "active": obligation.active,
    }


def filing_dict(filing: Filing, obligation: Obligation | None, on: date, due_soon_days: int) -> dict:
    """Contract Filing. obligation_title and authority are the obligation's current values."""
    return {
        "id": filing.id,
        "organisation_id": filing.organisation_id,
        "obligation_id": filing.obligation_id,
        "obligation_title": obligation.title if obligation else None,
        "authority": obligation.authority if obligation else None,
        "period_label": filing.period_label,
        "period_start": filing.period_start.isoformat(),
        "period_end": filing.period_end.isoformat(),
        "due_on": filing.due_on.isoformat(),
        "owner_id": filing.owner_id,
        "status": filing.status,
        "preparation_notes": filing.preparation_notes,
        "links": list(filing.links or []),
        "review_comment": filing.review_comment,
        "submitted_on": filing.submitted_on.isoformat() if filing.submitted_on else None,
        "submission_reference": filing.submission_reference,
        "submitted_by": filing.submitted_by,
        "acknowledged_on": filing.acknowledged_on.isoformat() if filing.acknowledged_on else None,
        "acknowledgement_reference": filing.acknowledgement_reference,
        "not_applicable_reason": filing.not_applicable_reason,
        "overdue": rules.is_overdue(filing.status, filing.due_on, on),
        "due_soon": rules.is_due_soon(filing.status, filing.due_on, on, due_soon_days),
    }


def _one_filing(db: Session, filing: Filing) -> dict:
    return filing_dict(filing, repo.get(db, Obligation, filing.obligation_id), today(), load_settings().due_soon_days)


def _summary_dict(s: due_rules.FilingSummary) -> dict:
    return {
        "filing_id": s.filing_id,
        "obligation_title": s.obligation_title,
        "authority": s.authority,
        "period_label": s.period_label,
        "due_on": s.due_on.isoformat(),
        "status": s.status,
        "overdue": s.overdue,
    }


def _for_due(db: Session, filings: list[Filing]) -> list[due_rules.FilingForDue]:
    by_id = repo.obligations_by_id(db, {f.obligation_id for f in filings})
    return [
        due_rules.FilingForDue(
            filing_id=f.id,
            obligation_title=by_id[f.obligation_id].title if f.obligation_id in by_id else "",
            authority=by_id[f.obligation_id].authority if f.obligation_id in by_id else "",
            period_label=f.period_label,
            due_on=f.due_on,
            status=f.status,
        )
        for f in filings
    ]


# ---------------------------------------------------------------- obligations


def list_obligations(db: Session, actor: Actor, *, authority: str | None, active: bool | None, q: str | None) -> list:
    """GET /obligations, by title. A preparer (filing:prepare without data:read or obligation:manage) sees only the
    obligations of filings they own (permissions.yaml: "See one's own filings and their obligations")."""
    require(actor, DATA_READ, OBLIGATION_MANAGE, FILING_PREPARE)
    only = None if actor.sees_all_obligations() else repo.obligation_ids_owned_by(db, actor.user_id)
    rows = repo.obligations(db, authority=authority, active=active, q=q, only_ids=only)
    return [obligation_dict(o) for o in rows]


def create_obligation(db: Session, actor: Actor, body: dict) -> dict:
    """POST /obligations. active defaults to true."""
    require(actor, OBLIGATION_MANAGE)
    obligation = Obligation(
        organisation_id=actor.organisation_id,
        title=body["title"],
        authority=body["authority"],
        portal_url=body.get("portal_url"),
        description=body.get("description"),
        recurrence=body["recurrence"],
        default_owner_id=body.get("default_owner_id"),
        active=body.get("active", True),
    )
    db.add(obligation)
    db.flush()
    _audit(db, actor, "obligation.created", OBLIGATION, obligation.id)
    db.commit()
    return obligation_dict(obligation)


def get_obligation(db: Session, actor: Actor, obligation_id: str) -> dict:
    """GET /obligations/{id} with filing_counts: one entry per FilingStatus, zeros included, in the contract's order.
    A preparer sees an obligation only when they own one of its filings, and its counts cover their filings only."""
    require(actor, DATA_READ, OBLIGATION_MANAGE, FILING_PREPARE)
    obligation = _obligation(db, obligation_id)
    owner = None if actor.sees_all_obligations() else actor.user_id
    if owner is not None and obligation.id not in repo.obligation_ids_owned_by(db, owner):
        raise _not_found("obligation")
    counts = repo.filing_counts(db, obligation.id, owner)
    return {
        **obligation_dict(obligation),
        "filing_counts": [{"status": s, "count": counts.get(s, 0)} for s in rules.FILING_STATUSES],
    }


def update_obligation(db: Session, actor: Actor, obligation_id: str, body: dict) -> dict:
    """PATCH /obligations/{id}: only the fields sent change; portal_url and default_owner_id may be cleared with
    null. An inactive obligation may be made active again. Existing filings keep their owner, dates and period; their
    obligation_title and authority are read from the obligation, so they show the new values. An empty body changes
    nothing and is not audited."""
    require(actor, OBLIGATION_MANAGE)
    obligation = _obligation(db, obligation_id, lock=True)
    if not body:
        return obligation_dict(obligation)
    deactivated = obligation.active and body.get("active") is False
    for name, value in body.items():
        setattr(obligation, name, value)
    _audit(db, actor, "obligation.deactivated" if deactivated else "obligation.updated", OBLIGATION, obligation.id)
    db.commit()
    return obligation_dict(obligation)


# ---------------------------------------------------------------- filings


def create_filing(db: Session, actor: Actor, obligation_id: str, body: dict) -> dict:
    """POST /obligations/{id}/filings: status open, owner_id defaulting to the obligation's default owner (422 when
    there is neither). The obligation row is locked so a concurrent deactivation cannot slip in between. due_on is
    not tied to the period: a return can be due before the period ends (advance filings) or long after it."""
    require(actor, FILING_MANAGE)
    obligation = _obligation(db, obligation_id, lock=True)
    _domain(rules.check_obligation_active, obligation.active)
    for field in ("period_start", "period_end", "due_on"):
        _domain(rules.check_date, body[field], field)
    _domain(rules.check_period, body["period_start"], body["period_end"])
    owner = _domain(rules.resolve_owner, body.get("owner_id"), obligation.default_owner_id)
    if repo.filing_with_label(db, obligation.id, body["period_label"]) is not None:
        raise _period_taken()
    filing = Filing(
        organisation_id=actor.organisation_id,
        obligation_id=obligation.id,
        period_label=body["period_label"],
        period_start=body["period_start"],
        period_end=body["period_end"],
        due_on=body["due_on"],
        owner_id=owner,
        status=rules.OPEN,
        links=[],
    )
    db.add(filing)
    _flush_unique(db)
    _audit(db, actor, "filing.created", FILING, filing.id)
    db.commit()
    return filing_dict(filing, obligation, today(), load_settings().due_soon_days)


def list_filings(
    db: Session,
    actor: Actor,
    *,
    obligation_id: str | None,
    statuses: list[str] | None,
    owner: str | None,
    overdue: bool | None,
    due_before: date | None,
    cursor: str | None,
    limit: int,
) -> dict:
    """GET /filings, soonest due first. owner=me means the caller. A preparer sees only their own filings: asking for
    another owner gives an empty page, not a 403."""
    require(actor, DATA_READ, FILING_MANAGE, FILING_PREPARE)
    try:
        offset = repo.decode_cursor(cursor)
    except ValueError:
        raise _invalid("invalid_cursor", "cursor is not one this API returned", "cursor") from None
    owner_id = actor.user_id if owner == "me" else owner
    if not actor.sees_all_filings():
        if owner_id and owner_id != actor.user_id:
            return {"items": [], "next_cursor": None}
        owner_id = actor.user_id
    if due_before is not None:
        _domain(rules.check_date, due_before, "due_before")
    on = today()
    rows, more = repo.filings_page(
        db,
        today=on,
        obligation_id=obligation_id,
        statuses=statuses,
        owner_id=owner_id,
        overdue=overdue,
        due_before=due_before,
        offset=offset,
        limit=limit,
    )
    by_id = repo.obligations_by_id(db, {f.obligation_id for f in rows})
    days = load_settings().due_soon_days
    next_offset = offset + limit
    return {
        "items": [filing_dict(f, by_id.get(f.obligation_id), on, days) for f in rows],
        "next_cursor": repo.encode_cursor(next_offset) if more and next_offset <= repo.MAX_OFFSET else None,
    }


def get_filing(db: Session, actor: Actor, filing_id: str) -> dict:
    require(actor, DATA_READ, FILING_MANAGE, FILING_PREPARE)
    return _one_filing(db, _filing(db, actor, filing_id))


def update_filing(db: Session, actor: Actor, filing_id: str, body: dict) -> dict:
    """PATCH /filings/{id}: only the fields sent change. preparation_notes and links: the owner with filing:prepare,
    or filing:manage, while open or in_preparation. owner_id, due_on and the period: filing:manage only, while not yet
    submitted (also under review, so the coordinator can correct a due date during review). 403 for a field the caller
    may not change, 409 for a status that does not allow it, 409 when the new period label is taken. An empty body
    changes nothing and is not audited."""
    require(actor, FILING_PREPARE, FILING_MANAGE)
    filing = _filing(db, actor, filing_id, lock=True)
    fields = set(body)
    manager = actor.can(FILING_MANAGE)
    if fields & rules.MANAGER_FIELDS and not manager:
        raise forbidden(f"changing {', '.join(sorted(fields & rules.MANAGER_FIELDS))} needs {FILING_MANAGE}")
    if fields & rules.OWNER_FIELDS and not (manager or filing.owner_id == actor.user_id):
        raise forbidden(f"only the owner or {FILING_MANAGE} may change notes and links")
    if not fields:
        return _one_filing(db, filing)
    _domain(rules.check_editable, filing.status, fields)
    for field in ("period_start", "period_end", "due_on"):
        if field in body:
            _domain(rules.check_date, body[field], field)
    _domain(
        rules.check_period, body.get("period_start", filing.period_start), body.get("period_end", filing.period_end)
    )
    label = body.get("period_label")
    if label is not None and label != filing.period_label:
        if repo.filing_with_label(db, filing.obligation_id, label) is not None:
            raise _period_taken()
    for name, value in body.items():
        setattr(filing, name, list(value or []) if name == "links" else value)
    _flush_unique(db)
    _audit(db, actor, "filing.updated", FILING, filing.id)
    db.commit()
    return _one_filing(db, filing)


def move_filing(db: Session, actor: Actor, filing_id: str, body: dict) -> dict:
    """POST /filings/{id}/status. open -> in_preparation and in_preparation -> under_review: the owner with
    filing:prepare, or filing:manage. under_review -> in_preparation (a return, needs a comment, kept as
    review_comment until the next return) and open or in_preparation -> not_applicable (needs a reason): filing:manage.
    Checked in this order: the move exists (409), the caller may make it (403), the note is there (422)."""
    require(actor, FILING_PREPARE, FILING_MANAGE)
    filing = _filing(db, actor, filing_id, lock=True)
    move = _domain(rules.transition, filing.status, body["status"])
    manager = actor.can(FILING_MANAGE)
    owner = actor.can(FILING_PREPARE) and filing.owner_id == actor.user_id
    if not (manager or (owner and move in rules.OWNER_MOVES)):
        raise forbidden(f"this move needs {FILING_MANAGE}" if owner else "only the owner or a manager may move it")
    comment, reason = body.get("comment"), body.get("reason")
    _domain(rules.check_note, move, comment, reason)
    filing.status = body["status"]
    note = None
    if move == rules.RETURN:
        filing.review_comment = note = comment.strip()
    elif move == rules.MARK_NOT_APPLICABLE:
        filing.not_applicable_reason = note = reason.strip()
    action = {rules.RETURN: "filing.returned"}.get(move, f"filing.{filing.status}")
    _audit(db, actor, action, FILING, filing.id, note)
    db.commit()
    return _one_filing(db, filing)


def submit_filing(db: Session, actor: Actor, filing_id: str, body: dict) -> dict:
    """POST /filings/{id}/submit: under_review -> submitted with the date and the authority's reference;
    submitted_by is the caller. submitted_on may not be after today (422): it records a submission that happened."""
    require(actor, FILING_MANAGE)
    filing = _filing(db, actor, filing_id, lock=True)
    status = _domain(rules.submit, filing.status)
    _domain(rules.check_recorded_on, body["submitted_on"], today(), "submitted_on")
    filing.status = status
    filing.submitted_on = body["submitted_on"]
    filing.submission_reference = body["submission_reference"]
    filing.submitted_by = actor.user_id
    _audit(db, actor, "filing.submitted", FILING, filing.id)
    _publish(
        db,
        actor,
        "submitted",
        {
            "filing_id": filing.id,
            "obligation_id": filing.obligation_id,
            "period_label": filing.period_label,
            "submitted_on": filing.submitted_on.isoformat(),
        },
    )
    db.commit()
    return _one_filing(db, filing)


def acknowledge_filing(db: Session, actor: Actor, filing_id: str, body: dict) -> dict:
    """POST /filings/{id}/acknowledge: submitted -> acknowledged (final). acknowledged_on may be neither after today
    nor before submitted_on (422)."""
    require(actor, FILING_MANAGE)
    filing = _filing(db, actor, filing_id, lock=True)
    status = _domain(rules.acknowledge, filing.status)
    _domain(rules.check_recorded_on, body["acknowledged_on"], today(), "acknowledged_on", filing.submitted_on)
    filing.status = status
    filing.acknowledged_on = body["acknowledged_on"]
    filing.acknowledgement_reference = body.get("acknowledgement_reference")
    _audit(db, actor, "filing.acknowledged", FILING, filing.id)
    _publish(
        db,
        actor,
        "acknowledged",
        {
            "filing_id": filing.id,
            "obligation_id": filing.obligation_id,
            "acknowledged_on": filing.acknowledged_on.isoformat(),
        },
    )
    db.commit()
    return _one_filing(db, filing)


# ---------------------------------------------------------------- widgets


def due_stats(db: Session, actor: Actor, scope: str) -> dict:
    """GET /stats/due, behind regulatory-reports.due. scope=mine counts the caller's own filings whatever else they
    may read; scope=all needs data:read (403)."""
    require(actor, STATS_READ)
    if scope == "all":
        require(actor, DATA_READ)
    days = load_settings().due_soon_days
    on = today()
    cutoff = on + timedelta(days=min(days, (date.max - on).days))
    rows = repo.open_filings_due_by(db, cutoff, None if scope == "all" else actor.user_id)
    result = due_rules.due_stats(_for_due(db, rows), scope, days, on)
    return {
        "scope": result.scope,
        "due_soon_days": result.due_soon_days,
        "due_soon": result.due_soon,
        "overdue": result.overdue,
        "soonest": [_summary_dict(s) for s in result.soonest],
    }


def calendar(db: Session, actor: Actor, start: date, end: date) -> dict:
    """GET /calendar, behind regulatory-reports.compliance-calendar: needs data:read and stats:read (403). from and
    to are both included; "at most REGULATORY_REPORTS_CALENDAR_MAX_DAYS apart" means to - from <= that many days."""
    require_all(actor, DATA_READ, STATS_READ)
    _domain(due_rules.check_range, start, end, load_settings().calendar_max_days)
    rows = repo.filings_due_between(db, start, end)
    items = due_rules.calendar(_for_due(db, rows), start, end, today())
    return {"from": start.isoformat(), "to": end.isoformat(), "items": [_summary_dict(s) for s in items]}
