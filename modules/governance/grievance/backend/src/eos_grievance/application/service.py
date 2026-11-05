"""Use cases of grievance (docs/prd.md, contracts/openapi.yaml). Each one checks the caller's permission and, for case
operations, their committee membership; checks the domain rules; changes state; writes an audit entry; and publishes the
matching event from contracts/events.yaml to the outbox in the same transaction. Notices to committee members and
complainants go out after the commit and carry the case number only.

Where the contract leaves a detail open, the choice made here is noted at the function. Choices that hold for the whole
module:

- Case content is visible to the complainant (own cases, without proceedings) and to members of the committee that
  filed-with or was appealed to; operations that change a case need the committee that handles it now: the committee
  the case was filed with or transferred to, and from `appealed` on the ombudsperson committee the appeal went to. A
  case a caller may not see is "not found" (404), never "forbidden".
- Listing cases and reading one are audited for every case returned (PRD "Audit").
- Due dates are worked out when read (domain.cases.due_at); with no setting a case has no due date and is never overdue.
- A committee member may also be a complainant; nothing stops a member from handling a case they filed (PRD open
  question 7 leaves composition rules to the organisation).
"""

from __future__ import annotations

from datetime import datetime

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import cases as rules
from ..domain.errors import DomainRuleError
from ..infrastructure import notifier
from ..infrastructure import repository as repo
from ..infrastructure.config import ModuleSettings, load_settings
from ..infrastructure.models import (
    Appeal,
    AuditEntry,
    Committee,
    Decision,
    Grievance,
    Proceeding,
    Update,
    as_utc,
    iso,
)
from .access import (
    APPEAL_DECIDE,
    CASE_FILE,
    CASE_MANAGE,
    CASE_READ,
    CASE_READ_OWN,
    COMMITTEE_MANAGE,
    MODULE,
    STATS_READ,
    Actor,
    require,
)
from .errors import GrievanceError, conflict, forbidden, from_domain, invalid, not_found

CASE, COMMITTEE = "case", "committee"  # audit entities

Notice = tuple[list[str], str]  # (person ids, case number)


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


# ---------------------------------------------------------------- helpers


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
        f"{MODULE}.case.{name}",
        actor.organisation_id,
        {"organisation_id": actor.organisation_id, **payload},
        actor=actor.user_id,
    )


def _commit(db: Session, actor: Actor, notices: list[Notice] | None = None) -> None:
    """Commit the change with its audit entries and events, then send the notices."""
    db.commit()
    for person_ids, number in notices or []:
        notifier.send(actor.organisation_id, [p for p in person_ids if p != actor.user_id], number)


def _offset(cursor: str | None) -> int:
    try:
        return repo.decode_cursor(cursor)
    except ValueError:
        raise invalid("invalid_cursor", "cursor is not one this API handed out") from None


def _member_ids(db: Session, committee_id: str) -> list[str]:
    return [m.person_id for m in repo.members_of(db, [committee_id])[committee_id]]


def _check_members(members: list[dict]) -> None:
    ids = [m["person_id"].lower() for m in members]
    if len(set(ids)) != len(ids):
        raise invalid("duplicate_member", "a person can be listed once on a committee")


# ---------------------------------------------------------------- serialisation (contract schemas)


def committee_dict(db: Session, committees: list[Committee], *, with_members: set[str] | None = None) -> list[dict]:
    """Committees; members only for the ids in `with_members` (None: for all)."""
    shown = [c.id for c in committees if with_members is None or c.id in with_members]
    members = repo.members_of(db, shown)
    out = []
    for c in committees:
        item = {
            "id": c.id,
            "organisation_id": c.organisation_id,
            "name": c.name,
            "kind": c.kind,
            "active": c.active,
        }
        if c.id in members:
            item["members"] = [{"person_id": m.person_id, "role": m.role} for m in members[c.id]]
        out.append(item)
    return out


def _respondent(case: Grievance) -> dict | None:
    out = {}
    if case.respondent_person_id:
        out["person_id"] = case.respondent_person_id
    if case.respondent_description:
        out["description"] = case.respondent_description
    return out or None


def _due(case: Grievance, settings: ModuleSettings) -> datetime | None:
    return rules.due_at(
        case.status,
        as_utc(case.filed_at),
        settings.acknowledge_days.get(case.track),
        settings.decide_days.get(case.track),
        settings.day_counting,
    )


def case_dict(case: Grievance, now: datetime, settings: ModuleSettings) -> dict:
    """A case as committee members see it (contract Grievance)."""
    due = _due(case, settings)
    return {
        "id": case.id,
        "organisation_id": case.organisation_id,
        "number": case.number,
        "track": case.track,
        "committee_id": case.committee_id,
        "complainant_id": case.complainant_id,
        "respondent": _respondent(case),
        "category": case.category,
        "description": case.description,
        "incident_date": iso(case.incident_date),
        "status": case.status,
        "closure": case.closure,
        "filed_at": iso(case.filed_at),
        "acknowledged_at": iso(case.acknowledged_at),
        "decided_at": iso(case.decided_at),
        "closed_at": iso(case.closed_at),
        "due_at": iso(due),
        "overdue": rules.is_overdue(case.status, due, now),
    }


def my_case_dict(case: Grievance, now: datetime, settings: ModuleSettings) -> dict:
    """A case as its complainant sees it (contract MyGrievance): no respondent, no due date, no committee-side data."""
    can_appeal = (
        case.status == "decided"
        and case.track == "student_grievance"
        and rules.appeal_open(as_utc(case.decided_at), settings.appeal_window_days, settings.day_counting, now)
    )
    return {
        "id": case.id,
        "number": case.number,
        "track": case.track,
        "committee_id": case.committee_id,
        "category": case.category,
        "description": case.description,
        "incident_date": iso(case.incident_date),
        "status": case.status,
        "filed_at": iso(case.filed_at),
        "acknowledged_at": iso(case.acknowledged_at),
        "decided_at": iso(case.decided_at),
        "closed_at": iso(case.closed_at),
        "can_appeal": can_appeal,
    }


def update_dict(u: Update) -> dict:
    return {
        "id": u.id,
        "grievance_id": u.grievance_id,
        "author_id": u.author_id,
        "from_committee": u.from_committee,
        "body": u.body,
        "created_at": iso(u.created_at),
    }


def proceeding_dict(p: Proceeding) -> dict:
    return {
        "id": p.id,
        "grievance_id": p.grievance_id,
        "kind": p.kind,
        "held_on": iso(p.held_on),
        "summary": p.summary,
        "recorded_by": p.recorded_by,
        "created_at": iso(p.created_at),
    }


def decision_dict(d: Decision | None) -> dict | None:
    if d is None:
        return None
    return {
        "outcome": d.outcome,
        "findings": d.findings,
        "actions_recommended": d.actions_recommended,
        "decided_by": d.decided_by,
        "decided_at": iso(d.decided_at),
    }


def appeal_dict(a: Appeal | None) -> dict | None:
    if a is None:
        return None
    return {
        "committee_id": a.committee_id,
        "reason": a.reason,
        "filed_at": iso(a.filed_at),
        "outcome": a.outcome,
        "outcome_note": a.outcome_note,
        "decided_by": a.decided_by,
        "decided_at": iso(a.decided_at),
    }


def detail_dict(db: Session, case: Grievance, now: datetime, settings: ModuleSettings) -> dict:
    """The full case with proceedings (contract GrievanceDetail)."""
    return {
        **case_dict(case, now, settings),
        "updates": [update_dict(u) for u in repo.updates_of(db, case.id)],
        "proceedings": [proceeding_dict(p) for p in repo.proceedings_of(db, case.id)],
        "decision": decision_dict(repo.decision_of(db, case.id)),
        "appeal": appeal_dict(repo.appeals_for(db, [case.id]).get(case.id)),
    }


def my_detail_dict(db: Session, case: Grievance, now: datetime, settings: ModuleSettings) -> dict:
    """The case for its complainant, with updates, decision and appeal and never proceedings (MyGrievanceDetail)."""
    return {
        **my_case_dict(case, now, settings),
        "updates": [update_dict(u) for u in repo.updates_of(db, case.id)],
        "not_admitted_reason": case.not_admitted_reason,
        "decision": decision_dict(repo.decision_of(db, case.id)),
        "appeal": appeal_dict(repo.appeals_for(db, [case.id]).get(case.id)),
    }


# ---------------------------------------------------------------- committees


def list_committees(db: Session, actor: Actor, kind: str | None, active: bool | None) -> list[dict]:
    """Members are listed to coordinators and to the members of that committee; everyone else sees id, name, kind and
    whether it is active, to choose where to file."""
    require(actor, COMMITTEE_MANAGE, CASE_READ, CASE_FILE)
    rows = repo.committees(db, kind, active)
    shown = None if actor.can(COMMITTEE_MANAGE) else set(repo.memberships_of(db, actor.user_id))
    return committee_dict(db, rows, with_members=shown)


def _name_taken() -> GrievanceError:
    return conflict("name_used", "a committee with this name already exists")


def _flush_unique(db: Session, error: GrievanceError) -> None:
    """Flush; a concurrent request that took the same name first is a 409, not a 500."""
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise error from None


def create_committee(db: Session, actor: Actor, data: dict) -> dict:
    require(actor, COMMITTEE_MANAGE)
    members = data.get("members") or []
    _check_members(members)
    if repo.committee_by_name(db, data["name"]) is not None:
        raise _name_taken()
    committee = Committee(
        organisation_id=actor.organisation_id, name=data["name"], kind=data["kind"], active=data.get("active", True)
    )
    db.add(committee)
    _flush_unique(db, _name_taken())
    repo.replace_members(db, committee.id, members, actor.organisation_id)
    _audit(db, actor, "committee.created", COMMITTEE, committee.id)
    db.flush()
    out = committee_dict(db, [committee])[0]
    _commit(db, actor)
    return out


def update_committee(db: Session, actor: Actor, committee_id: str, data: dict) -> dict:
    """Rename, replace the members or (de)activate. A committee that still has open cases cannot be deactivated."""
    require(actor, COMMITTEE_MANAGE)
    committee = repo.get(db, Committee, committee_id, lock=True)
    if committee is None:
        raise not_found("committee")
    if "name" in data and data["name"].lower() != committee.name.lower():
        if repo.committee_by_name(db, data["name"]) is not None:
            raise _name_taken()
    if "name" in data and data["name"] != committee.name:
        committee.name = data["name"]
        _audit(db, actor, "committee.renamed", COMMITTEE, committee.id)
    if "members" in data:
        _check_members(data["members"])
        repo.replace_members(db, committee.id, data["members"], actor.organisation_id)
        _audit(db, actor, "committee.members_changed", COMMITTEE, committee.id)
    if "active" in data and data["active"] != committee.active:
        if not data["active"] and repo.committee_has_open_cases(db, committee.id):
            raise conflict("committee_has_open_cases", "a committee with open cases cannot be deactivated")
        committee.active = data["active"]
        _audit(
            db, actor, "committee.activated" if committee.active else "committee.deactivated", COMMITTEE, committee.id
        )
    _flush_unique(db, _name_taken())
    out = committee_dict(db, [committee])[0]
    _commit(db, actor)
    return out


# ---------------------------------------------------------------- the caller's own cases (/me)


def _filing_committee(db: Session, track: str, committee_id: str | None) -> Committee:
    """The committee a new case goes to: the one named, or the only active one of the track's kind."""
    kind = rules.KIND_FOR_TRACK[track]
    if committee_id is not None:
        committee = repo.get(db, Committee, committee_id)
        if committee is None:
            raise invalid("committee_not_found", "committee not found in your organisation")
        if not committee.active:
            raise invalid("committee_inactive", "this committee is not active")
        if not rules.committee_fits_track(committee.kind, track):
            raise invalid("committee_wrong_kind", f"a {track} case is heard by a {kind} committee")
        return committee
    found = repo.active_committees_of_kind(db, kind)
    if not found:
        raise invalid("no_active_committee", f"there is no active {kind} committee for this track")
    if len(found) > 1:
        raise invalid("committee_required", f"choose one of the {len(found)} active {kind} committees")
    return found[0]


def file_case(db: Session, actor: Actor, data: dict) -> dict:
    require(actor, CASE_FILE)
    settings, now = load_settings(), clock()
    committee = _filing_committee(db, data["track"], data.get("committee_id"))
    respondent = data.get("respondent") or {}
    sequence = repo.next_sequence(db)
    case = Grievance(
        organisation_id=actor.organisation_id,
        sequence=sequence,
        number=f"{settings.case_number_prefix}-{sequence:06d}",
        track=data["track"],
        committee_id=committee.id,
        complainant_id=actor.user_id,
        respondent_person_id=respondent.get("person_id"),
        respondent_description=respondent.get("description"),
        category=data["category"],
        description=data["description"],
        incident_date=data.get("incident_date"),
        status="submitted",
        filed_at=now,
    )
    db.add(case)
    _flush_unique(db, conflict("number_taken", "the case number was taken by another request; try again"))
    _audit(db, actor, "case.filed", CASE, case.id)
    _publish(
        db,
        actor,
        "filed",
        {
            "case_id": case.id,
            "number": case.number,
            "track": case.track,
            "committee_id": case.committee_id,
            "filed_at": iso(case.filed_at),
        },
    )
    out = my_case_dict(case, now, settings)
    notices = [(_member_ids(db, committee.id), case.number)]
    _commit(db, actor, notices)
    return out


def list_my_cases(db: Session, actor: Actor, statuses: list[str] | None, cursor: str | None, limit: int) -> dict:
    require(actor, CASE_READ_OWN)
    offset = _offset(cursor)
    settings, now = load_settings(), clock()
    rows = list(db.scalars(repo.my_cases(db, actor.user_id, statuses).offset(offset).limit(limit + 1)))
    page, next_cursor = rows[:limit], repo.encode_cursor(offset + limit) if len(rows) > limit else None
    return {"items": [my_case_dict(c, now, settings) for c in page], "next_cursor": next_cursor}


def _own_case(db: Session, actor: Actor, case_id: str, *, lock: bool = False) -> Grievance:
    case = repo.get(db, Grievance, case_id, lock=lock)
    if case is None or case.complainant_id != actor.user_id:
        raise not_found("case")  # another person's case is "not found" (contract)
    return case


def get_my_case(db: Session, actor: Actor, case_id: str) -> dict:
    require(actor, CASE_READ_OWN)
    return my_detail_dict(db, _own_case(db, actor, case_id), clock(), load_settings())


def _handling_committee(case: Grievance, appeal: Appeal | None) -> str:
    """The committee that works the case now: the ombudsperson committee from `appealed` on, else the case's own."""
    if appeal is not None and case.status in rules.APPEALED_STATUSES:
        return appeal.committee_id
    return case.committee_id


def _not_final(case: Grievance) -> None:
    if case.status in rules.FINAL_STATUSES:
        raise conflict("case_final", f"case {case.number} is {case.status}")


def _add_update(db: Session, actor: Actor, case: Grievance, body: str, *, from_committee: bool) -> Update:
    update = Update(
        organisation_id=actor.organisation_id,
        grievance_id=case.id,
        author_id=actor.user_id,
        from_committee=from_committee,
        body=body,
        created_at=clock(),
    )
    db.add(update)
    db.flush()
    _audit(db, actor, "update.added", CASE, case.id)
    return update


def add_my_update(db: Session, actor: Actor, case_id: str, body: str) -> dict:
    """The complainant adds information or answers the committee; the committee handling the case is notified."""
    require(actor, CASE_READ_OWN)
    case = _own_case(db, actor, case_id, lock=True)
    _not_final(case)
    appeal = repo.appeals_for(db, [case.id]).get(case.id)
    update = _add_update(db, actor, case, body, from_committee=False)
    out = update_dict(update)
    _commit(db, actor, [(_member_ids(db, _handling_committee(case, appeal)), case.number)])
    return out


def _close(db: Session, actor: Actor, case: Grievance, status: str, closure: str, now: datetime) -> None:
    """Move the case to a final state and publish grievance.case.closed."""
    case.status, case.closure, case.closed_at = status, closure, now
    appealed = repo.appeals_for(db, [case.id]).get(case.id) is not None
    _publish(
        db,
        actor,
        "closed",
        {
            "case_id": case.id,
            "number": case.number,
            "track": case.track,
            "committee_id": case.committee_id,
            "closure": closure,
            "appealed": appealed,
            "closed_at": iso(now),
        },
    )


def withdraw_case(db: Session, actor: Actor, case_id: str, reason: str | None) -> dict:
    """Before a decision: submitted, acknowledged or under_inquiry -> withdrawn (final)."""
    require(actor, CASE_READ_OWN)
    settings, now = load_settings(), clock()
    case = _own_case(db, actor, case_id, lock=True)
    if case.status not in rules.WITHDRAWABLE:
        raise conflict("invalid_status", f"a {case.status} case cannot be withdrawn")
    _close(db, actor, case, "withdrawn", "withdrawn", now)
    _audit(db, actor, "case.withdrawn", CASE, case.id, reason)
    out = my_case_dict(case, now, settings)
    _commit(db, actor, [(_member_ids(db, case.committee_id), case.number)])
    return out


def appeal_case(db: Session, actor: Actor, case_id: str, reason: str) -> dict:
    """decided -> appealed, on the student_grievance track, inside GRIEVANCE_APPEAL_WINDOW_DAYS. With no window
    configured no appeal is accepted. The appeal goes to the organisation's active ombudsperson committee; when there
    are several, the oldest."""
    require(actor, CASE_READ_OWN)
    settings, now = load_settings(), clock()
    case = _own_case(db, actor, case_id, lock=True)
    if case.status != "decided":
        raise conflict("invalid_status", f"a {case.status} case cannot be appealed")
    if case.track != "student_grievance":
        raise conflict("appeal_not_allowed", "only student grievance decisions can be appealed")
    if settings.appeal_window_days is None:
        raise conflict("appeal_window_not_configured", "Appeal window is not configured")
    if not rules.appeal_open(as_utc(case.decided_at), settings.appeal_window_days, settings.day_counting, now):
        raise conflict("appeal_window_passed", "the appeal window has passed")
    ombudsperson = repo.active_committees_of_kind(db, "ombudsperson")
    if not ombudsperson:
        raise conflict("no_ombudsperson", "there is no active ombudsperson committee to hear the appeal")
    target = ombudsperson[0]
    db.add(
        Appeal(
            organisation_id=actor.organisation_id,
            grievance_id=case.id,
            committee_id=target.id,
            reason=reason,
            filed_at=now,
        )
    )
    case.status = "appealed"
    _audit(db, actor, "case.appealed", CASE, case.id)
    db.flush()
    out = my_case_dict(case, now, settings)
    _commit(db, actor, [(_member_ids(db, target.id), case.number)])
    return out


# ---------------------------------------------------------------- committee side


def _visible_case(db: Session, actor: Actor, case_id: str, *, lock: bool = False):
    """(case, appeal, the caller's committees) when the caller sits on the committee the case was filed with or the one
    it was appealed to; 404 otherwise, whatever permission they hold."""
    case = repo.get(db, Grievance, case_id, lock=lock)
    mine = repo.memberships_of(db, actor.user_id)
    appeal = repo.appeals_for(db, [case.id]).get(case.id) if case is not None else None
    if case is None or not (case.committee_id in mine or (appeal is not None and appeal.committee_id in mine)):
        raise not_found("case")
    return case, appeal, mine


def _handled_case(db: Session, actor: Actor, case_id: str):
    """Like _visible_case, for a change: the caller must sit on the committee that handles the case now."""
    require(actor, CASE_MANAGE)
    case, appeal, mine = _visible_case(db, actor, case_id, lock=True)
    if _handling_committee(case, appeal) not in mine:
        raise forbidden("the case is handled by another committee")
    return case, appeal


def list_cases(
    db: Session,
    actor: Actor,
    *,
    committee_id: str | None,
    track: str | None,
    statuses: list[str] | None,
    overdue: bool | None,
    cursor: str | None,
    limit: int,
) -> dict:
    """Cases of the caller's committees, and cases appealed to them, newest first. overdue is worked out when read, so
    it filters after the query."""
    require(actor, CASE_READ)
    offset = _offset(cursor)
    settings, now = load_settings(), clock()
    mine = list(repo.memberships_of(db, actor.user_id))
    if not mine:
        return {"items": [], "next_cursor": None}
    query = repo.committee_cases(db, mine, committee_id=committee_id, track=track, statuses=statuses)
    if overdue is None:
        rows = list(db.scalars(query.offset(offset).limit(limit + 1)))
        page, next_cursor = rows[:limit], repo.encode_cursor(offset + limit) if len(rows) > limit else None
    else:
        matching = [c for c in db.scalars(query) if rules.is_overdue(c.status, _due(c, settings), now) is overdue]
        page, next_cursor = repo.slice_page(matching, offset, limit)
    for c in page:
        _audit(db, actor, "case.listed", CASE, c.id)
    out = {"items": [case_dict(c, now, settings) for c in page], "next_cursor": next_cursor}
    _commit(db, actor)
    return out


def get_case(db: Session, actor: Actor, case_id: str) -> dict:
    """The full case including proceedings. The read is audited."""
    require(actor, CASE_READ)
    case, _, _ = _visible_case(db, actor, case_id)
    _audit(db, actor, "case.read", CASE, case.id)
    out = detail_dict(db, case, clock(), load_settings())
    _commit(db, actor)
    return out


def move_case(db: Session, actor: Actor, case_id: str, status: str, reason: str | None) -> dict:
    """submitted -> acknowledged; acknowledged -> under_inquiry; submitted -> not_admitted (needs a reason);
    decided -> closed (after the appeal window on the student_grievance track, at once elsewhere); appeal_decided ->
    closed. With no appeal window configured, no appeal can be made, so a decided case closes at once."""
    settings, now = load_settings(), clock()
    case, _ = _handled_case(db, actor, case_id)
    _domain(rules.check_move, case.status, status)
    if status == "not_admitted" and not (reason and reason.strip()):
        raise invalid("reason_required", "a reason is required to not admit a case")
    if (
        status == "closed"
        and case.status == "decided"
        and case.track == "student_grievance"
        and rules.appeal_open(as_utc(case.decided_at), settings.appeal_window_days, settings.day_counting, now)
    ):
        raise conflict("appeal_window_open", "the complainant can still appeal; close the case after the window")
    previous = case.status
    if status == "acknowledged":
        case.status, case.acknowledged_at = status, now
    elif status == "under_inquiry":
        case.status = status
    elif status == "not_admitted":
        case.not_admitted_reason = reason
        _close(db, actor, case, "not_admitted", "not_admitted", now)
    else:
        _close(db, actor, case, "closed", "decided", now)
    _audit(db, actor, f"case.{previous}_to_{case.status}", CASE, case.id, reason if status == "not_admitted" else None)
    out = case_dict(case, now, settings)
    _commit(db, actor, [([case.complainant_id], case.number)])
    return out


def add_update(db: Session, actor: Actor, case_id: str, body: str) -> dict:
    """A message to the complainant, for example to ask for information."""
    case, _ = _handled_case(db, actor, case_id)
    _not_final(case)
    update = _add_update(db, actor, case, body, from_committee=True)
    out = update_dict(update)
    _commit(db, actor, [([case.complainant_id], case.number)])
    return out


def add_proceeding(db: Session, actor: Actor, case_id: str, data: dict) -> dict:
    case, _ = _handled_case(db, actor, case_id)
    if case.status not in rules.PROCEEDING_STATUSES:
        raise conflict("invalid_status", "proceedings are recorded on an acknowledged or under-inquiry case")
    proceeding = Proceeding(
        organisation_id=actor.organisation_id,
        grievance_id=case.id,
        kind=data["kind"],
        held_on=data["held_on"],
        summary=data["summary"],
        recorded_by=actor.user_id,
        created_at=clock(),
    )
    db.add(proceeding)
    db.flush()
    _audit(db, actor, "proceeding.recorded", CASE, case.id)
    out = proceeding_dict(proceeding)
    _commit(db, actor)
    return out


def decide_case(db: Session, actor: Actor, case_id: str, data: dict) -> dict:
    """under_inquiry -> decided."""
    settings, now = load_settings(), clock()
    case, _ = _handled_case(db, actor, case_id)
    if case.status != "under_inquiry":
        raise conflict("invalid_status", "a decision is recorded on a case under inquiry")
    db.add(
        Decision(
            organisation_id=actor.organisation_id,
            grievance_id=case.id,
            outcome=data["outcome"],
            findings=data["findings"],
            actions_recommended=data.get("actions_recommended"),
            decided_by=actor.user_id,
            decided_at=now,
        )
    )
    case.status, case.decided_at = "decided", now
    _audit(db, actor, "case.decided", CASE, case.id)
    db.flush()
    out = detail_dict(db, case, now, settings)
    _commit(db, actor, [([case.complainant_id], case.number)])
    return out


def transfer_case(db: Session, actor: Actor, case_id: str, data: dict) -> dict:
    """Before a decision, to another active committee that is not an ombudsperson committee. The track follows the new
    committee's kind. The members of the new committee are notified."""
    settings, now = load_settings(), clock()
    case, _ = _handled_case(db, actor, case_id)
    if case.status not in rules.TRANSFERABLE:
        raise conflict("invalid_status", f"a {case.status} case cannot be transferred")
    target = repo.get(db, Committee, data["committee_id"])
    if target is None:
        raise not_found("committee")
    if target.id == case.committee_id:
        raise conflict("same_committee", "the case is already with this committee")
    if not target.active:
        raise conflict("committee_inactive", "this committee is not active")
    if target.kind == "ombudsperson":
        raise conflict("committee_kind_invalid", "cases are not transferred to an ombudsperson committee")
    case.committee_id, case.track = target.id, rules.TRACK_FOR_KIND[target.kind]
    _audit(db, actor, "case.transferred", CASE, case.id, data["reason"])
    out = case_dict(case, now, settings)
    _commit(db, actor, [(_member_ids(db, target.id), case.number)])
    return out


def decide_appeal(db: Session, actor: Actor, case_id: str, data: dict) -> dict:
    """appealed -> appeal_decided, by a member of the ombudsperson committee the appeal went to."""
    require(actor, APPEAL_DECIDE)
    settings, now = load_settings(), clock()
    case, appeal, mine = _visible_case(db, actor, case_id, lock=True)
    if case.status != "appealed" or appeal is None:
        raise conflict("not_appealed", "the case has no appeal waiting for a decision")
    if appeal.committee_id not in mine:
        raise forbidden("the appeal went to another committee")
    appeal.outcome, appeal.outcome_note = data["outcome"], data["outcome_note"]
    appeal.decided_by, appeal.decided_at = actor.user_id, now
    case.status = "appeal_decided"
    _audit(db, actor, "appeal.decided", CASE, case.id)
    db.flush()
    out = detail_dict(db, case, now, settings)
    _commit(db, actor, [([case.complainant_id], case.number)])
    return out


# ---------------------------------------------------------------- counts (widgets)


def _open_rows(db: Session, settings: ModuleSettings, now: datetime) -> list[dict]:
    rows = []
    for _case_id, track, status, filed_at, handling in repo.open_cases(db):
        due = rules.due_at(
            status,
            as_utc(filed_at),
            settings.acknowledge_days.get(track),
            settings.decide_days.get(track),
            settings.day_counting,
        )
        rows.append(
            {
                "track": track,
                "status": status,
                "committee_id": handling,
                "overdue": rules.is_overdue(status, due, now),
            }
        )
    return rows


def open_by_committee(db: Session, actor: Actor) -> dict:
    """Open cases per committee and status, with overdue counts; no case content. Appealed cases count under the
    ombudsperson committee. Active committees are listed even with nothing open."""
    require(actor, STATS_READ)
    rows = _open_rows(db, load_settings(), clock())
    items = []
    for c in repo.committees(db):
        mine = [r for r in rows if r["committee_id"] == c.id]
        if not c.active and not mine:
            continue
        by_status = [
            {"status": s, "count": n} for s in rules.OPEN_STATUSES if (n := sum(1 for r in mine if r["status"] == s))
        ]
        items.append(
            {
                "committee_id": c.id,
                "name": c.name,
                "kind": c.kind,
                "open": len(mine),
                "overdue": sum(1 for r in mine if r["overdue"]),
                "by_status": by_status,
            }
        )
    return {"total_open": len(rows), "committees": items}


def open_by_track(db: Session, actor: Actor) -> dict:
    """Open cases per track, with overdue counts; every track is listed."""
    require(actor, STATS_READ)
    rows = _open_rows(db, load_settings(), clock())
    tracks = [
        {
            "track": t,
            "open": sum(1 for r in rows if r["track"] == t),
            "overdue": sum(1 for r in rows if r["track"] == t and r["overdue"]),
        }
        for t in rules.TRACKS
    ]
    return {"total_open": len(rows), "overdue": sum(1 for r in rows if r["overdue"]), "tracks": tracks}
