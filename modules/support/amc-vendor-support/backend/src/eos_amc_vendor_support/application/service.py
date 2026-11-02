"""Use cases of amc-vendor-support (docs/prd.md, contracts/openapi.yaml). Each one checks the caller's permission and
the domain rules, changes state, writes an audit entry, and publishes the matching event from contracts/events.yaml to
the outbox in the same transaction. Event payloads carry ids, numbers, dates and status only; scope text, vendor
contacts and engagement notes are never published.

Where the contract leaves a detail open, the choice made here is noted at the function."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import contracts as rules
from ..domain import engagements as eng
from ..domain.errors import DomainRuleError
from ..domain.expiring import ContractForExpiry, contracts_expiring
from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from ..infrastructure.models import AuditEntry, Contract, CoveredItem, Engagement
from .access import CONTRACT_MANAGE, CONTRACT_READ, ENGAGEMENT_MANAGE, MODULE, Actor, require
from .errors import AmcVendorSupportError, from_domain

CONTRACT, ENGAGEMENT = "contract", "engagement"  # number sequence kinds and audit entities
COVERED_ITEM = "covered_item"

# Fields a contract copies to its renewal (contract /renew: "copied from this active contract (terms and covered
# items) for the next period").
RENEWAL_COPIED_FIELDS = (
    "vendor_id",
    "title",
    "coverage_type",
    "scope",
    "value_amount",
    "value_currency",
    "response_hours",
    "resolution_hours",
    "preventive_visits_per_year",
    "vendor_contacts",
    "owner_id",
    "renewal_notice_days",
)


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


def _not_found(what: str) -> AmcVendorSupportError:
    return AmcVendorSupportError(404, "not_found", f"{what} not found")


def _conflict(code: str, message: str, field: str | None = None) -> AmcVendorSupportError:
    return AmcVendorSupportError(409, code, message, field=field)


def _invalid(code: str, message: str, field: str | None = None) -> AmcVendorSupportError:
    return AmcVendorSupportError(422, code, message, field=field)


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
        f"{MODULE}.contract.{name}",
        actor.organisation_id,
        {"organisation_id": actor.organisation_id, **payload},
        actor=actor.user_id,
    )


def _number(db: Session, actor: Actor, kind: str) -> str:
    settings = load_settings()
    prefix = settings.contract_number_prefix if kind == CONTRACT else settings.engagement_number_prefix
    # Format from the PRD's examples AMC-000012 and AVS-000034: the prefix, a hyphen and six digits.
    return f"{prefix}-{repo.next_number(db, actor.organisation_id, kind):06d}"


def _contract(db: Session, contract_id: str) -> Contract:
    contract = repo.get(db, Contract, contract_id)
    if contract is None:
        raise _not_found("contract")
    return contract


def _engagement(db: Session, engagement_id: str) -> Engagement:
    engagement = repo.get(db, Engagement, engagement_id)
    if engagement is None:
        raise _not_found("engagement")
    return engagement


def _commit(db: Session) -> None:
    db.commit()


# ---------------------------------------------------------------- serialisation (contract schemas)


def _money(amount: Decimal | None, currency: str | None) -> dict | None:
    if amount is None:
        return None
    return {"amount": f"{Decimal(amount):.2f}", "currency": currency}


def _set_money(contract: Contract, value: dict | None) -> None:
    """Money.currency defaults to AMC_VENDOR_SUPPORT_DEFAULT_CURRENCY when the caller gives none."""
    if value is None:
        contract.value_amount, contract.value_currency = None, None
        return
    contract.value_amount = Decimal(value["amount"])
    contract.value_currency = value.get("currency") or load_settings().default_currency


def _reference(item: CoveredItem) -> dict | None:
    if item.ref_module is None:
        return None
    return {"module": item.ref_module, "entity": item.ref_entity, "id": item.ref_id}


def contract_dict(contract: Contract, on: date | None = None) -> dict:
    on = on or today()
    return {
        "id": contract.id,
        "organisation_id": contract.organisation_id,
        "number": contract.number,
        "vendor_id": contract.vendor_id,
        "title": contract.title,
        "coverage_type": contract.coverage_type,
        "scope": contract.scope,
        "start_date": contract.start_date.isoformat(),
        "end_date": contract.end_date.isoformat(),
        "value": _money(contract.value_amount, contract.value_currency),
        "purchase_order_reference": contract.purchase_order_reference,
        "response_hours": contract.response_hours,
        "resolution_hours": contract.resolution_hours,
        "preventive_visits_per_year": contract.preventive_visits_per_year,
        "vendor_contacts": list(contract.vendor_contacts or []),
        "owner_id": contract.owner_id,
        "renewal_notice_days": contract.renewal_notice_days,
        "status": contract.status,
        "expiring": rules.is_expiring(contract.status, contract.end_date, contract.renewal_notice_days, on),
        "expired": rules.is_expired(contract.status, contract.end_date, on),
        "renewed_from_id": contract.renewed_from_id,
        "renewed_to_id": contract.renewed_to_id,
        "activated_at": iso(contract.activated_at),
        "terminated_at": iso(contract.terminated_at),
        "termination_effective_date": (
            contract.termination_effective_date.isoformat() if contract.termination_effective_date else None
        ),
        "termination_reason": contract.termination_reason,
        "created_at": iso(contract.created_at),
    }


def item_dict(item: CoveredItem) -> dict:
    body = {"id": item.id, "contract_id": item.contract_id, "description": item.description}
    reference = _reference(item)
    if reference is not None:
        body["reference"] = reference
    return body


def _within_terms(engagement: Engagement, contract: Contract | None) -> bool | None:
    if contract is None:
        return None
    return eng.within_terms(
        response_hours=contract.response_hours,
        resolution_hours=contract.resolution_hours,
        reported_at=as_utc(engagement.reported_at),
        vendor_responded_at=as_utc(engagement.vendor_responded_at),
        resolved_at=as_utc(engagement.resolved_at),
    )


def engagement_dict(engagement: Engagement, contract: Contract | None) -> dict:
    return {
        "id": engagement.id,
        "organisation_id": engagement.organisation_id,
        "number": engagement.number,
        "contract_id": engagement.contract_id,
        "kind": engagement.kind,
        "description": engagement.description,
        "covered_item_id": engagement.covered_item_id,
        "references": list(engagement.references or []),
        "vendor_call_reference": engagement.vendor_call_reference,
        "status": engagement.status,
        "reported_at": iso(engagement.reported_at),
        "vendor_responded_at": iso(engagement.vendor_responded_at),
        "resolved_at": iso(engagement.resolved_at),
        "closed_at": iso(engagement.closed_at),
        "resolution_note": engagement.resolution_note,
        "raised_by": engagement.raised_by,
        "within_terms": _within_terms(engagement, contract),
    }


# ---------------------------------------------------------------- contracts


def list_contracts(
    db: Session,
    actor: Actor,
    *,
    statuses: list[str] | None,
    vendor_id: str | None,
    owner: str | None,
    expiring: bool | None,
    expired: bool | None,
    q: str | None,
    cursor: str | None,
    limit: int,
) -> dict:
    """GET /contracts, soonest end date first. owner=me means the caller. expiring and expired are worked out when
    read, so those two filters run here rather than in the database."""
    require(actor, CONTRACT_READ)
    owner_id = actor.user_id if owner == "me" else owner
    on = today()
    rows = repo.contracts(db, statuses=statuses, vendor_id=vendor_id, owner_id=owner_id, q=q)
    if expiring is not None:
        rows = [c for c in rows if rules.is_expiring(c.status, c.end_date, c.renewal_notice_days, on) is expiring]
    if expired is not None:
        rows = [c for c in rows if rules.is_expired(c.status, c.end_date, on) is expired]
    items, next_cursor = repo.page_of(rows, cursor, limit)
    return {"items": [contract_dict(c, on) for c in items], "next_cursor": next_cursor}


def create_contract(db: Session, actor: Actor, body: dict) -> dict:
    """POST /contracts: a draft with the next AMC number. owner_id defaults to the caller."""
    require(actor, CONTRACT_MANAGE)
    _domain(rules.check_period, body["start_date"], body["end_date"])
    contract = Contract(
        organisation_id=actor.organisation_id,
        number=_number(db, actor, CONTRACT),
        vendor_id=body["vendor_id"],
        title=body["title"],
        coverage_type=body["coverage_type"],
        scope=body.get("scope"),
        start_date=body["start_date"],
        end_date=body["end_date"],
        purchase_order_reference=body.get("purchase_order_reference"),
        response_hours=body.get("response_hours"),
        resolution_hours=body.get("resolution_hours"),
        preventive_visits_per_year=body.get("preventive_visits_per_year"),
        vendor_contacts=list(body.get("vendor_contacts") or []),
        owner_id=body.get("owner_id") or actor.user_id,
        renewal_notice_days=body.get("renewal_notice_days", 60),
        status=rules.DRAFT,
    )
    _set_money(contract, body.get("value"))
    db.add(contract)
    db.flush()
    _audit(db, actor, "contract.created", CONTRACT, contract.id)
    _commit(db)
    return contract_dict(contract)


def get_contract(db: Session, actor: Actor, contract_id: str) -> dict:
    """GET /contracts/{id}: with covered items and engagement counts. open counts open and in_progress engagements,
    resolved counts resolved and closed ones, outside_terms those whose within_terms is false."""
    require(actor, CONTRACT_READ)
    contract = _contract(db, contract_id)
    engagements = repo.engagements(db, contract_id=contract.id)
    counts = {
        "open": sum(1 for e in engagements if e.status in (eng.OPEN, eng.IN_PROGRESS)),
        "resolved": sum(1 for e in engagements if e.status in (eng.RESOLVED, eng.CLOSED)),
        "outside_terms": sum(1 for e in engagements if _within_terms(e, contract) is False),
    }
    return {
        **contract_dict(contract),
        "covered_items": [item_dict(i) for i in repo.covered_items(db, contract.id)],
        "engagement_counts": counts,
    }


def update_contract(db: Session, actor: Actor, contract_id: str, body: dict) -> dict:
    """PATCH /contracts/{id}: only the fields sent change. A draft can change any field; an active contract only
    owner_id, vendor_contacts and renewal_notice_days (409 otherwise); a terminated or renewed one nothing."""
    require(actor, CONTRACT_MANAGE)
    contract = _contract(db, contract_id)
    _domain(rules.check_editable, contract.status, set(body))
    start = body.get("start_date", contract.start_date)
    end = body.get("end_date", contract.end_date)
    if "start_date" in body or "end_date" in body:
        _domain(rules.check_period, start, end)
    for name, value in body.items():
        if name == "value":
            _set_money(contract, value)
        elif name == "vendor_contacts":
            contract.vendor_contacts = list(value or [])
        else:
            setattr(contract, name, value)
    _audit(db, actor, "contract.updated", CONTRACT, contract.id)
    _commit(db)
    return contract_dict(contract)


def activate_contract(db: Session, actor: Actor, contract_id: str) -> dict:
    """POST /contracts/{id}/activate: draft -> active, publishing contract.activated. When the draft renews another
    contract, that contract becomes renewed and contract.renewed is published too (409 when it is no longer active)."""
    require(actor, CONTRACT_MANAGE)
    contract = _contract(db, contract_id)
    new_status = _domain(rules.activate, contract.status)
    predecessor = None
    if contract.renewed_from_id:
        predecessor = repo.get(db, Contract, contract.renewed_from_id)
        _domain(rules.check_predecessor_active, predecessor.status if predecessor else rules.TERMINATED)
    now = clock()
    contract.status, contract.activated_at = new_status, now
    _audit(db, actor, "contract.activated", CONTRACT, contract.id)
    covered = [r for r in (_reference(i) for i in repo.covered_items(db, contract.id)) if r is not None]
    _publish(
        db,
        actor,
        "activated",
        {
            "contract_id": contract.id,
            "number": contract.number,
            "vendor_id": contract.vendor_id,
            "coverage_type": contract.coverage_type,
            "start_date": contract.start_date.isoformat(),
            "end_date": contract.end_date.isoformat(),
            "renewed_from_id": contract.renewed_from_id,
            "covered_references": covered,
        },
    )
    if predecessor is not None:
        predecessor.status = rules.RENEWED
        _audit(db, actor, "contract.renewed", CONTRACT, predecessor.id)
        _publish(
            db,
            actor,
            "renewed",
            {
                "contract_id": predecessor.id,
                "number": predecessor.number,
                "successor_id": contract.id,
                "successor_number": contract.number,
                "vendor_id": predecessor.vendor_id,
                "renewed_at": iso(now),
            },
        )
    _commit(db)
    return contract_dict(contract)


def terminate_contract(db: Session, actor: Actor, contract_id: str, body: dict) -> dict:
    """POST /contracts/{id}/terminate: active -> terminated with a reason and an effective date. Open engagements stay
    open (PRD main flow 9). The contract does not limit effective_date, so any date is accepted."""
    require(actor, CONTRACT_MANAGE)
    contract = _contract(db, contract_id)
    contract.status = _domain(rules.terminate, contract.status)
    now = clock()
    contract.terminated_at = now
    contract.termination_effective_date = body["effective_date"]
    contract.termination_reason = body["reason"]
    _audit(db, actor, "contract.terminated", CONTRACT, contract.id, body["reason"])
    _publish(
        db,
        actor,
        "terminated",
        {
            "contract_id": contract.id,
            "number": contract.number,
            "vendor_id": contract.vendor_id,
            "effective_date": body["effective_date"].isoformat(),
            "terminated_at": iso(now),
        },
    )
    _commit(db)
    return contract_dict(contract)


def renew_contract(db: Session, actor: Actor, contract_id: str, body: dict) -> dict:
    """POST /contracts/{id}/renew: a draft successor with the terms and covered items of this active contract and the
    next period. start_date defaults to the day after the current end_date. value is copied unless one is sent; the
    purchase order reference is not copied, since a new period normally has its own order, and is set only when sent.
    No event yet: contract.activated and contract.renewed follow when the successor is activated."""
    require(actor, CONTRACT_MANAGE)
    original = _contract(db, contract_id)
    _domain(rules.check_renewable, original.status, original.renewed_to_id)
    # A contract ending on date.max has no next day; check_period then refuses the renewal (422) instead of overflowing.
    start = body.get("start_date") or min(original.end_date, date.max - timedelta(days=1)) + timedelta(days=1)
    _domain(rules.check_period, start, body["end_date"])
    successor = Contract(
        organisation_id=actor.organisation_id,
        number=_number(db, actor, CONTRACT),
        start_date=start,
        end_date=body["end_date"],
        purchase_order_reference=body.get("purchase_order_reference"),
        status=rules.DRAFT,
        renewed_from_id=original.id,
        **{name: getattr(original, name) for name in RENEWAL_COPIED_FIELDS},
    )
    successor.vendor_contacts = list(original.vendor_contacts or [])
    if body.get("value") is not None:
        _set_money(successor, body["value"])
    db.add(successor)
    db.flush()
    for item in repo.covered_items(db, original.id):
        db.add(
            CoveredItem(
                organisation_id=actor.organisation_id,
                contract_id=successor.id,
                description=item.description,
                ref_module=item.ref_module,
                ref_entity=item.ref_entity,
                ref_id=item.ref_id,
            )
        )
    original.renewed_to_id = successor.id
    _audit(db, actor, "contract.renewal_started", CONTRACT, original.id)
    _audit(db, actor, "contract.created", CONTRACT, successor.id)
    _commit(db)
    return contract_dict(successor)


def add_covered_item(db: Session, actor: Actor, contract_id: str, body: dict) -> dict:
    """POST /contracts/{id}/covered-items: while the contract is a draft or active; 409 when the same reference is
    already covered by this contract."""
    require(actor, CONTRACT_MANAGE)
    contract = _contract(db, contract_id)
    _domain(rules.check_items_changeable, contract.status)
    reference = body.get("reference")
    if reference and repo.covered_item_with_reference(
        db, contract.id, reference["module"], reference["entity"], reference["id"]
    ):
        raise _conflict("already_covered", "this contract already covers that record", field="reference")
    item = CoveredItem(
        organisation_id=actor.organisation_id,
        contract_id=contract.id,
        description=body["description"],
        ref_module=reference["module"] if reference else None,
        ref_entity=reference["entity"] if reference else None,
        ref_id=reference["id"] if reference else None,
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError:  # the same reference added at the same moment
        db.rollback()
        raise _conflict("already_covered", "this contract already covers that record", field="reference") from None
    _audit(db, actor, "covered_item.added", COVERED_ITEM, item.id)
    _commit(db)
    return item_dict(item)


def remove_covered_item(db: Session, actor: Actor, contract_id: str, item_id: str) -> None:
    """DELETE /contracts/{id}/covered-items/{item_id}: "Remove a covered item added by mistake. Audited." The only
    deletion in the module. Engagements that named the item keep its id."""
    require(actor, CONTRACT_MANAGE)
    contract = _contract(db, contract_id)
    item = repo.get(db, CoveredItem, item_id)
    if item is None or item.contract_id != contract.id:
        raise _not_found("covered item")
    _domain(rules.check_items_changeable, contract.status)
    db.delete(item)
    _audit(db, actor, "covered_item.removed", COVERED_ITEM, item_id)
    _commit(db)


def coverage(db: Session, actor: Actor, module: str, entity: str, ref_id: str, include_expired: bool) -> list[dict]:
    """GET /coverage: active contracts whose covered items reference the record, soonest end date first. Expired ones
    only with include_expired."""
    require(actor, CONTRACT_READ)
    on = today()
    found = repo.contracts_by_id(db, repo.contract_ids_covering(db, module, entity, ref_id)).values()
    rows = [
        c
        for c in found
        if c.status == rules.ACTIVE and (include_expired or not rules.is_expired(c.status, c.end_date, on))
    ]
    rows.sort(key=lambda c: (c.end_date, c.number))
    return [contract_dict(c, on) for c in rows]


def contracts_expiring_stats(db: Session, actor: Actor, within_days: int | None) -> dict:
    """GET /stats/contracts-expiring, behind the widget amc-vendor-support.contracts-expiring. within_days defaults to
    AMC_VENDOR_SUPPORT_EXPIRY_WINDOW_DAYS."""
    require(actor, CONTRACT_READ)
    window = within_days or load_settings().expiry_window_days
    active = repo.active_contracts(db)
    successors = repo.contracts_by_id(db, {c.renewed_to_id for c in active if c.renewed_to_id})
    result = contracts_expiring(
        [
            ContractForExpiry(
                contract_id=c.id,
                number=c.number,
                vendor_id=c.vendor_id,
                title=c.title,
                status=c.status,
                end_date=c.end_date,
                successor_status=successors[c.renewed_to_id].status if c.renewed_to_id in successors else None,
            )
            for c in active
        ],
        window,
        today(),
    )
    return {
        "within_days": result.within_days,
        "expiring_count": result.expiring_count,
        "expired_count": result.expired_count,
        "items": [
            {
                "contract_id": i.contract_id,
                "number": i.number,
                "vendor_id": i.vendor_id,
                "title": i.title,
                "end_date": i.end_date.isoformat(),
                "days_left": i.days_left,
                "renewal_draft_exists": i.renewal_draft_exists,
            }
            for i in result.items
        ],
    }


# ---------------------------------------------------------------- engagements


def _check_covered_item(db: Session, contract: Contract, covered_item_id: str | None) -> None:
    """422 "covered_item_id does not belong to the contract"."""
    if covered_item_id is None:
        return
    item = repo.get(db, CoveredItem, covered_item_id)
    if item is None or item.contract_id != contract.id:
        raise _invalid("covered_item_not_in_contract", "the covered item is not on this contract", "covered_item_id")


def list_engagements(
    db: Session,
    actor: Actor,
    *,
    contract_id: str | None,
    statuses: list[str] | None,
    kind: str | None,
    within_terms: bool | None,
    cursor: str | None,
    limit: int,
) -> dict:
    """GET /engagements, newest first. within_terms is worked out when read, so that filter runs here: false returns
    the engagements outside the contract's hours, true those within them; not yet measurable ones match neither."""
    require(actor, CONTRACT_READ)
    rows = repo.engagements(db, contract_id=contract_id, statuses=statuses, kind=kind)
    by_id = repo.contracts_by_id(db, {e.contract_id for e in rows})
    if within_terms is not None:
        rows = [e for e in rows if _within_terms(e, by_id.get(e.contract_id)) is within_terms]
    items, next_cursor = repo.page_of(rows, cursor, limit)
    return {"items": [engagement_dict(e, by_id.get(e.contract_id)) for e in items], "next_cursor": next_cursor}


def raise_engagement(db: Session, actor: Actor, body: dict) -> dict:
    """POST /engagements: against an active contract that has not expired (409), with a covered item of that contract
    (422). An unknown contract_id is a 422, like any request value that names nothing; the contract lists no 404 here.
    reported_at defaults to now."""
    require(actor, ENGAGEMENT_MANAGE)
    contract = repo.get(db, Contract, body["contract_id"])
    if contract is None:
        raise _invalid("unknown_contract", "contract not found", "contract_id")
    _domain(rules.check_can_raise_engagement, contract.status, contract.end_date, today())
    _check_covered_item(db, contract, body.get("covered_item_id"))
    engagement = Engagement(
        organisation_id=actor.organisation_id,
        number=_number(db, actor, ENGAGEMENT),
        contract_id=contract.id,
        kind=body["kind"],
        description=body["description"],
        covered_item_id=body.get("covered_item_id"),
        references=list(body.get("references") or []),
        vendor_call_reference=body.get("vendor_call_reference"),
        status=eng.OPEN,
        reported_at=body.get("reported_at") or clock(),
        raised_by=actor.user_id,
    )
    db.add(engagement)
    db.flush()
    _audit(db, actor, "engagement.raised", ENGAGEMENT, engagement.id)
    _commit(db)
    return engagement_dict(engagement, contract)


def get_engagement(db: Session, actor: Actor, engagement_id: str) -> dict:
    require(actor, CONTRACT_READ)
    engagement = _engagement(db, engagement_id)
    return engagement_dict(engagement, repo.get(db, Contract, engagement.contract_id))


def update_engagement(db: Session, actor: Actor, engagement_id: str, body: dict) -> dict:
    """PATCH /engagements/{id}: only the fields sent change; 409 when closed or cancelled. covered_item_id may be set
    to null."""
    require(actor, ENGAGEMENT_MANAGE)
    engagement = _engagement(db, engagement_id)
    _domain(eng.check_editable, engagement.status)
    contract = repo.get(db, Contract, engagement.contract_id)
    if "covered_item_id" in body:
        _check_covered_item(db, contract, body["covered_item_id"])
    for name, value in body.items():
        setattr(engagement, name, list(value or []) if name == "references" else value)
    _audit(db, actor, "engagement.updated", ENGAGEMENT, engagement.id)
    _commit(db)
    return engagement_dict(engagement, contract)


def move_engagement(db: Session, actor: Actor, engagement_id: str, body: dict) -> dict:
    """POST /engagements/{id}/status: open -> in_progress records vendor_responded_at, in_progress -> resolved records
    resolved_at and the resolution_note, resolved -> closed records closed_at, open or in_progress -> cancelled keeps
    the note as the audit reason. `at` (default now) is when the vendor responded or resolved."""
    require(actor, ENGAGEMENT_MANAGE)
    engagement = _engagement(db, engagement_id)
    target = body["status"]
    engagement.status = _domain(
        eng.move, engagement.status, target, resolution_note=body.get("resolution_note"), note=body.get("note")
    )
    at = body.get("at") or clock()
    reason = None
    if target == eng.IN_PROGRESS:
        engagement.vendor_responded_at = at
    elif target == eng.RESOLVED:
        engagement.resolved_at, engagement.resolution_note = at, body["resolution_note"]
    elif target == eng.CLOSED:
        engagement.closed_at = clock()
    else:
        reason = body["note"]
    _audit(db, actor, f"engagement.{target}", ENGAGEMENT, engagement.id, reason)
    _commit(db)
    return engagement_dict(engagement, repo.get(db, Contract, engagement.contract_id))
