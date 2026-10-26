"""Use cases of asset-management (docs/prd.md). Each one checks permissions and rules, changes state, and publishes
the matching event from contracts/events.yaml to the outbox in the same transaction. Until the audit SDK exists,
the outbox is the audit trail (PRD rule 9)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.rules import (
    IN_DISPOSAL,
    ZERO,
    Depreciation,
    RuleViolationError,
    check_cancel,
    check_close,
    check_complete,
    check_decision,
    check_depreciation,
    check_disposal_request,
    check_editable,
    check_line,
    check_manual_status,
    depreciate,
    due_state,
    effective_depreciation,
    fmt,
    money,
    month_end,
    month_ends,
    next_verification_due,
    project,
    residual_value,
    run_period,
    tag_for,
    transfer_changes,
)
from ..infrastructure import repository as repo
from ..infrastructure.config import ModuleSettings, load_settings
from ..infrastructure.models import (
    Asset,
    Category,
    Cycle,
    CycleLine,
    DepreciationLine,
    DepreciationRun,
    Disposal,
    Transfer,
    iso,
)

MODULE = "asset-management"
ASSET_READ = f"{MODULE}:asset:read"
ASSET_READ_ALL = f"{MODULE}:asset:read-all"
ASSET_MANAGE = f"{MODULE}:asset:manage"
VERIFY_PERFORM = f"{MODULE}:verification:perform"
VERIFY_MANAGE = f"{MODULE}:verification:manage"
DEPRECIATION_READ = f"{MODULE}:depreciation:read"
DEPRECIATION_MANAGE = f"{MODULE}:depreciation:manage"
DISPOSAL_REQUEST = f"{MODULE}:disposal:request"
DISPOSAL_APPROVE = f"{MODULE}:disposal:approve"


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


def today() -> date:
    return clock().date()


@dataclass
class Actor:
    """Who is calling. Built by the API layer from the verified token."""

    user_id: str
    organisation_id: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


class AssetError(Exception):
    """A refusal with an HTTP status and a contract error body ({code, message})."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def body(self) -> dict:
        return {"code": self.code, "message": self.message}


def _not_found(what: str) -> AssetError:
    return AssetError(404, "not_found", f"{what} not found in your organisation")


def _forbidden(message: str) -> AssetError:
    return AssetError(403, "forbidden", message)


def _rule(v: RuleViolationError) -> AssetError:
    return AssetError(v.status, v.code, v.message)


def _publish(db: Session, actor: Actor | None, name: str, organisation_id: str, payload: dict) -> None:
    events.publish(
        db,
        f"{MODULE}.{name}",
        organisation_id,
        {"organisation_id": organisation_id, **payload},
        actor=actor.user_id if actor else None,
    )


def _get(db: Session, model, row_id: str | None, what: str, *, lock: bool = False):
    row = repo.get_for_update(db, model, row_id) if lock and row_id else repo.get(db, model, row_id)
    if row is None:
        raise _not_found(what)
    return row


def _money(value: Decimal | None, currency: str) -> dict | None:
    return None if value is None else {"amount": fmt(value), "currency": currency}


def _amount(m: dict | None, settings: ModuleSettings, *, allow_negative: bool = False) -> Decimal | None:
    """A contract Money in the organisation's currency."""
    if not m:
        return None
    try:
        value = money(m["amount"], m["currency"], allow_negative=allow_negative)
    except RuleViolationError as v:
        raise _rule(v) from v
    if m["currency"] != settings.default_currency:
        raise AssetError(
            422, "currency_mismatch", f"amounts are recorded in {settings.default_currency} in this organisation"
        )
    return value


# ---------------------------------------------------------------- who sees what


def _sees(actor: Actor, a: Asset) -> bool:
    """Custodians without read-all see only the assets in their care."""
    return actor.can(ASSET_READ_ALL) or a.custodian_id == actor.user_id


def _asset_for(db: Session, actor: Actor, asset_id: str, *, lock: bool = False) -> Asset:
    a = repo.get_for_update(db, Asset, asset_id) if lock else repo.get(db, Asset, asset_id)
    if a is None or not _sees(actor, a):
        raise _not_found("asset")
    return a


# ---------------------------------------------------------------- shapes


def _category_settings(db: Session, category_id: str) -> tuple[Category | None, dict]:
    c = db.get(Category, category_id)
    return c, (c.depreciation if c else {}) or {}


def _effective(db: Session, a: Asset) -> Depreciation:
    _, cat = _category_settings(db, a.category_id)
    return effective_depreciation(cat, a.depreciation)


def _next_due(db: Session, a: Asset, settings: ModuleSettings) -> date | None:
    if a.status == "disposed":
        return None
    c = db.get(Category, a.category_id)
    interval = (c.verification_interval_months if c else None) or settings.default_verification_interval_months
    return next_verification_due(a.last_verified_at, a.in_service_date, interval)


def _book_value(a: Asset) -> Decimal:
    return Decimal(a.cost) - Decimal(a.accumulated_depreciation)


def category_dict(db: Session, c: Category) -> dict:
    return {
        "id": c.id,
        "organisation_id": c.organisation_id,
        "name": c.name,
        "code": c.code,
        "description": c.description,
        "depreciation": c.depreciation or {},
        "verification_interval_months": c.verification_interval_months,
        "asset_count": repo.count_in_category(db, c.id),
    }


def asset_dict(db: Session, a: Asset, settings: ModuleSettings | None = None) -> dict:
    settings = settings or load_settings()
    return {
        "id": a.id,
        "organisation_id": a.organisation_id,
        "tag": a.tag,
        "name": a.name,
        "category_id": a.category_id,
        "serial_number": a.serial_number,
        "make": a.make,
        "model": a.model,
        "description": a.description,
        "location": a.location,
        "org_unit_id": a.org_unit_id,
        "custodian_id": a.custodian_id,
        "condition": a.condition,
        "acquisition": {**(a.acquisition or {}), "cost": _money(Decimal(a.cost), a.currency)},
        "in_service_date": iso(a.in_service_date),
        "warranty_until": iso(a.warranty_until),
        "amc_reference": a.amc_reference,
        "inventory_unit_id": a.inventory_unit_id,
        "depreciation": a.depreciation or {},
        "attributes": a.attributes or {},
        "photo_document_ids": list(a.photo_document_ids or []),
        "status": a.status,
        "effective_depreciation": asdict(_effective(db, a)),
        "accumulated_depreciation": _money(Decimal(a.accumulated_depreciation), a.currency),
        "book_value": _money(_book_value(a), a.currency),
        "last_verified_at": iso(a.last_verified_at),
        "next_verification_due": iso(_next_due(db, a, settings)),
        "disposed_on": iso(a.disposed_on),
        "created_at": iso(a.created_at),
        "updated_at": iso(a.updated_at),
    }


def transfer_dict(t: Transfer) -> dict:
    return {
        "id": t.id,
        "organisation_id": t.organisation_id,
        "asset_id": t.asset_id,
        "from": t.from_values,
        "to": t.to_values,
        "effective_on": iso(t.effective_on),
        "reason": t.reason,
        "source": t.source,
        "recorded_by": t.recorded_by,
        "recorded_at": iso(t.created_at),
    }


def _counts(lines: list[CycleLine]) -> dict:
    out = {"total": len(lines), "pending": 0, "found": 0, "missing": 0, "damaged": 0, "relocated": 0}
    for line in lines:
        out[line.result] += 1
    return out


def cycle_dict(db: Session, c: Cycle) -> dict:
    return {
        "id": c.id,
        "organisation_id": c.organisation_id,
        "name": c.name,
        "due_on": iso(c.due_on),
        "scope": c.scope or {},
        "verifier_user_ids": list(c.verifier_user_ids or []),
        "status": c.status,
        "started_at": iso(c.started_at),
        "closed_at": iso(c.closed_at),
        "counts": _counts(repo.lines_of(db, c.id)),
    }


def line_dict(line: CycleLine) -> dict:
    return {
        "id": line.id,
        "cycle_id": line.cycle_id,
        "asset_id": line.asset_id,
        "tag": line.tag,
        "name": line.name,
        "expected_location": line.expected_location,
        "result": line.result,
        "observed_location": line.observed_location,
        "condition": line.condition,
        "note": line.note,
        "verified_by": line.verified_by,
        "verified_at": iso(line.verified_at),
    }


def run_dict(r: DepreciationRun) -> dict:
    return {
        "id": r.id,
        "organisation_id": r.organisation_id,
        "period_start": iso(r.period_start),
        "period_end": iso(r.period_end),
        "status": r.status,
        "asset_count": r.asset_count,
        "total": _money(Decimal(r.total), r.currency),
        "by_category": r.by_category or [],
        "calculated_at": iso(r.calculated_at),
        "posted_by": r.posted_by,
        "posted_at": iso(r.posted_at),
    }


def depreciation_line_dict(line: DepreciationLine, currency: str) -> dict:
    return {
        "asset_id": line.asset_id,
        "tag": line.tag,
        "category_id": line.category_id,
        "method": line.method,
        "opening_book_value": _money(Decimal(line.opening_book_value), currency),
        "amount": _money(Decimal(line.amount), currency),
        "closing_book_value": _money(Decimal(line.closing_book_value), currency),
    }


def disposal_dict(db: Session, d: Disposal) -> dict:
    a = db.get(Asset, d.asset_id)
    return {
        "id": d.id,
        "organisation_id": d.organisation_id,
        "asset_id": d.asset_id,
        "asset_tag": a.tag if a else None,
        "method": d.method,
        "status": d.status,
        "reason": d.reason,
        "expected_proceeds": _money(d.expected_proceeds, d.currency),
        "requested_by": d.requested_by,
        "requested_at": iso(d.created_at),
        "decided_by": d.decided_by,
        "decision_note": d.decision_note,
        "disposed_on": iso(d.disposed_on),
        "proceeds": _money(d.proceeds, d.currency),
        "book_value_at_disposal": _money(d.book_value_at_disposal, d.currency),
        "gain_or_loss": _money(d.gain_or_loss, d.currency),
        "recipient": d.recipient,
    }


# ---------------------------------------------------------------- categories


def _check_settings(d: Depreciation) -> None:
    try:
        check_depreciation(d)
    except RuleViolationError as v:
        raise _rule(v) from v


def list_categories(db: Session) -> list[dict]:
    return [category_dict(db, c) for c in repo.all_of(db, Category, Category.name)]


def create_category(db: Session, actor: Actor, data: dict) -> dict:
    if repo.first_by(db, Category, "name", data["name"]):
        raise AssetError(409, "name_taken", "a category with this name already exists")
    _check_settings(effective_depreciation(data.get("depreciation"), None))
    c = Category(organisation_id=actor.organisation_id, created_at=clock(), **data)
    db.add(c)
    db.commit()
    return category_dict(db, c)


def update_category(db: Session, actor: Actor, category_id: str, data: dict) -> dict:
    c = _get(db, Category, category_id, "category")
    if "name" in data and data["name"] != c.name and repo.first_by(db, Category, "name", data["name"]):
        raise AssetError(409, "name_taken", "a category with this name already exists")
    if "depreciation" in data:
        _check_settings(effective_depreciation(data["depreciation"], None))
    for key, value in data.items():
        setattr(c, key, value)
    db.commit()
    return category_dict(db, c)


# ---------------------------------------------------------------- the register


def list_assets(db: Session, actor: Actor, q: dict, page: int, page_size: int) -> dict:
    settings = load_settings()
    items = [a for a in repo.assets(db) if _sees(actor, a)]
    for key in ("category_id", "org_unit_id", "custodian_id"):
        if q.get(key):
            items = [a for a in items if getattr(a, key) == q[key]]
    if q.get("status"):
        items = [a for a in items if a.status in set(q["status"])]
    if q.get("location"):
        needle = q["location"].lower()
        items = [a for a in items if needle in (a.location or "").lower()]
    if q.get("verification_due_before"):
        items = [a for a in items if (due := _next_due(db, a, settings)) and due < q["verification_due_before"]]
    if q.get("warranty_expires_before"):
        items = [a for a in items if a.warranty_until and a.warranty_until < q["warranty_expires_before"]]
    if q.get("q"):
        needle = q["q"].lower()
        items = [
            a
            for a in items
            if needle in " ".join(filter(None, (a.tag, a.name, a.serial_number, a.make, a.model))).lower()
        ]
    total = len(items)
    chunk = items[(page - 1) * page_size : page * page_size]
    return {"items": [asset_dict(db, a, settings) for a in chunk], "total": total, "page": page, "page_size": page_size}


def get_asset(db: Session, actor: Actor, asset_id: str) -> dict:
    return asset_dict(db, _asset_for(db, actor, asset_id))


def _category(db: Session, category_id: str) -> Category:
    c = repo.get(db, Category, category_id)
    if c is None:
        raise AssetError(422, "unknown_category", "unknown category")
    return c


def _acquisition(data: dict, settings: ModuleSettings) -> tuple[dict, Decimal]:
    """Split the contract Acquisition into the stored details and the decimal cost."""
    acq = dict(data.get("acquisition") or {})
    cost = _amount(acq.pop("cost", None), settings) or ZERO
    if isinstance(acq.get("date"), date):
        acq["date"] = acq["date"].isoformat()  # stored as JSON
    return acq, cost


def register_asset(db: Session, actor: Actor, data: dict) -> dict:
    settings = load_settings()
    category = _category(db, data.pop("category_id"))
    acq, cost = _acquisition(data, settings)
    data.pop("acquisition", None)
    _check_settings(effective_depreciation(category.depreciation, data.get("depreciation")))
    wanted_tag = data.pop("tag", None)
    if wanted_tag and repo.first_by(db, Asset, "tag", wanted_tag):
        raise AssetError(409, "tag_taken", "an asset with this tag already exists")
    in_service = data.pop("in_service_date", None) or acq.get("date") or today()
    if isinstance(in_service, str):
        in_service = date.fromisoformat(in_service)
    # Two registrations at the same moment can be handed the same generated tag (the lock in repo.next_tag_number
    # covers Postgres; SQLite has none): the unique constraint refuses the second insert, which is retried once.
    for attempt in (1, 2):
        tag = wanted_tag or _generate_tag(db, actor.organisation_id, settings, category.code)
        a = Asset(
            organisation_id=actor.organisation_id,
            tag=tag,
            category_id=category.id,
            acquisition=acq,
            cost=cost,
            currency=settings.default_currency,
            in_service_date=in_service,
            created_at=clock(),
            updated_at=clock(),
            **data,
        )
        db.add(a)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
            if attempt == 2 or wanted_tag:
                raise AssetError(409, "tag_taken", "an asset with this tag already exists") from None
    _publish(
        db,
        actor,
        "asset.registered",
        a.organisation_id,
        {
            "asset_id": a.id,
            "tag": a.tag,
            "name": a.name,
            "category_id": a.category_id,
            "org_unit_id": a.org_unit_id,
            "custodian_id": a.custodian_id,
            "cost": _money(cost, a.currency),
            "purchase_reference": acq.get("purchase_reference"),
        },
    )
    db.commit()
    return asset_dict(db, a, settings)


def _generate_tag(db: Session, organisation_id: str, settings: ModuleSettings, code: str | None) -> str:
    number = repo.next_tag_number(db, organisation_id, settings.tag_prefix)
    while True:
        tag = tag_for(settings.tag_prefix, code, number)
        if not repo.first_by(db, Asset, "tag", tag):
            return tag
        number += 1  # a hand-chosen tag already uses this number


def update_asset(db: Session, actor: Actor, asset_id: str, data: dict) -> dict:
    settings = load_settings()
    a = _asset_for(db, actor, asset_id, lock=True)
    try:
        check_editable(a.status)
    except RuleViolationError as v:
        raise _rule(v) from v
    changed = sorted(data)
    if "category_id" in data:
        a.category_id = _category(db, data.pop("category_id")).id
    if "acquisition" in data:
        acq, cost = _acquisition(data, settings)
        data.pop("acquisition")
        a.acquisition, a.cost = acq, cost
    for key, value in data.items():
        setattr(a, key, value)
    _check_settings(_effective(db, a))
    a.updated_at = clock()
    _publish(db, actor, "asset.updated", a.organisation_id, {"asset_id": a.id, "changed": changed})
    db.commit()
    return asset_dict(db, a, settings)


def set_status(db: Session, actor: Actor, asset_id: str, status: str, condition: str | None, reason: str) -> dict:
    a = _asset_for(db, actor, asset_id, lock=True)
    try:
        check_manual_status(a.status, status)
    except RuleViolationError as v:
        raise _rule(v) from v
    old = a.status
    a.status = status
    if condition:
        a.condition = condition
    a.updated_at = clock()
    if old != status:
        _publish(
            db,
            actor,
            "asset.status-changed",
            a.organisation_id,
            {"asset_id": a.id, "tag": a.tag, "from": old, "to": status, "reason": reason},
        )
    db.commit()
    return asset_dict(db, a)


def _transfer(
    db: Session, actor: Actor, a: Asset, wanted: dict, reason: str, effective_on: date, source: str
) -> Transfer:
    current = {"location": a.location, "org_unit_id": a.org_unit_id, "custodian_id": a.custodian_id}
    try:
        check_editable(a.status)
        before, after = transfer_changes(current, wanted)
    except RuleViolationError as v:
        raise _rule(v) from v
    t = Transfer(
        organisation_id=a.organisation_id,
        asset_id=a.id,
        from_values=before,
        to_values=after,
        effective_on=effective_on,
        reason=reason,
        source=source,
        recorded_by=actor.user_id,
        created_at=clock(),
    )
    db.add(t)
    for key, value in after.items():
        setattr(a, key, value)
    a.updated_at = clock()
    db.flush()
    _publish(
        db,
        actor,
        "asset.transferred",
        a.organisation_id,
        {
            "asset_id": a.id,
            "transfer_id": t.id,
            "from": before,
            "to": after,
            "effective_on": iso(effective_on),
            "source": source,
        },
    )
    return t


def transfer_asset(db: Session, actor: Actor, asset_id: str, data: dict) -> dict:
    a = _asset_for(db, actor, asset_id, lock=True)
    wanted = {k: data[k] for k in ("location", "org_unit_id", "custodian_id") if k in data}
    t = _transfer(db, actor, a, wanted, data["reason"], data.get("effective_on") or today(), "manual")
    db.commit()
    return transfer_dict(t)


def list_transfers(db: Session, actor: Actor, asset_id: str) -> list[dict]:
    a = _asset_for(db, actor, asset_id)
    return [transfer_dict(t) for t in repo.transfers_of(db, a.id)]


def depreciation_schedule(db: Session, actor: Actor, asset_id: str) -> dict:
    a = _asset_for(db, actor, asset_id)
    d = _effective(db, a)
    cost = Decimal(a.cost)
    posted = []
    for line, run in repo.posted_lines_of(db, a.id):
        posted.append(
            {
                "run_id": run.id if run else None,
                "period_end": iso(line.period_end),
                "amount": _money(Decimal(line.amount), a.currency),
                "book_value_after": _money(Decimal(line.closing_book_value), a.currency),
            }
        )
    projected = []
    if a.status != "disposed":
        for m, amount, after in project(d, cost, _book_value(a), a.in_service_date, a.depreciated_to):
            projected.append(
                {
                    "period_end": iso(m),
                    "amount": _money(amount, a.currency),
                    "book_value_after": _money(after, a.currency),
                }
            )
    return {
        "asset_id": a.id,
        "method": d.method,
        "cost": _money(cost, a.currency),
        "residual_value": _money(residual_value(cost, d), a.currency),
        "posted": posted,
        "projected": projected,
    }


# ---------------------------------------------------------------- verification


def verifications_due(db: Session, actor: Actor, within_days: int | None, org_unit_id: str | None) -> dict:
    settings = load_settings()
    window = settings.verification_due_soon_days if within_days is None else within_days
    now = today()
    rows = []
    for a in repo.assets(db):
        if not _sees(actor, a) or a.status in IN_DISPOSAL:
            continue
        if org_unit_id and a.org_unit_id != org_unit_id:
            continue
        due = _next_due(db, a, settings)
        state = due_state(due, now, window)
        if state:
            rows.append((state == "overdue", due, a))
    rows.sort(key=lambda r: (not r[0], r[1], r[2].tag))
    open_cycles = []
    if actor.can(VERIFY_PERFORM) or actor.can(ASSET_READ_ALL):
        open_cycles = [cycle_dict(db, c) for c in repo.all_of(db, Cycle, Cycle.due_on) if c.status != "closed"]
    return {
        "within_days": window,
        "overdue_count": sum(1 for r in rows if r[0]),
        "due_soon_count": sum(1 for r in rows if not r[0]),
        "assets": [
            {
                "asset_id": a.id,
                "tag": a.tag,
                "name": a.name,
                "location": a.location,
                "org_unit_id": a.org_unit_id,
                "next_verification_due": iso(due),
                "overdue": overdue,
            }
            for overdue, due, a in rows
        ],
        "open_cycles": open_cycles,
    }


def list_cycles(db: Session, status: str | None) -> list[dict]:
    cycles = repo.all_of(db, Cycle, Cycle.due_on)
    return [cycle_dict(db, c) for c in cycles if not status or c.status == status]


def create_cycle(db: Session, actor: Actor, data: dict) -> dict:
    c = Cycle(organisation_id=actor.organisation_id, status="planned", created_at=clock(), **data)
    db.add(c)
    db.commit()
    return cycle_dict(db, c)


def get_cycle(db: Session, cycle_id: str) -> dict:
    return cycle_dict(db, _get(db, Cycle, cycle_id, "verification cycle"))


def _in_scope(db: Session, a: Asset, scope: dict, due_on: date, settings: ModuleSettings) -> bool:
    if a.status in IN_DISPOSAL:
        return False
    if scope.get("category_ids") and a.category_id not in scope["category_ids"]:
        return False
    if scope.get("org_unit_ids") and a.org_unit_id not in scope["org_unit_ids"]:
        return False
    if scope.get("location_contains") and scope["location_contains"].lower() not in (a.location or "").lower():
        return False
    if scope.get("only_due"):
        due = _next_due(db, a, settings)
        return due is not None and due <= due_on
    return True


def start_cycle(db: Session, actor: Actor, cycle_id: str) -> dict:
    settings = load_settings()
    c = _get(db, Cycle, cycle_id, "verification cycle", lock=True)
    if c.status != "planned":
        raise AssetError(409, "not_planned", "only a planned cycle can be started")
    in_scope = [a for a in repo.assets(db) if _in_scope(db, a, c.scope or {}, c.due_on, settings)]
    for a in in_scope:
        db.add(
            CycleLine(
                organisation_id=c.organisation_id,
                cycle_id=c.id,
                asset_id=a.id,
                tag=a.tag,
                name=a.name,
                expected_location=a.location,
            )
        )
    c.status, c.started_at = "in_progress", clock()
    _publish(
        db,
        actor,
        "verification-cycle.started",
        c.organisation_id,
        {
            "cycle_id": c.id,
            "name": c.name,
            "due_on": iso(c.due_on),
            "asset_count": len(in_scope),
            "verifier_user_ids": list(c.verifier_user_ids or []),
        },
    )
    db.commit()
    return cycle_dict(db, c)


def list_lines(db: Session, cycle_id: str, result: str | None, page: int, page_size: int) -> dict:
    c = _get(db, Cycle, cycle_id, "verification cycle")
    lines = [x for x in repo.lines_of(db, c.id) if not result or x.result == result]
    chunk = lines[(page - 1) * page_size : page * page_size]
    return {"items": [line_dict(x) for x in chunk], "total": len(lines), "page": page, "page_size": page_size}


def record_lines(db: Session, actor: Actor, cycle_id: str, inputs: list[dict]) -> list[dict]:
    c = _get(db, Cycle, cycle_id, "verification cycle", lock=True)
    if c.status != "in_progress":
        raise AssetError(409, "not_in_progress", "results are recorded only while the cycle is in progress")
    lines = repo.lines_of(db, c.id)
    by_asset = {x.asset_id: x for x in lines}
    by_tag = {x.tag: x for x in lines}
    updated = []
    now = clock()
    for item in inputs:
        line = by_asset.get(item.get("asset_id") or "") or by_tag.get(item.get("tag") or "")
        if line is None:
            ref = item.get("asset_id") or item.get("tag")
            raise AssetError(422, "not_in_cycle", f"{ref} is not part of this cycle")
        try:
            check_line(item["result"], item.get("observed_location"))
        except RuleViolationError as v:
            raise _rule(v) from v
        line.result = item["result"]
        line.observed_location = item.get("observed_location")
        line.condition = item.get("condition")
        line.note = item.get("note")
        line.photo_document_id = item.get("photo_document_id")
        line.verified_by, line.verified_at = actor.user_id, now
        updated.append(line)
    db.commit()
    return [line_dict(x) for x in updated]


def close_cycle(db: Session, actor: Actor, cycle_id: str, close_with_pending: bool, note: str | None) -> dict:
    c = _get(db, Cycle, cycle_id, "verification cycle", lock=True)
    if c.status != "in_progress":
        raise AssetError(409, "not_in_progress", "only a cycle in progress can be closed")
    lines = repo.lines_of(db, c.id)
    try:
        check_close(sum(1 for x in lines if x.result == "pending"), close_with_pending)
    except RuleViolationError as v:
        raise _rule(v) from v
    day = today()
    missing_ids: list[str] = []
    for line in lines:
        if line.result == "pending":
            line.result = "missing"
        a = db.get(Asset, line.asset_id)
        if a is None or a.status == "disposed":
            continue
        if line.result == "missing":
            missing_ids.append(a.id)
            if a.status not in ("missing", *IN_DISPOSAL):
                old, a.status = a.status, "missing"
                _publish(
                    db,
                    actor,
                    "asset.status-changed",
                    a.organisation_id,
                    {
                        "asset_id": a.id,
                        "tag": a.tag,
                        "from": old,
                        "to": "missing",
                        "reason": f"not found in verification cycle {c.name}",
                    },
                )
            continue
        a.last_verified_at, a.overdue_notified_for = day, None
        if line.condition:
            a.condition = line.condition
        elif line.result == "damaged":
            a.condition = "damaged"
        if line.result == "relocated" and line.observed_location != a.location:
            reason = f"found at {line.observed_location} in verification cycle {c.name}"
            _transfer(db, actor, a, {"location": line.observed_location}, reason, day, "verification")
        a.updated_at = clock()
    counts = _counts(lines)
    c.status, c.closed_at, c.close_note = "closed", clock(), note
    _publish(
        db,
        actor,
        "verification-cycle.closed",
        c.organisation_id,
        {
            "cycle_id": c.id,
            "found": counts["found"],
            "missing": counts["missing"],
            "damaged": counts["damaged"],
            "relocated": counts["relocated"],
            "missing_asset_ids": missing_ids,
        },
    )
    db.commit()
    return cycle_dict(db, c)


# ---------------------------------------------------------------- depreciation


def list_runs(db: Session) -> list[dict]:
    return [run_dict(r) for r in repo.runs(db)]


def get_run(db: Session, run_id: str) -> dict:
    return run_dict(_get(db, DepreciationRun, run_id, "depreciation run"))


def _delete_run(db: Session, r: DepreciationRun) -> None:
    for line in repo.run_lines(db, r.id):
        db.delete(line)
    db.delete(r)


def calculate_run(db: Session, actor: Actor, period_end: date, category_ids: list[str] | None) -> dict:
    """Calculate a draft for the period, replacing an existing draft for the same period (rule 5)."""
    settings = load_settings()
    try:
        period_start = run_period(period_end, repo.last_posted_end(db))
    except RuleViolationError as v:
        raise _rule(v) from v
    for old in repo.runs(db):
        if old.status == "draft" and old.period_end == period_end:
            _delete_run(db, old)
    db.flush()
    r = DepreciationRun(
        organisation_id=actor.organisation_id,
        period_start=period_start,
        period_end=period_end,
        status="draft",
        currency=settings.default_currency,
        category_ids=list(category_ids or []),
        created_at=clock(),
    )
    db.add(r)
    db.flush()
    totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    counts: dict[str, int] = defaultdict(int)
    for a in repo.assets(db):
        if a.status == "disposed" or a.in_service_date > period_end:
            continue
        if category_ids and a.category_id not in category_ids:
            continue
        d = _effective(db, a)
        # From the month it went into service, or after what is already posted: an asset registered late, or left
        # out of an earlier run by its category filter, catches up here (corrections go into the next period).
        months = [m for m in month_ends(a.in_service_date, period_end) if not a.depreciated_to or m > a.depreciated_to]
        opening = _book_value(a)
        amount, closing, _ = depreciate(d, Decimal(a.cost), opening, a.in_service_date, months)
        if amount <= 0:
            continue
        db.add(
            DepreciationLine(
                organisation_id=a.organisation_id,
                run_id=r.id,
                asset_id=a.id,
                category_id=a.category_id,
                tag=a.tag,
                method=d.method,
                period_end=period_end,
                opening_book_value=opening,
                amount=amount,
                closing_book_value=closing,
            )
        )
        totals[a.category_id] += amount
        counts[a.category_id] += 1
    r.total = sum(totals.values(), ZERO)
    r.asset_count = sum(counts.values())
    r.by_category = [
        {"category_id": cid, "amount": _money(totals[cid], r.currency), "asset_count": counts[cid]}
        for cid in sorted(totals)
    ]
    r.calculated_at = clock()
    db.commit()
    return run_dict(r)


def delete_run(db: Session, actor: Actor, run_id: str) -> None:
    r = _get(db, DepreciationRun, run_id, "depreciation run", lock=True)
    if r.status == "posted":
        raise AssetError(409, "run_posted", "a posted run cannot change; correct it in the next period")
    _delete_run(db, r)
    db.commit()


def list_run_lines(db: Session, run_id: str, category_id: str | None, page: int, page_size: int) -> dict:
    r = _get(db, DepreciationRun, run_id, "depreciation run")
    lines = [x for x in repo.run_lines(db, r.id) if not category_id or x.category_id == category_id]
    chunk = lines[(page - 1) * page_size : page * page_size]
    return {
        "items": [depreciation_line_dict(x, r.currency) for x in chunk],
        "total": len(lines),
        "page": page,
        "page_size": page_size,
    }


def post_run(db: Session, actor: Actor, run_id: str) -> dict:
    r = _get(db, DepreciationRun, run_id, "depreciation run", lock=True)
    if r.status != "draft":
        raise AssetError(409, "not_draft", "only a calculated draft can be posted")
    last = repo.last_posted_end(db)
    if any(x.status == "draft" and x.period_end < r.period_end for x in repo.runs(db)):
        raise AssetError(409, "earlier_not_posted", "post or delete the earlier draft first")
    if (last and r.period_start != last + timedelta(days=1)) or (not last and r.period_start > r.period_end):
        raise AssetError(409, "run_stale", "another period was posted since this draft; recalculate it")
    lines = repo.run_lines(db, r.id)
    for line in lines:
        a = db.get(Asset, line.asset_id)
        if a is None or a.status == "disposed" or _book_value(a) != Decimal(line.opening_book_value):
            raise AssetError(409, "run_stale", f"{line.tag} changed since this draft; recalculate it")
    for line in lines:
        a = db.get(Asset, line.asset_id)
        a.accumulated_depreciation = Decimal(a.accumulated_depreciation) + Decimal(line.amount)
        a.depreciated_to = r.period_end
    r.status, r.posted_by, r.posted_at = "posted", actor.user_id, clock()
    _publish(
        db,
        actor,
        "depreciation-run.posted",
        r.organisation_id,
        {
            "run_id": r.id,
            "period_start": iso(r.period_start),
            "period_end": iso(r.period_end),
            "total": _money(Decimal(r.total), r.currency),
            "by_category": r.by_category or [],
        },
    )
    db.commit()
    return run_dict(r)


# ---------------------------------------------------------------- disposal


def _disposal_for(db: Session, actor: Actor, disposal_id: str, *, lock: bool = False) -> Disposal:
    d = repo.get_for_update(db, Disposal, disposal_id) if lock else repo.get(db, Disposal, disposal_id)
    if d is None or not (actor.can(DISPOSAL_APPROVE) or actor.can(ASSET_MANAGE) or d.requested_by == actor.user_id):
        raise _not_found("disposal")
    return d


def list_disposals(db: Session, actor: Actor, status: str | None, page: int, page_size: int) -> dict:
    items = repo.all_of(db, Disposal, Disposal.created_at)
    if not actor.can(DISPOSAL_APPROVE):
        items = [d for d in items if d.requested_by == actor.user_id]
    if status:
        items = [d for d in items if d.status == status]
    chunk = items[(page - 1) * page_size : page * page_size]
    return {"items": [disposal_dict(db, d) for d in chunk], "total": len(items), "page": page, "page_size": page_size}


def get_disposal(db: Session, actor: Actor, disposal_id: str) -> dict:
    return disposal_dict(db, _disposal_for(db, actor, disposal_id))


def request_disposal(db: Session, actor: Actor, data: dict) -> dict:
    settings = load_settings()
    a = _asset_for(db, actor, data["asset_id"], lock=True)
    if not (actor.can(ASSET_MANAGE) or a.custodian_id == actor.user_id):
        raise _forbidden(f"only the custodian or {ASSET_MANAGE} can request a disposal")
    try:
        check_disposal_request(a.status)
    except RuleViolationError as v:
        raise _rule(v) from v
    d = Disposal(
        organisation_id=a.organisation_id,
        asset_id=a.id,
        method=data["method"],
        reason=data["reason"],
        expected_proceeds=_amount(data.get("expected_proceeds"), settings),
        currency=settings.default_currency,
        requested_by=actor.user_id,
        created_at=clock(),
    )
    db.add(d)
    a.status_before_disposal, a.status, a.updated_at = a.status, "disposal_pending", clock()
    db.flush()
    _publish(
        db,
        actor,
        "disposal.requested",
        d.organisation_id,
        {
            "disposal_id": d.id,
            "asset_id": a.id,
            "method": d.method,
            "reason": d.reason,
            "requested_by": actor.user_id,
        },
    )
    db.commit()
    return disposal_dict(db, d)


def _restore(db: Session, d: Disposal) -> None:
    a = db.get(Asset, d.asset_id)
    if a is not None and a.status == "disposal_pending":
        a.status, a.status_before_disposal, a.updated_at = a.status_before_disposal or "in_service", None, clock()


def decide_disposal(db: Session, actor: Actor, disposal_id: str, approve: bool, note: str | None) -> dict:
    d = _disposal_for(db, actor, disposal_id, lock=True)
    try:
        check_decision(d.status, d.requested_by, actor.user_id)
    except RuleViolationError as v:
        raise _rule(v) from v
    d.decided_by, d.decision_note = actor.user_id, note
    if approve:
        d.status = "approved"
        _publish(
            db,
            actor,
            "disposal.approved",
            d.organisation_id,
            {"disposal_id": d.id, "asset_id": d.asset_id, "approved_by": actor.user_id},
        )
    else:
        d.status = "rejected"
        _restore(db, d)
        _publish(
            db,
            actor,
            "disposal.rejected",
            d.organisation_id,
            {"disposal_id": d.id, "asset_id": d.asset_id, "rejected_by": actor.user_id, "reason": note},
        )
    db.commit()
    return disposal_dict(db, d)


def cancel_disposal(db: Session, actor: Actor, disposal_id: str) -> dict:
    d = _disposal_for(db, actor, disposal_id, lock=True)
    if not (d.requested_by == actor.user_id or actor.can(DISPOSAL_APPROVE)):
        raise _forbidden(f"only the requester or {DISPOSAL_APPROVE} can cancel a disposal")
    try:
        check_cancel(d.status)
    except RuleViolationError as v:
        raise _rule(v) from v
    d.status = "cancelled"
    _restore(db, d)
    _publish(
        db,
        actor,
        "disposal.cancelled",
        d.organisation_id,
        {"disposal_id": d.id, "asset_id": d.asset_id, "cancelled_by": actor.user_id},
    )
    db.commit()
    return disposal_dict(db, d)


def complete_disposal(db: Session, actor: Actor, disposal_id: str, data: dict) -> dict:
    """Depreciate up to the disposal date, compute gain or loss against book value, set the asset disposed."""
    settings = load_settings()
    d = _disposal_for(db, actor, disposal_id, lock=True)
    try:
        check_complete(d.status)
    except RuleViolationError as v:
        raise _rule(v) from v
    a = repo.get_for_update(db, Asset, d.asset_id)
    disposed_on: date = data["disposed_on"]
    if disposed_on < a.in_service_date:
        raise AssetError(422, "invalid_date", "disposed_on is before the asset went into service")
    if a.depreciated_to and disposed_on <= a.depreciated_to:
        raise AssetError(422, "invalid_date", f"depreciation is already posted up to {iso(a.depreciated_to)}")
    proceeds = _amount(data.get("proceeds"), settings) or ZERO
    dep = _effective(db, a)
    opening = _book_value(a)
    months = [m for m in month_ends(a.in_service_date, disposed_on) if not a.depreciated_to or m > a.depreciated_to]
    amount, closing, _ = depreciate(dep, Decimal(a.cost), opening, a.in_service_date, months)
    if amount > 0:
        db.add(
            DepreciationLine(
                organisation_id=a.organisation_id,
                run_id=None,
                asset_id=a.id,
                category_id=a.category_id,
                tag=a.tag,
                method=dep.method,
                period_end=disposed_on,
                opening_book_value=opening,
                amount=amount,
                closing_book_value=closing,
                kind="disposal",
            )
        )
        a.accumulated_depreciation = Decimal(a.accumulated_depreciation) + amount
        a.depreciated_to = month_end(disposed_on)
    book_value = _book_value(a)
    d.status, d.disposed_on, d.proceeds = "completed", disposed_on, proceeds
    d.book_value_at_disposal, d.gain_or_loss = book_value, proceeds - book_value
    d.recipient, d.certificate_document_id, d.completion_note = (
        data.get("recipient"),
        data.get("certificate_document_id"),
        data.get("note"),
    )
    a.status, a.disposed_on, a.status_before_disposal, a.updated_at = "disposed", disposed_on, None, clock()
    _publish(
        db,
        actor,
        "asset.disposed",
        a.organisation_id,
        {
            "asset_id": a.id,
            "disposal_id": d.id,
            "tag": a.tag,
            "method": d.method,
            "disposed_on": iso(disposed_on),
            "proceeds": _money(proceeds, d.currency),
            "book_value": _money(book_value, d.currency),
            "gain_or_loss": _money(d.gain_or_loss, d.currency),
            "inventory_unit_id": a.inventory_unit_id,
        },
    )
    db.commit()
    return disposal_dict(db, d)


# ---------------------------------------------------------------- summary and the overdue sweep


def summary(db: Session) -> dict:
    settings = load_settings()
    now = today()
    assets = repo.assets(db)
    live = [a for a in assets if a.status != "disposed"]
    by_status: dict[str, int] = defaultdict(int)
    for a in assets:
        by_status[a.status] += 1
    states = [due_state(_next_due(db, a, settings), now, settings.verification_due_soon_days) for a in live]
    horizon = now + timedelta(days=30)
    return {
        "assets_total": len(assets),
        "by_status": dict(by_status),
        "verification_overdue": states.count("overdue"),
        "verification_due_soon": states.count("due_soon"),
        "open_cycles": sum(1 for c in repo.all_of(db, Cycle) if c.status != "closed"),
        "disposals_awaiting_approval": sum(1 for d in repo.all_of(db, Disposal) if d.status == "requested"),
        "warranties_expiring_30_days": sum(1 for a in live if a.warranty_until and now <= a.warranty_until <= horizon),
        "total_cost": _money(sum((Decimal(a.cost) for a in live), ZERO), settings.default_currency),
        "total_book_value": _money(sum((_book_value(a) for a in live), ZERO), settings.default_currency),
    }


def flag_overdue(db: Session, a: Asset, now: date, settings: ModuleSettings) -> bool:
    """Publish asset-management.asset.verification-overdue once per due date (rule 3)."""
    due = _next_due(db, a, settings)
    if due is None or due >= now or a.overdue_notified_for == due:
        return False
    a.overdue_notified_for = due
    _publish(
        db,
        None,
        "asset.verification-overdue",
        a.organisation_id,
        {
            "asset_id": a.id,
            "tag": a.tag,
            "next_verification_due": iso(due),
            "org_unit_id": a.org_unit_id,
            "custodian_id": a.custodian_id,
        },
    )
    return True
