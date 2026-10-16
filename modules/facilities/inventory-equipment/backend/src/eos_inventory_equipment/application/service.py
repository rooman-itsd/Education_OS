"""Use cases of inventory-equipment (docs/prd.md). Each one checks permissions and rules, changes state, writes
the stock ledger for every quantity change, and publishes the matching event from contracts/events.yaml to
the outbox in the same transaction. Until the audit SDK exists, the outbox is the audit trail (PRD rule 13)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.orm import Session

from ..domain.rules import (
    OUT_LOAN_STATUSES,
    LoanRules,
    RuleViolationError,
    StockShortageError,
    check_due,
    check_loan_line,
    check_open_loans,
    days_late,
    effective_rules,
    loan_status,
    low_stock_transition,
    take,
)
from ..infrastructure import repository as repo
from ..infrastructure.config import ModuleSettings, load_settings
from ..infrastructure.models import Category, Item, Loan, LoanLine, Location, Movement, StockLevel, Unit, as_utc, iso

MODULE = "inventory-equipment"
ITEM_READ = f"{MODULE}:item:read"
ITEM_MANAGE = f"{MODULE}:item:manage"
STOCK_READ = f"{MODULE}:stock:read"
STOCK_MANAGE = f"{MODULE}:stock:manage"
LOAN_READ = f"{MODULE}:loan:read"
LOAN_READ_ALL = f"{MODULE}:loan:read-all"
LOAN_REQUEST = f"{MODULE}:loan:request"
LOAN_APPROVE = f"{MODULE}:loan:approve"
LOAN_MANAGE = f"{MODULE}:loan:manage"


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

    def can(self, permission: str) -> bool:
        return permission in self.permissions


class InventoryError(Exception):
    """A refusal with an HTTP status and a contract error body ({code, message, ...})."""

    def __init__(self, status: int, code: str, message: str, **extra) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra

    def body(self) -> dict:
        return {"code": self.code, "message": self.message, **self.extra}


def _not_found(what: str) -> InventoryError:
    return InventoryError(404, "not_found", f"{what} not found in your organisation")


def _forbidden(message: str) -> InventoryError:
    return InventoryError(403, "forbidden", message)


def _rule_error(v: RuleViolationError) -> InventoryError:
    extra = {"rule": v.rule} if v.rule else {}
    if v.limit is not None:
        extra["limit"] = v.limit
    return InventoryError(422, v.code, v.message, **extra)


def _stock_error(e: StockShortageError, item_id: str | None = None) -> InventoryError:
    extra = {
        k: v
        for k, v in {"item_id": item_id, "available": e.available, "requested": e.requested}.items()
        if v is not None
    }
    return InventoryError(409, e.code, e.message, **extra)


def _publish(db: Session, actor: Actor | None, name: str, organisation_id: str, payload: dict) -> None:
    events.publish(
        db,
        f"{MODULE}.{name}",
        organisation_id,
        {"organisation_id": organisation_id, **payload},
        actor=actor.user_id if actor else None,
    )


def _get(db: Session, model, row_id: str | None, what: str):
    row = repo.get(db, model, row_id)
    if row is None:
        raise _not_found(what)
    return row


# ---------------------------------------------------------------- stock figures


def figures(db: Session, item: Item) -> dict:
    """on_hand (in the stores, incl. reserved), available (can be lent or issued now), on_loan, reserved."""
    if item.tracking == "individual":
        units = repo.units_of(db, item.id)
        count = {s: sum(1 for u in units if u.status == s) for s in ("available", "reserved", "on_loan")}
        return {
            "on_hand": float(count["available"] + count["reserved"]),
            "available": float(count["available"]),
            "on_loan": float(count["on_loan"]),
            "reserved": float(count["reserved"]),
        }
    levels = repo.stock_levels(db, item_id=item.id)
    on_hand = sum(s.on_hand for s in levels)
    reserved = sum(s.reserved for s in levels)
    return {
        "on_hand": on_hand,
        "available": on_hand - reserved,
        "on_loan": repo.out_quantity(db, item.id),
        "reserved": reserved,
    }


def _refresh_low_stock(db: Session, actor: Actor | None, item: Item) -> None:
    """Publish stock.ran-low once when available crosses the reorder level, stock.replenished when it recovers."""
    db.flush()
    available = figures(db, item)["available"]
    change = low_stock_transition(available, item.reorder_level, item.low_since is not None)
    if change == "low":
        item.low_since = clock()
        _publish(
            db,
            actor,
            "stock.ran-low",
            item.organisation_id,
            {
                "item_id": item.id,
                "item_name": item.name,
                "available": available,
                "reorder_level": item.reorder_level,
                "reorder_quantity": item.reorder_quantity,
                "unit_of_measure": item.unit_of_measure,
            },
        )
    elif change == "replenished":
        item.low_since = None
        _publish(
            db,
            actor,
            "stock.replenished",
            item.organisation_id,
            {
                "item_id": item.id,
                "available": available,
                "reorder_level": item.reorder_level,
            },
        )


def _level(db: Session, item: Item, location_id: str) -> StockLevel:
    level = repo.stock_level(db, item.id, location_id, lock=True)
    if level is None:
        level = StockLevel(
            organisation_id=item.organisation_id, item_id=item.id, location_id=location_id, on_hand=0, reserved=0
        )
        db.add(level)
        db.flush()
    return level


def _take_from(db: Session, item: Item, location_id: str, quantity: float) -> None:
    level = _level(db, item, location_id)
    try:
        level.on_hand = take(level.on_hand - level.reserved, quantity) + level.reserved
    except StockShortageError as e:
        raise _stock_error(e, item.id) from e


def _record(db: Session, actor: Actor, item: Item, kind: str, quantity: float, **fields) -> Movement:
    m = Movement(
        organisation_id=item.organisation_id,
        kind=kind,
        item_id=item.id,
        quantity=quantity,
        recorded_by=actor.user_id,
        unit_ids=fields.pop("unit_ids", None) or [],
        **fields,
    )
    db.add(m)
    db.flush()
    return m


# ---------------------------------------------------------------- serialisation


def category_dict(db: Session, c: Category) -> dict:
    return {
        "id": c.id,
        "organisation_id": c.organisation_id,
        "name": c.name,
        "description": c.description,
        "approver_user_ids": list(c.approver_user_ids or []),
        "default_loan_rules": dict(c.default_loan_rules or {}),
        "item_count": len(repo.by_field(db, Item, "category_id", c.id)),
    }


def location_dict(loc: Location) -> dict:
    return {
        "id": loc.id,
        "organisation_id": loc.organisation_id,
        "name": loc.name,
        "address": loc.address,
        "keeper_user_ids": list(loc.keeper_user_ids or []),
        "active": loc.active,
    }


def _rules_for(db: Session, item: Item, settings: ModuleSettings) -> LoanRules:
    category = repo.get(db, Category, item.category_id)
    return effective_rules(settings.default_rules(), category.default_loan_rules if category else None, item.loan_rules)


def item_dict(db: Session, item: Item, settings: ModuleSettings | None = None) -> dict:
    settings = settings or load_settings()
    f = figures(db, item)
    low = item.reorder_level is not None and f["available"] <= item.reorder_level
    return {
        "id": item.id,
        "organisation_id": item.organisation_id,
        "name": item.name,
        "code": item.code,
        "category_id": item.category_id,
        "tracking": item.tracking,
        "unit_of_measure": item.unit_of_measure,
        "loanable": item.loanable,
        "consumable": item.consumable,
        "reorder_level": item.reorder_level,
        "reorder_quantity": item.reorder_quantity,
        "description": item.description,
        "attributes": dict(item.attributes or {}),
        "image_document_id": item.image_document_id,
        "loan_rules": dict(item.loan_rules or {}),
        "active": item.active,
        "effective_loan_rules": _rules_for(db, item, settings).to_dict(),
        "on_hand": f["on_hand"],
        "available": f["available"],
        "on_loan": f["on_loan"],
        "low_stock": low,
        "created_at": iso(item.created_at),
        "updated_at": iso(item.updated_at),
    }


def unit_dict(u: Unit) -> dict:
    return {
        "id": u.id,
        "organisation_id": u.organisation_id,
        "item_id": u.item_id,
        "tag": u.tag,
        "serial_number": u.serial_number,
        "location_id": u.location_id,
        "condition": u.condition,
        "asset_id": u.asset_id,
        "notes": u.notes,
        "status": u.status,
        "current_loan_id": u.current_loan_id,
        "created_at": iso(u.created_at),
    }


def movement_dict(m: Movement) -> dict:
    return {
        "id": m.id,
        "organisation_id": m.organisation_id,
        "kind": m.kind,
        "item_id": m.item_id,
        "quantity": m.quantity,
        "unit_ids": list(m.unit_ids or []),
        "from_location_id": m.from_location_id,
        "to_location_id": m.to_location_id,
        "issued_to": m.issued_to,
        "reason": m.reason,
        "reference": m.reference,
        "loan_id": m.loan_id,
        "recorded_by": m.recorded_by,
        "recorded_at": iso(m.created_at),
    }


def _approval_categories(db: Session, lines: list[LoanLine], settings: ModuleSettings) -> list[Category]:
    """Categories of the loan's items whose rules require approval."""
    out: dict[str, Category] = {}
    for line in lines:
        item = repo.get(db, Item, line.item_id)
        if item and _rules_for(db, item, settings).requires_approval:
            category = repo.get(db, Category, item.category_id)
            if category:
                out[category.id] = category
    return list(out.values())


def _is_approver(actor: Actor, categories: list[Category]) -> bool:
    return (
        actor.can(LOAN_APPROVE)
        and bool(categories)
        and all(actor.user_id in (c.approver_user_ids or []) for c in categories)
    )


def allowed_actions(
    db: Session, actor: Actor, loan: Loan, lines: list[LoanLine], settings: ModuleSettings
) -> list[str]:
    manage = actor.can(LOAN_MANAGE)
    own = actor.user_id in (loan.borrower_id, loan.requested_by)
    can: list[str] = []
    if loan.status in ("requested", "approved") and (manage or own):
        can.append("cancel")
    if loan.status == "requested" and (manage or _is_approver(actor, _approval_categories(db, lines, settings))):
        can += ["approve", "reject"]
    if loan.status == "approved" and manage:
        can.append("hand_out")
    if loan.status in OUT_LOAN_STATUSES:
        if manage:
            can += ["return", "extend", "mark_lost"]
        elif actor.user_id == loan.borrower_id and loan.extensions == 0:
            can.append("extend")
    return can


def line_dict(db: Session, line: LoanLine) -> dict:
    item = repo.get(db, Item, line.item_id)
    unit = repo.get(db, Unit, line.unit_id)
    return {
        "id": line.id,
        "item_id": line.item_id,
        "item_name": item.name if item else None,
        "quantity": line.quantity,
        "unit_id": line.unit_id,
        "unit_tag": unit.tag if unit else None,
        "from_location_id": line.from_location_id,
        "condition_out": line.condition_out,
        "condition_in": line.condition_in,
        "status": line.status,
        "returned_at": iso(line.returned_at),
    }


def loan_dict(db: Session, actor: Actor, loan: Loan, settings: ModuleSettings | None = None) -> dict:
    settings = settings or load_settings()
    lines = repo.lines_of(db, loan.id)
    now = clock()
    overdue = loan.status in OUT_LOAN_STATUSES and now > as_utc(loan.due_at)
    return {
        "id": loan.id,
        "organisation_id": loan.organisation_id,
        "borrower_id": loan.borrower_id,
        "requested_by": loan.requested_by,
        "status": loan.status,
        "lines": [line_dict(db, line) for line in lines],
        "purpose": loan.purpose,
        "due_at": iso(loan.due_at),
        "handed_out_at": iso(loan.handed_out_at),
        "handed_out_by": loan.handed_out_by,
        "closed_at": iso(loan.closed_at),
        "decided_by": loan.decided_by,
        "decision_note": loan.decision_note,
        "extensions": loan.extensions,
        "days_overdue": days_late(as_utc(loan.due_at), now) if overdue else 0,
        "reference": loan.reference,
        "created_at": iso(loan.created_at),
        "can": allowed_actions(db, actor, loan, lines, settings),
    }


# ---------------------------------------------------------------- categories and locations


def list_categories(db: Session) -> list[dict]:
    return [category_dict(db, c) for c in repo.all_of(db, Category, Category.name)]


def create_category(db: Session, actor: Actor, data: dict) -> dict:
    if repo.first_by(db, Category, "name", data["name"]):
        raise InventoryError(409, "name_taken", "a category with this name already exists")
    c = Category(organisation_id=actor.organisation_id, **data)
    db.add(c)
    db.commit()
    return category_dict(db, c)


def update_category(db: Session, actor: Actor, category_id: str, data: dict) -> dict:
    c = _get(db, Category, category_id, "category")
    if "name" in data and data["name"] != c.name and repo.first_by(db, Category, "name", data["name"]):
        raise InventoryError(409, "name_taken", "a category with this name already exists")
    for key, value in data.items():
        setattr(c, key, value)
    db.commit()
    return category_dict(db, c)


def delete_category(db: Session, actor: Actor, category_id: str) -> None:
    c = _get(db, Category, category_id, "category")
    if repo.by_field(db, Item, "category_id", c.id):
        raise InventoryError(409, "category_in_use", "items still use this category")
    db.delete(c)
    db.commit()


def list_locations(db: Session) -> list[dict]:
    return [location_dict(loc) for loc in repo.all_of(db, Location, Location.name)]


def create_location(db: Session, actor: Actor, data: dict) -> dict:
    loc = Location(organisation_id=actor.organisation_id, **data)
    db.add(loc)
    db.commit()
    return location_dict(loc)


def update_location(db: Session, actor: Actor, location_id: str, data: dict) -> dict:
    loc = _get(db, Location, location_id, "location")
    if data.get("active") is False and loc.active and repo.location_holds_stock(db, loc.id):
        raise InventoryError(409, "location_holds_stock", "move the stock out before deactivating this location")
    for key, value in data.items():
        setattr(loc, key, value)
    db.commit()
    return location_dict(loc)


def _active_location(db: Session, location_id: str | None) -> Location:
    loc = _get(db, Location, location_id, "location")
    if not loc.active:
        raise InventoryError(422, "location_inactive", "this location is not active")
    return loc


# ---------------------------------------------------------------- items and units


def list_items(db: Session, filters: dict, page: int, page_size: int) -> dict:
    settings = load_settings()
    items = repo.all_of(db, Item, Item.name)
    for key in ("category_id", "tracking", "loanable"):
        if filters.get(key) is not None:
            items = [i for i in items if getattr(i, key) == filters[key]]
    if filters.get("q"):
        needle = filters["q"].lower()
        items = [
            i
            for i in items
            if needle
            in " ".join([i.name, i.code or "", *[f"{k} {v}" for k, v in (i.attributes or {}).items()]]).lower()
        ]
    if filters.get("available"):
        items = [i for i in items if figures(db, i)["available"] > 0]
    total = len(items)
    chunk = items[(page - 1) * page_size : page * page_size]
    return {"items": [item_dict(db, i, settings) for i in chunk], "total": total, "page": page, "page_size": page_size}


def create_item(db: Session, actor: Actor, data: dict) -> dict:
    _get(db, Category, data["category_id"], "category")
    if data.get("code") and repo.first_by(db, Item, "code", data["code"]):
        raise InventoryError(409, "code_taken", "an item with this code already exists")
    if data.get("consumable"):
        data["loanable"] = False  # a consumable is not loanable (contract ItemInput)
    item = Item(organisation_id=actor.organisation_id, **data)
    db.add(item)
    db.flush()
    _publish(
        db,
        actor,
        "item.created",
        item.organisation_id,
        {
            "item_id": item.id,
            "category_id": item.category_id,
            "name": item.name,
            "tracking": item.tracking,
            "consumable": item.consumable,
        },
    )
    db.commit()
    return item_dict(db, item)


def get_item(db: Session, item_id: str) -> dict:
    return item_dict(db, _get(db, Item, item_id, "item"))


def update_item(db: Session, actor: Actor, item_id: str, data: dict) -> dict:
    item = _get(db, Item, item_id, "item")
    if "category_id" in data:
        _get(db, Category, data["category_id"], "category")
    if data.get("code") and data["code"] != item.code and repo.first_by(db, Item, "code", data["code"]):
        raise InventoryError(409, "code_taken", "an item with this code already exists")
    if "tracking" in data and data["tracking"] != item.tracking and repo.item_has_stock_history(db, item.id):
        raise InventoryError(409, "tracking_locked", "tracking cannot change once stock exists")
    if data.get("consumable"):
        data["loanable"] = False
    changed = [k for k, v in data.items() if getattr(item, k) != v]
    for key in changed:
        setattr(item, key, data[key])
    if changed:
        _publish(
            db,
            actor,
            "item.updated",
            item.organisation_id,
            {"item_id": item.id, "changed": changed, "active": item.active},
        )
        if "reorder_level" in changed:
            _refresh_low_stock(db, actor, item)
    db.commit()
    return item_dict(db, item)


def list_units(db: Session, item_id: str, status: str | None) -> list[dict]:
    item = _get(db, Item, item_id, "item")
    return [unit_dict(u) for u in repo.units_of(db, item.id) if not status or u.status == status]


def register_unit(db: Session, actor: Actor, item_id: str, data: dict) -> dict:
    item = _get(db, Item, item_id, "item")
    if item.tracking != "individual":
        raise InventoryError(422, "wrong_tracking", "units exist only for individually tracked items")
    if repo.first_by(db, Unit, "tag", data["tag"]):
        raise InventoryError(409, "tag_taken", "a unit with this tag already exists")
    if not data.get("location_id"):
        raise InventoryError(422, "location_required", "a new unit needs a location")
    _active_location(db, data["location_id"])
    unit = Unit(organisation_id=item.organisation_id, item_id=item.id, status="available", **data)
    db.add(unit)
    db.flush()
    m = _record(db, actor, item, "receipt", 1, unit_ids=[unit.id], to_location_id=unit.location_id)
    _publish(
        db,
        actor,
        "stock.received",
        item.organisation_id,
        {
            "movement_id": m.id,
            "item_id": item.id,
            "location_id": unit.location_id,
            "quantity": 1,
            "unit_ids": [unit.id],
            "reference": None,
        },
    )
    _refresh_low_stock(db, actor, item)
    db.commit()
    return unit_dict(unit)


def get_unit(db: Session, actor: Actor, unit_id: str) -> dict:
    unit = _get(db, Unit, unit_id, "unit")
    approver_items = _approver_item_ids(db, actor)
    loan_ids = {line.loan_id for line in repo.by_field(db, LoanLine, "unit_id", unit.id)}
    loans = [loan for loan in (repo.get(db, Loan, loan_id) for loan_id in loan_ids) if loan is not None]
    loans.sort(key=lambda x: (as_utc(x.created_at), x.id))
    visible = [loan for loan in loans if _visible_loan(db, actor, loan, approver_items)]
    moves = [m for m in repo.movements(db) if unit.id in (m.unit_ids or [])]
    return unit_dict(unit) | {
        "recent_loans": [loan_dict(db, actor, loan) for loan in visible[-5:]],
        "recent_movements": [movement_dict(m) for m in moves[:10]],
    }


def update_unit(db: Session, actor: Actor, unit_id: str, data: dict) -> dict:
    unit = _get(db, Unit, unit_id, "unit")
    if "tag" in data and data["tag"] != unit.tag and repo.first_by(db, Unit, "tag", data["tag"]):
        raise InventoryError(409, "tag_taken", "a unit with this tag already exists")
    data.pop("location_id", None)  # moving a unit is a transfer movement
    data.pop("condition", None)  # condition changes through the status endpoint or a return
    for key, value in data.items():
        setattr(unit, key, value)
    db.commit()
    return unit_dict(unit)


def _condition_changed(db: Session, actor: Actor | None, unit: Unit, new: str, note: str | None, loan_id=None) -> None:
    if new and new != unit.condition:
        _publish(
            db,
            actor,
            "unit.condition-changed",
            unit.organisation_id,
            {
                "unit_id": unit.id,
                "item_id": unit.item_id,
                "asset_id": unit.asset_id,
                "from": unit.condition,
                "to": new,
                "note": note,
                "loan_id": loan_id,
            },
        )
        unit.condition = new


def set_unit_status(db: Session, actor: Actor, unit_id: str, data: dict) -> dict:
    unit = _get(db, Unit, unit_id, "unit")
    if unit.status in ("on_loan", "reserved"):
        raise InventoryError(409, "unit_on_loan", "a unit on loan or reserved changes only through its loan")
    item = _get(db, Item, unit.item_id, "item")
    status, reason = data.get("status"), data["reason"]
    if status and status != unit.status:
        _publish(
            db,
            actor,
            "unit.status-changed",
            unit.organisation_id,
            {
                "unit_id": unit.id,
                "item_id": unit.item_id,
                "asset_id": unit.asset_id,
                "from": unit.status,
                "to": status,
                "reason": reason,
            },
        )
        unit.status = status
    _condition_changed(db, actor, unit, data.get("condition"), reason)
    _refresh_low_stock(db, actor, item)
    db.commit()
    return unit_dict(unit)


# ---------------------------------------------------------------- stock


def list_stock(db: Session, item_id: str | None, location_id: str | None, category_id: str | None) -> list[dict]:
    items = {i.id: i for i in repo.all_of(db, Item)}
    locations = {loc.id: loc for loc in repo.all_of(db, Location)}
    rows: dict[tuple[str, str], dict] = {}

    def row(item: Item, loc_id: str) -> dict:
        key = (item.id, loc_id)
        if key not in rows:
            loc = locations.get(loc_id)
            rows[key] = {
                "item_id": item.id,
                "item_name": item.name,
                "location_id": loc_id,
                "location_name": loc.name if loc else None,
                "on_hand": 0.0,
                "reserved": 0.0,
                "available": 0.0,
                "unit_of_measure": item.unit_of_measure,
            }
        return rows[key]

    for level in repo.stock_levels(db, item_id=item_id, location_id=location_id):
        item = items.get(level.item_id)
        if item:
            r = row(item, level.location_id)
            r["on_hand"], r["reserved"], r["available"] = level.on_hand, level.reserved, level.on_hand - level.reserved
    for unit in repo.all_of(db, Unit):
        item = items.get(unit.item_id)
        if not item or not unit.location_id or (item_id and unit.item_id != item_id):
            continue
        if (location_id and unit.location_id != location_id) or unit.status not in ("available", "reserved"):
            continue
        r = row(item, unit.location_id)
        r["on_hand"] += 1
        r["reserved" if unit.status == "reserved" else "available"] += 1
    out = list(rows.values())
    if category_id:
        out = [r for r in out if items[r["item_id"]].category_id == category_id]
    return sorted(out, key=lambda r: (r["item_name"], r["location_name"] or ""))


def list_movements(db: Session, filters: dict, page: int, page_size: int) -> dict:
    moves = repo.movements(db)
    for key in ("item_id", "kind"):
        if filters.get(key):
            moves = [m for m in moves if getattr(m, key) == filters[key]]
    if filters.get("unit_id"):
        moves = [m for m in moves if filters["unit_id"] in (m.unit_ids or [])]
    if filters.get("location_id"):
        moves = [m for m in moves if filters["location_id"] in (m.from_location_id, m.to_location_id)]
    if filters.get("from"):
        moves = [m for m in moves if as_utc(m.created_at) >= as_utc(filters["from"])]
    if filters.get("to"):
        moves = [m for m in moves if as_utc(m.created_at) < as_utc(filters["to"])]
    total = len(moves)
    chunk = moves[(page - 1) * page_size : page * page_size]
    return {"items": [movement_dict(m) for m in chunk], "total": total, "page": page, "page_size": page_size}


def record_movement(db: Session, actor: Actor, data: dict) -> dict:
    """Receipt, issue, transfer, adjustment or write-off (PRD rule 2: every quantity change is a movement)."""
    item = repo.get_for_update(db, Item, data["item_id"])
    if item is None:
        raise _not_found("item")
    kind = data["kind"]
    if kind in ("adjustment", "write_off") and not data.get("reason"):
        raise InventoryError(422, "reason_required", f"a {kind.replace('_', '-')} needs a reason")
    if item.tracking == "individual":
        m = _move_units(db, actor, item, data)
    else:
        m = _move_quantity(db, actor, item, data)
    _publish_movement(db, actor, item, m)
    _refresh_low_stock(db, actor, item)
    db.commit()
    return movement_dict(m)


def _move_quantity(db: Session, actor: Actor, item: Item, data: dict) -> Movement:
    kind, qty = data["kind"], float(data["quantity"])
    src, dst = data.get("from_location_id"), data.get("to_location_id")
    fields = {"reason": data.get("reason"), "reference": data.get("reference")}
    if kind != "adjustment" and qty <= 0:
        raise InventoryError(422, "invalid_quantity", "quantity must be positive")
    if kind == "receipt":
        if not dst:
            raise InventoryError(422, "location_required", "a receipt needs to_location_id")
        _active_location(db, dst)
        _level(db, item, dst).on_hand += qty
        return _record(db, actor, item, kind, qty, to_location_id=dst, **fields)
    if kind in ("issue", "write_off"):
        if not src:
            raise InventoryError(422, "location_required", f"a {kind.replace('_', '-')} needs from_location_id")
        _get(db, Location, src, "location")
        _take_from(db, item, src, qty)
        return _record(db, actor, item, kind, qty, from_location_id=src, issued_to=data.get("issued_to"), **fields)
    if kind == "transfer":
        if not src or not dst or src == dst:
            raise InventoryError(422, "invalid_transfer", "a transfer needs two different locations")
        _get(db, Location, src, "location")
        _active_location(db, dst)
        _take_from(db, item, src, qty)
        _level(db, item, dst).on_hand += qty
        return _record(db, actor, item, kind, qty, from_location_id=src, to_location_id=dst, **fields)
    # adjustment: signed quantity at one location
    where = dst or src
    if not where or qty == 0:
        raise InventoryError(422, "invalid_adjustment", "an adjustment needs a location and a non-zero quantity")
    _get(db, Location, where, "location")
    level = _level(db, item, where)
    if level.on_hand + qty < level.reserved:
        raise _stock_error(
            StockShortageError("not_enough_stock", "stock cannot go negative", level.on_hand - level.reserved, -qty),
            item.id,
        )
    level.on_hand += qty
    return _record(db, actor, item, kind, qty, from_location_id=src, to_location_id=dst, **fields)


def _move_units(db: Session, actor: Actor, item: Item, data: dict) -> Movement:
    kind = data["kind"]
    unit_ids = data.get("unit_ids") or []
    if kind in ("receipt", "adjustment") or (kind == "issue" and not item.consumable):
        raise InventoryError(
            422, "wrong_tracking", "register units with POST /items/{id}/units; individual items are lent, not issued"
        )
    if not unit_ids:
        raise InventoryError(422, "units_required", "give unit_ids for an individually tracked item")
    units = []
    for unit_id in unit_ids:
        unit = repo.get(db, Unit, unit_id)
        if unit is None or unit.item_id != item.id:
            raise _not_found("unit")
        if unit.status != "available":
            raise InventoryError(409, "unit_not_available", f"unit {unit.tag} is {unit.status}", item_id=item.id)
        units.append(unit)
    fields = {"reason": data.get("reason"), "reference": data.get("reference"), "unit_ids": unit_ids}
    if kind == "transfer":
        dst = data.get("to_location_id")
        if not dst:
            raise InventoryError(422, "location_required", "a transfer needs to_location_id")
        _active_location(db, dst)
        src = units[0].location_id
        for unit in units:
            unit.location_id = dst
        return _record(db, actor, item, kind, len(units), from_location_id=src, to_location_id=dst, **fields)
    # write_off, or issue of a consumable that is tracked individually
    for unit in units:
        unit.status = "retired"
    return _record(
        db,
        actor,
        item,
        kind,
        len(units),
        from_location_id=units[0].location_id,
        issued_to=data.get("issued_to"),
        **fields,
    )


def _publish_movement(db: Session, actor: Actor, item: Item, m: Movement) -> None:
    base = {"movement_id": m.id, "item_id": item.id, "quantity": m.quantity}
    if m.kind == "receipt":
        _publish(
            db,
            actor,
            "stock.received",
            item.organisation_id,
            base | {"location_id": m.to_location_id, "unit_ids": list(m.unit_ids or []), "reference": m.reference},
        )
    elif m.kind == "issue":
        _publish(
            db,
            actor,
            "stock.issued",
            item.organisation_id,
            base | {"location_id": m.from_location_id, "issued_to": m.issued_to, "reference": m.reference},
        )
    else:
        _publish(
            db,
            actor,
            "stock.adjusted",
            item.organisation_id,
            base
            | {
                "kind": m.kind,
                "from_location_id": m.from_location_id,
                "to_location_id": m.to_location_id,
                "reason": m.reason,
            },
        )


def low_stock(db: Session, category_id: str | None) -> list[dict]:
    out = []
    for item in repo.all_of(db, Item, Item.name):
        if not item.active or item.reorder_level is None or (category_id and item.category_id != category_id):
            continue
        available = figures(db, item)["available"]
        if available <= item.reorder_level:
            out.append(
                {
                    "item_id": item.id,
                    "item_name": item.name,
                    "category_id": item.category_id,
                    "available": available,
                    "reorder_level": item.reorder_level,
                    "reorder_quantity": item.reorder_quantity,
                    "unit_of_measure": item.unit_of_measure,
                    "low_since": iso(item.low_since),
                }
            )
    return sorted(out, key=lambda r: (r["available"] - r["reorder_level"], r["item_name"]))


# ---------------------------------------------------------------- loans


def _visible_loan(db: Session, actor: Actor, loan: Loan, approver_items: set[str] | None = None) -> bool:
    if actor.user_id in (loan.borrower_id, loan.requested_by) or actor.can(LOAN_READ_ALL) or actor.can(LOAN_MANAGE):
        return True
    approver_items = approver_items if approver_items is not None else _approver_item_ids(db, actor)
    return any(line.item_id in approver_items for line in repo.lines_of(db, loan.id))


def _approver_item_ids(db: Session, actor: Actor) -> set[str]:
    categories = {c.id for c in repo.all_of(db, Category) if actor.user_id in (c.approver_user_ids or [])}
    return {i.id for i in repo.all_of(db, Item) if i.category_id in categories}


def _loan_for(db: Session, actor: Actor, loan_id: str) -> Loan:
    loan = repo.get(db, Loan, loan_id)
    if loan is None or not _visible_loan(db, actor, loan):
        raise _not_found("loan")
    return loan


def list_loans(db: Session, actor: Actor, q: dict, page: int, page_size: int) -> dict:
    settings = load_settings()
    loans = repo.loans(db)
    if (q.get("scope") or "mine") == "mine":
        loans = [x for x in loans if actor.user_id in (x.borrower_id, x.requested_by)]
    elif not actor.can(LOAN_READ_ALL):
        approver_items = _approver_item_ids(db, actor)
        loans = [x for x in loans if any(line.item_id in approver_items for line in repo.lines_of(db, x.id))]
    if q.get("status"):
        loans = [x for x in loans if x.status in set(q["status"])]
    if q.get("open"):
        loans = [x for x in loans if x.status in ("requested", "approved", *OUT_LOAN_STATUSES)]
    if q.get("borrower_id"):
        loans = [x for x in loans if x.borrower_id == q["borrower_id"]]
    if q.get("item_id"):
        loans = [x for x in loans if any(line.item_id == q["item_id"] for line in repo.lines_of(db, x.id))]
    if q.get("due_before"):
        loans = [x for x in loans if as_utc(x.due_at) < as_utc(q["due_before"])]
    loans.sort(key=lambda x: (x.status != "overdue", as_utc(x.due_at)))
    total = len(loans)
    chunk = loans[(page - 1) * page_size : page * page_size]
    return {
        "items": [loan_dict(db, actor, x, settings) for x in chunk],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_loan(db: Session, actor: Actor, loan_id: str) -> dict:
    return loan_dict(db, actor, _loan_for(db, actor, loan_id))


def request_loan(db: Session, actor: Actor, data: dict) -> dict:
    settings = load_settings()
    now = clock()
    manage = actor.can(LOAN_MANAGE)
    borrower = data.get("borrower_id") or actor.user_id
    if borrower != actor.user_id and not manage:
        raise _forbidden("lending to someone else needs inventory-equipment:loan:manage")
    if not manage:
        try:
            check_open_loans(len(repo.open_loans_of(db, borrower)), settings.max_open_loans_per_person)
        except RuleViolationError as v:
            raise _rule_error(v) from v
    due_at = as_utc(data["due_at"])
    needs_approval = False
    planned: list[tuple[Item, float, Unit | None]] = []
    wanted: dict[str, float] = {}
    for line in data["lines"]:
        item = repo.get_for_update(db, Item, line["item_id"])
        if item is None:
            raise _not_found("item")
        rules = _rules_for(db, item, settings)
        qty = float(line.get("quantity") or 1)
        try:
            check_loan_line(
                rules=rules,
                loanable=item.loanable,
                consumable=item.consumable,
                active=item.active,
                quantity=qty,
                roles=set(actor.roles),
                manage=manage,
            )
            check_due(due_at, now, rules.max_loan_days)
        except RuleViolationError as v:
            raise _rule_error(v) from v
        needs_approval = needs_approval or rules.requires_approval
        unit = None
        if line.get("unit_id"):
            unit = repo.get(db, Unit, line["unit_id"])
            if unit is None or unit.item_id != item.id:
                raise _not_found("unit")
            if unit.status != "available":
                raise InventoryError(409, "unit_not_available", f"unit {unit.tag} is {unit.status}", item_id=item.id)
        if item.tracking == "individual" and not unit:
            planned += [(item, 1.0, None)] * int(qty)  # one line per piece; staff pick the units at hand-out
        else:
            planned.append((item, qty, unit))
        wanted[item.id] = wanted.get(item.id, 0) + qty
    for item_id, qty in wanted.items():
        item = repo.get(db, Item, item_id)
        available = figures(db, item)["available"]
        if qty > available:
            raise _stock_error(
                StockShortageError("not_enough_stock", "not enough available right now", available, qty), item_id
            )
    status = "requested" if needs_approval and not manage else "approved"
    loan = Loan(
        organisation_id=actor.organisation_id,
        borrower_id=borrower,
        requested_by=actor.user_id,
        status=status,
        purpose=data.get("purpose"),
        due_at=due_at,
        reference=data.get("reference"),
        approved_at=now if status == "approved" else None,
    )
    db.add(loan)
    db.flush()
    for position, (item, qty, unit) in enumerate(planned):
        db.add(
            LoanLine(
                organisation_id=loan.organisation_id,
                loan_id=loan.id,
                position=position,
                item_id=item.id,
                quantity=qty,
                unit_id=unit.id if unit else None,
            )
        )
        if unit and status == "approved":
            unit.status = "reserved"
    db.flush()
    lines = repo.lines_of(db, loan.id)
    if status == "requested":
        approvers = sorted({u for c in _approval_categories(db, lines, settings) for u in (c.approver_user_ids or [])})
        _publish(
            db,
            actor,
            "loan.requested",
            loan.organisation_id,
            {
                "loan_id": loan.id,
                "borrower_id": borrower,
                "item_ids": sorted(wanted),
                "due_at": iso(due_at),
                "approver_user_ids": approvers,
            },
        )
    else:
        _publish(
            db,
            actor,
            "loan.approved",
            loan.organisation_id,
            {"loan_id": loan.id, "borrower_id": borrower, "approved_by": None, "due_at": iso(due_at)},
        )
    db.commit()
    return loan_dict(db, actor, loan, settings)


def _release_reservations(db: Session, loan: Loan) -> None:
    for line in repo.lines_of(db, loan.id):
        unit = repo.get(db, Unit, line.unit_id)
        if unit and unit.status == "reserved" and line.status == "waiting":
            unit.status = "available"


def decide_loan(db: Session, actor: Actor, loan_id: str, approve: bool, note: str | None) -> dict:
    settings = load_settings()
    loan = _loan_for(db, actor, loan_id)
    lines = repo.lines_of(db, loan.id)
    if not (actor.can(LOAN_MANAGE) or _is_approver(actor, _approval_categories(db, lines, settings))):
        raise _forbidden("only an approver of these items or a manager may decide")
    if loan.status != "requested":
        raise InventoryError(409, "not_requested", "the loan is not waiting for approval")
    loan.decided_by, loan.decision_note = actor.user_id, note
    if approve:
        for line in lines:
            unit = repo.get(db, Unit, line.unit_id)
            if unit:
                if unit.status != "available":
                    raise InventoryError(409, "unit_not_available", f"unit {unit.tag} is {unit.status}")
                unit.status = "reserved"
        loan.status, loan.approved_at = "approved", clock()
        _publish(
            db,
            actor,
            "loan.approved",
            loan.organisation_id,
            {
                "loan_id": loan.id,
                "borrower_id": loan.borrower_id,
                "approved_by": actor.user_id,
                "due_at": iso(loan.due_at),
            },
        )
    else:
        loan.status, loan.closed_at = "rejected", clock()
        _publish(
            db,
            actor,
            "loan.rejected",
            loan.organisation_id,
            {"loan_id": loan.id, "borrower_id": loan.borrower_id, "rejected_by": actor.user_id, "reason": note},
        )
    db.commit()
    return loan_dict(db, actor, loan, settings)


def _cancel(db: Session, actor: Actor | None, loan: Loan, cancelled_by: str, reason: str | None) -> None:
    _release_reservations(db, loan)
    loan.status, loan.closed_at = "cancelled", clock()
    _publish(
        db,
        actor,
        "loan.cancelled",
        loan.organisation_id,
        {"loan_id": loan.id, "borrower_id": loan.borrower_id, "cancelled_by": cancelled_by, "reason": reason},
    )


def cancel_loan(db: Session, actor: Actor, loan_id: str, reason: str | None) -> dict:
    loan = _loan_for(db, actor, loan_id)
    if loan.status not in ("requested", "approved"):
        raise InventoryError(409, "not_cancellable", "the loan was already handed out or is finished")
    if not (actor.can(LOAN_MANAGE) or actor.user_id in (loan.borrower_id, loan.requested_by)):
        raise _forbidden("only the borrower or a manager may cancel this loan")
    _cancel(db, actor, loan, actor.user_id, reason)
    db.commit()
    return loan_dict(db, actor, loan)


def hand_out(db: Session, actor: Actor, loan_id: str, data: dict) -> dict:
    now = clock()
    loan = _loan_for(db, actor, loan_id)
    if loan.status != "approved":
        raise InventoryError(409, "not_approved", "only an approved loan can be handed out")
    picks = {p["line_id"]: p for p in data["lines"]}
    lines = repo.lines_of(db, loan.id)
    missing = [line.id for line in lines if line.status == "waiting" and line.id not in picks]
    if missing:
        raise InventoryError(422, "lines_missing", "every line must be handed out", line_ids=missing)
    touched: dict[str, Item] = {}
    for line in lines:
        pick = picks.get(line.id)
        if line.status != "waiting" or pick is None:
            continue
        item = repo.get_for_update(db, Item, line.item_id)
        touched[item.id] = item
        if item.tracking == "individual":
            unit = repo.get(db, Unit, pick.get("unit_id") or line.unit_id)
            if unit is None or unit.item_id != item.id:
                raise InventoryError(422, "unit_required", "pick a unit of this item for every individual line")
            if not (unit.status == "available" or (unit.status == "reserved" and unit.id == line.unit_id)):
                raise InventoryError(409, "unit_not_available", f"unit {unit.tag} is {unit.status}", item_id=item.id)
            if line.unit_id and line.unit_id != unit.id:
                pinned = repo.get(db, Unit, line.unit_id)  # staff picked another unit; free the one reserved
                if pinned and pinned.status == "reserved":
                    pinned.status = "available"
            line.unit_id, line.from_location_id = unit.id, unit.location_id
            line.condition_out = pick.get("condition_out") or unit.condition
            unit.status, unit.current_loan_id = "on_loan", loan.id
            _record(
                db, actor, item, "loan_out", 1, unit_ids=[unit.id], from_location_id=unit.location_id, loan_id=loan.id
            )
        else:
            src = pick.get("from_location_id")
            if not src:
                raise InventoryError(422, "location_required", "pick the store each quantity line comes from")
            _get(db, Location, src, "location")
            _take_from(db, item, src, line.quantity)
            line.from_location_id, line.condition_out = src, pick.get("condition_out")
            _record(db, actor, item, "loan_out", line.quantity, from_location_id=src, loan_id=loan.id)
        line.status = "out"
    loan.status, loan.handed_out_at, loan.handed_out_by = "on_loan", now, actor.user_id
    _publish(
        db,
        actor,
        "loan.handed-out",
        loan.organisation_id,
        {
            "loan_id": loan.id,
            "borrower_id": loan.borrower_id,
            "unit_ids": [x.unit_id for x in lines if x.unit_id],
            "due_at": iso(loan.due_at),
        },
    )
    for item in touched.values():
        _refresh_low_stock(db, actor, item)
    db.commit()
    return loan_dict(db, actor, loan)


def return_lines(db: Session, actor: Actor, loan_id: str, data: dict) -> dict:
    now = clock()
    loan = _loan_for(db, actor, loan_id)
    if loan.status not in OUT_LOAN_STATUSES:
        raise InventoryError(409, "not_out", "nothing is out on this loan")
    lines = {line.id: line for line in repo.lines_of(db, loan.id)}
    returned, damaged = [], []
    touched: dict[str, Item] = {}
    for back in data["lines"]:
        line = lines.get(back["line_id"])
        if line is None or line.status != "out":
            raise InventoryError(409, "line_not_out", "this line is not out on this loan", line_id=back["line_id"])
        if back["condition_in"] == "damaged" and not back.get("damage_note"):
            raise InventoryError(422, "damage_note_required", "describe the damage")
        item = repo.get_for_update(db, Item, line.item_id)
        touched[item.id] = item
        if back.get("to_location_id"):
            _active_location(db, back["to_location_id"])
        dst = back.get("to_location_id") or line.from_location_id
        if item.tracking == "individual":
            unit = _get(db, Unit, line.unit_id, "unit")
            unit.location_id, unit.current_loan_id = dst, None
            unit.status = "in_repair" if back["condition_in"] == "damaged" else "available"
            _condition_changed(db, actor, unit, back["condition_in"], back.get("damage_note"), loan.id)
            if back["condition_in"] == "damaged":
                damaged.append(unit.id)
            _record(db, actor, item, "loan_return", 1, unit_ids=[unit.id], to_location_id=dst, loan_id=loan.id)
        else:
            _level(db, item, dst).on_hand += line.quantity
            _record(db, actor, item, "loan_return", line.quantity, to_location_id=dst, loan_id=loan.id)
        line.status, line.condition_in, line.returned_at = "returned", back["condition_in"], now
        line.damage_note = back.get("damage_note")
        returned.append(line.id)
    loan.status = loan_status([x.status for x in lines.values()], as_utc(loan.due_at), now)
    complete = loan.status in ("returned", "closed_with_loss")
    if complete:
        loan.closed_at = now
    _publish(
        db,
        actor,
        "loan.returned",
        loan.organisation_id,
        {
            "loan_id": loan.id,
            "borrower_id": loan.borrower_id,
            "returned_line_ids": returned,
            "damaged_unit_ids": damaged,
            "days_late": days_late(as_utc(loan.due_at), now),
            "complete": complete,
        },
    )
    for item in touched.values():
        _refresh_low_stock(db, actor, item)
    db.commit()
    return loan_dict(db, actor, loan)


def extend_loan(db: Session, actor: Actor, loan_id: str, due_at: datetime, reason: str | None) -> dict:
    settings = load_settings()
    now = clock()
    loan = _loan_for(db, actor, loan_id)
    if loan.status not in OUT_LOAN_STATUSES:
        raise InventoryError(409, "not_out", "only a loan that is out can be extended")
    due_at = as_utc(due_at)
    lines = repo.lines_of(db, loan.id)
    if not actor.can(LOAN_MANAGE):
        if actor.user_id != loan.borrower_id:
            raise _forbidden("only the borrower or a manager may extend this loan")
        if loan.extensions > 0 or repo.waiting_loans_for(db, {x.item_id for x in lines}, loan.id):
            raise _rule_error(
                RuleViolationError(
                    "extension_not_allowed", "already extended once, or someone is waiting for these items"
                )
            )
        limit = min(_rules_for(db, repo.get(db, Item, x.item_id), settings).max_loan_days for x in lines)
        try:
            check_due(due_at, now, limit)
        except RuleViolationError as v:
            raise _rule_error(v) from v
    elif due_at <= now:
        raise _rule_error(RuleViolationError("due_in_past", "the due date must be in the future"))
    previous = loan.due_at
    loan.due_at, loan.extensions = due_at, loan.extensions + 1
    loan.status = loan_status([x.status for x in lines], due_at, now)
    _publish(
        db,
        actor,
        "loan.extended",
        loan.organisation_id,
        {
            "loan_id": loan.id,
            "borrower_id": loan.borrower_id,
            "from_due_at": iso(previous),
            "due_at": iso(due_at),
            "extended_by": actor.user_id,
        },
    )
    db.commit()
    return loan_dict(db, actor, loan, settings)


def mark_lost(db: Session, actor: Actor, loan_id: str, line_ids: list[str], reason: str) -> dict:
    now = clock()
    loan = _loan_for(db, actor, loan_id)
    if loan.status not in OUT_LOAN_STATUSES:
        raise InventoryError(409, "not_out", "nothing is out on this loan")
    lines = {line.id: line for line in repo.lines_of(db, loan.id)}
    lost_units = []
    for line_id in line_ids:
        line = lines.get(line_id)
        if line is None or line.status != "out":
            raise InventoryError(409, "line_not_out", "this line is not out on this loan", line_id=line_id)
        item = _get(db, Item, line.item_id, "item")
        if line.unit_id:
            unit = _get(db, Unit, line.unit_id, "unit")
            unit.status, unit.current_loan_id = "missing", None
            lost_units.append(unit.id)
        _record(
            db,
            actor,
            item,
            "write_off",
            line.quantity,
            unit_ids=[line.unit_id] if line.unit_id else [],
            reason=reason,
            loan_id=loan.id,
        )
        line.status = "lost"
    loan.status = loan_status([x.status for x in lines.values()], as_utc(loan.due_at), now)
    if loan.status in ("returned", "closed_with_loss"):
        loan.closed_at = now
    _publish(
        db,
        actor,
        "loan.lost-recorded",
        loan.organisation_id,
        {
            "loan_id": loan.id,
            "borrower_id": loan.borrower_id,
            "lost_line_ids": line_ids,
            "unit_ids": lost_units,
            "reason": reason,
        },
    )
    db.commit()
    return loan_dict(db, actor, loan)


def summary(db: Session, actor: Actor) -> dict:
    now = clock()
    loans = repo.loans(db)
    units = repo.all_of(db, Unit)
    return {
        "low_stock_items": len(low_stock(db, None)),
        "loans_awaiting_approval": sum(1 for x in loans if x.status == "requested"),
        "loans_ready_for_hand_out": sum(1 for x in loans if x.status == "approved"),
        "loans_out": sum(1 for x in loans if x.status in OUT_LOAN_STATUSES),
        "loans_overdue": sum(1 for x in loans if x.status in OUT_LOAN_STATUSES and now > as_utc(x.due_at)),
        "units_in_repair": sum(1 for u in units if u.status == "in_repair"),
    }


def expiry_cutoff(settings: ModuleSettings, now: datetime) -> datetime:
    return now - timedelta(hours=settings.pickup_expiry_hours)
