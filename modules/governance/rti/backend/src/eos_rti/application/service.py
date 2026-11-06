"""Use cases of rti (docs/prd.md, contracts/openapi.yaml). Each one checks the domain rules, changes state, writes an
audit entry, and publishes the matching event from contracts/events.yaml to the outbox in the same transaction.
Event payloads carry identifiers and metadata only: never the applicant, the subject, the information sought, fee
details, referral questions or replies, the response summary or grounds, the transfer authority or appeal text.

Where the contract leaves a detail open, the choice made here is noted at the function and in the README under
"Assumptions to revisit". Choices that hold for the whole module:

- "Today" is the date in India (IST), see domain.dates. Events that have happened (received, dispatched, transferred,
  appeal filed or decided) cannot be dated after it.
- Timelines are settings (RTI_RESPONSE_DAYS, RTI_APPEAL_WINDOW_DAYS, RTI_APPEAL_DECIDE_DAYS, RTI_DAY_COUNTING) read
  on every call. No statutory value is built in (PRD open question 1).
- The appeal window runs from the date the response was dispatched (Response.dispatched_on).
- Officers, custodians and the appellate authority are not notified yet: platform/notification has no SDK in
  packages/sdk. Every assignment, referral and reply is audited and names its person, so the notices can be added here.
- Every read of a request that returns applicant data (the detail and each row of a list) writes an audit entry.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import deadlines as dl
from ..domain import requests as rules
from ..domain.dates import today_in_india
from ..domain.errors import DomainRuleError
from ..infrastructure import repository as repo
from ..infrastructure.config import ModuleSettings, load_settings
from ..infrastructure.models import (
    Appeal,
    AuditEntry,
    Referral,
    Response,
    RtiRequest,
    Transfer,
    iso,
    money,
)
from .access import MODULE, REQUEST_READ, Actor
from .errors import RtiError, from_domain

REQUEST, REFERRAL = "request", "referral"  # audit entities


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


def today() -> date:
    """Today in India."""
    return today_in_india(clock())


# ---------------------------------------------------------------- helpers


def _not_found(what: str) -> RtiError:
    return RtiError(404, "not_found", f"{what} not found")


def _invalid(code: str, message: str, field: str | None = None) -> RtiError:
    return RtiError(422, code, message, field=field)


def _domain(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except DomainRuleError as err:
        raise from_domain(err) from err


def _audit(db: Session, actor: Actor, action: str, entity: str, entity_id: str) -> None:
    db.add(
        AuditEntry(
            organisation_id=actor.organisation_id,
            actor=actor.user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            occurred_at=clock(),
        )
    )


def _publish(db: Session, actor: Actor, name: str, payload: dict) -> None:
    events.publish(
        db,
        f"{MODULE}.request.{name}",
        actor.organisation_id,
        {"organisation_id": actor.organisation_id, **payload},
        actor=actor.user_id,
    )


def _request(db: Session, request_id: str, *, lock: bool = False) -> RtiRequest:
    row = repo.get(db, RtiRequest, request_id, lock=lock)
    if row is None:
        raise _not_found("request")
    return row


def _cursor(cursor: str | None) -> int:
    try:
        return repo.decode_cursor(cursor)
    except ValueError:
        raise _invalid("invalid_cursor", "cursor must be a value from a previous page", "cursor") from None


def _flush_unique(db: Session) -> None:
    """Flush; a concurrent request that took the same number first is a 409, not a 500."""
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise RtiError(409, "number_taken", "another request took that number; try again") from None


# ---------------------------------------------------------------- serialisation (contract schemas)


def _applicant(r: RtiRequest) -> dict:
    out: dict = {"name": r.applicant_name}
    for key, value in (("address", r.applicant_address), ("email", r.applicant_email), ("phone", r.applicant_phone)):
        if value is not None:
            out[key] = value
    out["person_id"] = r.applicant_person_id
    return out


def _fee(r: RtiRequest) -> dict:
    out: dict = {"status": r.fee_status}
    if r.fee_amount is not None:
        out["amount"] = {"amount": money(r.fee_amount), "currency": r.fee_currency}
    if r.fee_mode is not None:
        out["mode"] = r.fee_mode
    if r.fee_receipt_reference is not None:
        out["receipt_reference"] = r.fee_receipt_reference
    return out


def request_dict(r: RtiRequest, tl: dl.Timelines, on: date, appeal: Appeal | None = None) -> dict:
    """Contract Request. due_at is the response deadline from received_on; overdue is whether the deadline the request
    is waiting on has passed (the response for received and assigned, the appeal decision for appealed)."""
    response_due = dl.response_due_on(r.received_on, tl)
    current = dl.current_due_on(r.status, r.received_on, appeal.filed_on if appeal else None, tl)
    return {
        "id": r.id,
        "organisation_id": r.organisation_id,
        "number": r.number,
        "received_via": r.received_via,
        "received_on": iso(r.received_on),
        "applicant": _applicant(r),
        "subject": r.subject,
        "information_sought": r.information_sought,
        "fee": _fee(r),
        "officer_id": r.officer_id,
        "status": r.status,
        "closure": r.closure,
        "due_at": iso(dl.end_of_day(response_due)) if response_due else None,
        "overdue": dl.is_overdue(current, on),
        "created_by": r.created_by,
        "assigned_at": iso(r.assigned_at),
        "responded_at": iso(r.responded_at),
        "closed_at": iso(r.closed_at),
    }


def referral_dict(f: Referral) -> dict:
    """Contract Referral (officers and the appellate authority)."""
    return {
        "id": f.id,
        "request_id": f.request_id,
        "custodian_id": f.custodian_id,
        "question": f.question,
        "due_on": iso(f.due_on),
        "status": f.status,
        "reply": f.reply,
        "replied_at": iso(f.replied_at),
    }


def custodian_referral_dict(f: Referral, request_number: str) -> dict:
    """Contract CustodianReferral: the question and the request number, nothing of the applicant."""
    return {
        "id": f.id,
        "request_number": request_number,
        "question": f.question,
        "due_on": iso(f.due_on),
        "status": f.status,
        "reply": f.reply,
        "replied_at": iso(f.replied_at),
    }


def _response_dict(x: Response | None) -> dict | None:
    if x is None:
        return None
    out = {
        "type": x.type,
        "summary": x.summary,
        "dispatched_on": iso(x.dispatched_on),
        "dispatch_mode": x.dispatch_mode,
        "responded_by": x.responded_by,
    }
    if x.grounds is not None:
        out["grounds"] = x.grounds
    return out


def _transfer_dict(x: Transfer | None) -> dict | None:
    if x is None:
        return None
    out = {
        "authority_name": x.authority_name,
        "transferred_on": iso(x.transferred_on),
        "reason": x.reason,
        "transferred_by": x.transferred_by,
    }
    if x.authority_address is not None:
        out["authority_address"] = x.authority_address
    return out


def _appeal_dict(x: Appeal | None, tl: dl.Timelines) -> dict | None:
    if x is None:
        return None
    due = dl.appeal_due_on(x.filed_on, tl)
    return {
        "filed_on": iso(x.filed_on),
        "grounds": x.grounds,
        "outcome": x.outcome,
        "decision_note": x.decision_note,
        "decided_by": x.decided_by,
        "decided_on": iso(x.decided_on),
        "due_at": iso(dl.end_of_day(due)) if due else None,
    }


def detail_dict(db: Session, r: RtiRequest, tl: dl.Timelines, on: date) -> dict:
    """Contract RequestDetail: the request with its referrals, response, transfer and appeal."""
    appeal = repo.appeals_of(db, [r.id]).get(r.id)
    return {
        **request_dict(r, tl, on, appeal),
        "referrals": [referral_dict(f) for f in repo.referrals_of(db, r.id)],
        "response": _response_dict(repo.responses_of(db, [r.id]).get(r.id)),
        "transfer": _transfer_dict(repo.transfers_of(db, [r.id]).get(r.id)),
        "appeal": _appeal_dict(appeal, tl),
    }


# ---------------------------------------------------------------- requests


def _apply_applicant(r: RtiRequest, a: dict) -> None:
    """The applicant object replaces the stored one: what it leaves out is cleared."""
    r.applicant_name = a["name"]
    r.applicant_address = a.get("address")
    r.applicant_email = a.get("email")
    r.applicant_phone = a.get("phone")
    r.applicant_person_id = a.get("person_id")


def _apply_fee(r: RtiRequest, fee: dict, settings: ModuleSettings) -> None:
    """The fee object replaces the stored one. A fee amount without a currency is in RTI_DEFAULT_CURRENCY."""
    r.fee_status = fee["status"]
    amount = fee.get("amount")
    r.fee_amount = Decimal(amount["amount"]) if amount else None
    r.fee_currency = (amount.get("currency") or settings.default_currency) if amount else None
    r.fee_mode = fee.get("mode")
    r.fee_receipt_reference = fee.get("receipt_reference")


def list_requests(
    db: Session,
    actor: Actor,
    *,
    statuses: list[str] | None,
    officer: str | None,
    overdue: bool | None,
    received_via: str | None,
    q: str | None,
    cursor: str | None,
    limit: int,
) -> dict:
    """GET /requests, newest first. officer is a person id or `me`. Overdue depends on the settings and on how days are
    counted, so with the overdue filter the matching requests are filtered here and then paged; without it paging
    happens in the database."""
    offset = _cursor(cursor)
    tl, on = load_settings().timelines, today()
    officer_id = actor.user_id if officer == "me" else officer
    filters = {"statuses": statuses, "officer_id": officer_id, "received_via": received_via, "q": q}
    if overdue is None:
        rows = repo.requests(db, offset=offset, limit=limit, **filters)
        more = len(rows) > limit
        rows = rows[:limit]
        appeals = repo.appeals_of(db, [r.id for r in rows if r.status == rules.APPEALED])
        items = [request_dict(r, tl, on, appeals.get(r.id)) for r in rows]
    else:
        everything = repo.requests(db, **filters)
        appeals = repo.appeals_of(db, [r.id for r in everything if r.status == rules.APPEALED])
        wanted = [
            d for d in (request_dict(r, tl, on, appeals.get(r.id)) for r in everything) if d["overdue"] is overdue
        ]
        items, more = wanted[offset : offset + limit], len(wanted) > offset + limit
    for item in items:
        _audit(db, actor, "request.read", REQUEST, item["id"])
    db.commit()
    return {"items": items, "next_cursor": repo.encode_cursor(offset + limit) if more else None}


def get_request(db: Session, actor: Actor, request_id: str) -> dict:
    """GET /requests/{id}. The read is audited."""
    tl, on = load_settings().timelines, today()
    r = _request(db, request_id)
    _audit(db, actor, "request.read", REQUEST, r.id)
    out = detail_dict(db, r, tl, on)
    db.commit()
    return out


def create_request(db: Session, actor: Actor, data: dict) -> dict:
    """POST /requests: status received, numbered per organisation (prefix RTI_REQUEST_NUMBER_PREFIX), event
    rti.request.received."""
    settings = load_settings()
    on = today()
    _domain(rules.check_not_future, data["received_on"], on, "received_on")
    seq = repo.next_seq(db, actor.organisation_id)
    r = RtiRequest(
        organisation_id=actor.organisation_id,
        seq=seq,
        number=f"{settings.number_prefix}-{seq:06d}",
        received_via=data["received_via"],
        received_on=data["received_on"],
        subject=data["subject"],
        information_sought=data["information_sought"],
        status=rules.RECEIVED,
        created_by=actor.user_id,
    )
    _apply_applicant(r, data["applicant"])
    _apply_fee(r, data["fee"], settings)
    db.add(r)
    _flush_unique(db)
    _audit(db, actor, "request.recorded", REQUEST, r.id)
    _publish(
        db,
        actor,
        "received",
        {
            "request_id": r.id,
            "number": r.number,
            "received_via": r.received_via,
            "received_on": iso(r.received_on),
        },
    )
    db.commit()
    return request_dict(r, settings.timelines, on)


def update_request(db: Session, actor: Actor, request_id: str, data: dict) -> dict:
    """PATCH /requests/{id}: correct applicant, subject, information sought or fee while received or assigned. An
    applicant or fee object replaces the stored one. A body that changes nothing is 422."""
    settings = load_settings()
    on = today()
    r = _request(db, request_id, lock=True)
    _domain(rules.move, "correct", r.status)
    if not data:
        raise _invalid("nothing_to_change", "give at least one of applicant, subject, information_sought or fee")
    if "applicant" in data:
        _apply_applicant(r, data["applicant"])
    if "fee" in data:
        _apply_fee(r, data["fee"], settings)
    for key in ("subject", "information_sought"):
        if key in data:
            setattr(r, key, data[key])
    _audit(db, actor, "request.corrected", REQUEST, r.id)
    db.commit()
    return request_dict(r, settings.timelines, on)


def assign_request(db: Session, actor: Actor, request_id: str, officer_id: str) -> dict:
    """POST /requests/{id}/assign: received or assigned -> assigned; may be repeated to re-assign."""
    settings = load_settings()
    on = today()
    r = _request(db, request_id, lock=True)
    r.status = _domain(rules.move, "assign", r.status)
    r.officer_id = officer_id
    r.assigned_at = clock()
    _audit(db, actor, "request.assigned", REQUEST, r.id)
    db.commit()
    return request_dict(r, settings.timelines, on)


# ---------------------------------------------------------------- referrals


def create_referral(db: Session, actor: Actor, request_id: str, data: dict) -> dict:
    """POST /requests/{id}/referrals: ask a custodian while the request is assigned. The question must not repeat the
    applicant's name, email or phone. The request's status does not change."""
    r = _request(db, request_id, lock=True)
    _domain(rules.move, "refer", r.status)
    if "due_on" in data:
        _domain(rules.check_date, data["due_on"], "due_on")
    repeated = rules.question_repeats_applicant(data["question"], _applicant(r))
    if repeated:
        raise _invalid("applicant_details_in_question", f"the question repeats the applicant's {repeated}", "question")
    f = Referral(
        organisation_id=actor.organisation_id,
        request_id=r.id,
        custodian_id=data["custodian_id"],
        question=data["question"],
        due_on=data.get("due_on"),
        status="open",
        created_by=actor.user_id,
    )
    db.add(f)
    db.flush()
    _audit(db, actor, "referral.created", REFERRAL, f.id)
    db.commit()
    return referral_dict(f)


def list_referrals(
    db: Session, actor: Actor, *, request_id: str | None, status: str | None, cursor: str | None, limit: int
) -> dict:
    """GET /referrals. With rti:request:read (officers, the appellate authority): any referral, as Referral. With only
    rti:referral:respond (custodians): the caller's own, as CustodianReferral. A caller with both gets the first."""
    offset = _cursor(cursor)
    full = actor.can(REQUEST_READ)
    rows, more = repo.referrals_page(
        db,
        request_id=request_id,
        custodian_id=None if full else actor.user_id,
        status=status,
        offset=offset,
        limit=limit,
    )
    if full:
        items = [referral_dict(f) for f in rows]
    else:
        numbers = repo.numbers_of(db, {f.request_id for f in rows})
        items = [custodian_referral_dict(f, numbers[f.request_id]) for f in rows]
    return {"items": items, "next_cursor": repo.encode_cursor(offset + limit) if more else None}


def reply_referral(db: Session, actor: Actor, referral_id: str, reply: str) -> dict:
    """POST /referrals/{id}/reply: the custodian answers their own open referral. Someone else's referral is
    "not found"."""
    f = repo.get(db, Referral, referral_id, lock=True)
    if f is None or f.custodian_id != actor.user_id:
        raise _not_found("referral")
    if f.status != "open":
        raise RtiError(409, "already_replied", "this referral was already answered")
    f.status, f.reply, f.replied_at = "replied", reply, clock()
    _audit(db, actor, "referral.replied", REFERRAL, f.id)
    db.commit()
    return custodian_referral_dict(f, repo.numbers_of(db, {f.request_id})[f.request_id])


# ---------------------------------------------------------------- response, transfer, close


def respond(db: Session, actor: Actor, request_id: str, data: dict) -> dict:
    """POST /requests/{id}/respond: assigned -> responded. Grounds are required for partly_provided and refused. The
    response cannot be dispatched before the request was received or after today."""
    tl, on = load_settings().timelines, today()
    r = _request(db, request_id, lock=True)
    new_status = _domain(rules.move, "respond", r.status)
    _domain(rules.check_response, data["type"], data.get("grounds"))
    _domain(rules.check_not_future, data["dispatched_on"], on, "dispatched_on")
    _domain(rules.check_not_before, data["dispatched_on"], r.received_on, "dispatched_on", "the date received")
    db.add(
        Response(
            organisation_id=actor.organisation_id,
            request_id=r.id,
            type=data["type"],
            summary=data["summary"],
            grounds=data.get("grounds"),
            dispatched_on=data["dispatched_on"],
            dispatch_mode=data["dispatch_mode"],
            responded_by=actor.user_id,
        )
    )
    r.status, r.responded_at = new_status, clock()
    _audit(db, actor, "request.responded", REQUEST, r.id)
    db.flush()
    out = detail_dict(db, r, tl, on)
    db.commit()
    return out


def _close(
    db: Session, actor: Actor, r: RtiRequest, closure: str, response_type: str | None, *, appealed: bool
) -> None:
    """Make the request final and publish rti.request.closed in the same transaction."""
    r.closure, r.closed_at = closure, clock()
    _publish(
        db,
        actor,
        "closed",
        {
            "request_id": r.id,
            "number": r.number,
            "closure": closure,
            "response_type": response_type,
            "appealed": appealed,
            "closed_at": iso(r.closed_at),
        },
    )


def transfer(db: Session, actor: Actor, request_id: str, data: dict) -> dict:
    """POST /requests/{id}/transfer: received or assigned -> transferred (final), event rti.request.closed with
    closure transferred and no response type."""
    tl, on = load_settings().timelines, today()
    r = _request(db, request_id, lock=True)
    r.status = _domain(rules.move, "transfer", r.status)
    _domain(rules.check_not_future, data["transferred_on"], on, "transferred_on")
    _domain(rules.check_not_before, data["transferred_on"], r.received_on, "transferred_on", "the date received")
    db.add(
        Transfer(
            organisation_id=actor.organisation_id,
            request_id=r.id,
            authority_name=data["authority_name"],
            authority_address=data.get("authority_address"),
            transferred_on=data["transferred_on"],
            reason=data["reason"],
            transferred_by=actor.user_id,
        )
    )
    _audit(db, actor, "request.transferred", REQUEST, r.id)
    _close(db, actor, r, "transferred", None, appealed=False)
    db.flush()
    out = detail_dict(db, r, tl, on)
    db.commit()
    return out


def close_request(db: Session, actor: Actor, request_id: str) -> dict:
    """POST /requests/{id}/close: an appeal-decided request, or a responded one once the appeal window is configured
    and over (the day after the last day of the window; with no window configured it stays responded)."""
    tl, on = load_settings().timelines, today()
    r = _request(db, request_id, lock=True)
    before = r.status
    r.status = _domain(rules.move, "close", before)
    response = repo.responses_of(db, [r.id]).get(r.id)
    if before == rules.RESPONDED:
        if tl.appeal_window_days is None:
            raise RtiError(409, "appeal_window_not_configured", "Appeal window is not configured")
        last_day = dl.appeal_window_end(response.dispatched_on, tl)
        if on <= last_day:
            raise RtiError(409, "appeal_window_open", f"the appeal window is open until {last_day}")
    _audit(db, actor, "request.closed", REQUEST, r.id)
    closure = rules.closure_of(before)
    _close(db, actor, r, closure, response.type if response else None, appealed=before == rules.APPEAL_DECIDED)
    db.commit()
    return request_dict(r, tl, on)


# ---------------------------------------------------------------- appeals


def appeal(db: Session, actor: Actor, request_id: str, data: dict) -> dict:
    """POST /requests/{id}/appeal: responded -> appealed, if filed within RTI_APPEAL_WINDOW_DAYS of the response.
    While that setting is empty no appeal is accepted (409 "Appeal window is not configured"); this is checked first,
    whatever the request's status."""
    tl, on = load_settings().timelines, today()
    r = _request(db, request_id, lock=True)
    if tl.appeal_window_days is None:
        raise RtiError(409, "appeal_window_not_configured", "Appeal window is not configured")
    new_status = _domain(rules.move, "appeal", r.status)
    response = repo.responses_of(db, [r.id])[r.id]
    filed_on = data["filed_on"]
    _domain(rules.check_not_future, filed_on, on, "filed_on")
    _domain(rules.check_not_before, filed_on, response.dispatched_on, "filed_on", "the response was dispatched")
    last_day = dl.appeal_window_end(response.dispatched_on, tl)
    if filed_on > last_day:
        raise RtiError(409, "appeal_window_passed", f"the appeal window ended on {last_day}", field="filed_on")
    db.add(
        Appeal(
            organisation_id=actor.organisation_id,
            request_id=r.id,
            filed_on=filed_on,
            grounds=data["grounds"],
            filed_by=actor.user_id,
        )
    )
    r.status = new_status
    _audit(db, actor, "appeal.filed", REQUEST, r.id)
    db.flush()
    out = detail_dict(db, r, tl, on)
    db.commit()
    return out


def decide_appeal(db: Session, actor: Actor, request_id: str, data: dict) -> dict:
    """POST /requests/{id}/appeal-decision: appealed -> appeal_decided. Decided on or after the day it was filed, and
    not after today."""
    tl, on = load_settings().timelines, today()
    r = _request(db, request_id, lock=True)
    r.status = _domain(rules.move, "decide", r.status)
    a = repo.appeals_of(db, [r.id])[r.id]
    _domain(rules.check_not_future, data["decided_on"], on, "decided_on")
    _domain(rules.check_not_before, data["decided_on"], a.filed_on, "decided_on", "the day the appeal was filed")
    a.outcome, a.decision_note, a.decided_on, a.decided_by = (
        data["outcome"],
        data["decision_note"],
        data["decided_on"],
        actor.user_id,
    )
    _audit(db, actor, "appeal.decided", REQUEST, r.id)
    db.flush()
    out = detail_dict(db, r, tl, on)
    db.commit()
    return out


# ---------------------------------------------------------------- widget


def nearing_deadline(db: Session, actor: Actor) -> dict:
    """GET /stats/nearing-deadline: open requests (received, assigned, appealed) that are overdue or due within
    RTI_NEARING_DEADLINE_DAYS, the response deadline for the first two and the appeal decision deadline for an
    appealed one. Request numbers, statuses and due dates only."""
    settings = load_settings()
    tl, on = settings.timelines, today()
    rows = repo.open_requests(db)
    appeals = repo.appeals_of(db, [r.id for r in rows if r.status == rules.APPEALED])
    items = [
        dl.OpenItem(
            r.id,
            r.number,
            r.status,
            r.seq,
            dl.current_due_on(r.status, r.received_on, appeals[r.id].filed_on if r.id in appeals else None, tl),
        )
        for r in rows
    ]
    result = dl.nearing_deadline(items, settings.nearing_days, on)
    return {
        "within_days": result.within_days,
        "due_soon": result.due_soon,
        "overdue": result.overdue,
        "items": [
            {
                "request_id": i.request_id,
                "number": i.number,
                "status": i.status,
                "due_at": iso(i.due_at),
                "overdue": i.overdue,
            }
            for i in result.items
        ],
    }
