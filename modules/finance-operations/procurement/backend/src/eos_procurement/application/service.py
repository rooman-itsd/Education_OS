"""Use cases of procurement. Authenticated calls arrive with the caller's organisation pinned on the session
(api/deps). Every state change writes an audit record and, where the contract defines one, publishes its procurement.*
event to the eos_core outbox in the same transaction. Preparer and approver are always different people: the
requester never decides an indent, the preparer never approves an order, the recorder never approves an invoice."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from functools import wraps

import httpx
from eos_core import events
from eos_core.db import scoped, utcnow
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import ZERO, RuleError, money, number, parse_money, parse_quantity
from ..infrastructure import budget_grants
from ..infrastructure.config import load_settings
from ..infrastructure.models import (
    AuditEntry,
    GoodsReceipt,
    Indent,
    OrderIndent,
    PurchaseOrder,
    Quote,
    Tender,
    TenderIndent,
    Vendor,
    VendorInvoice,
)
from .access import Actor
from .errors import ProcurementError, conflict, forbidden, from_rule, invalid, not_found

MODULE = "procurement"
ISSUED_EVER = ("issued", "partially_received", "received", "closed")  # orders that went to the vendor


def clock() -> datetime:
    """Now, in UTC. Tests replace it."""
    return utcnow()


# Business dates follow the Indian business calendar (decided by the owner; see #335). Asia/Kolkata has kept UTC+05:30 without daylight
# saving since 1945, so a fixed offset is exact and needs no time-zone database (tzdata is not on the approved stack).
BUSINESS_TZ = timezone(timedelta(hours=5, minutes=30), "Asia/Kolkata")


def business_date(moment: datetime) -> date:
    """The Indian calendar date of a moment; timestamps themselves stay UTC."""
    return _aware(moment).astimezone(BUSINESS_TZ).date()


def business_today() -> date:
    """Today in Asia/Kolkata: the date "in the future", "overdue" and "expired" are judged against."""
    return business_date(clock())


def _publish(db: Session, name: str, organisation_id: str, payload: dict, actor: str | None = None) -> None:
    events.publish(
        db, f"{MODULE}.{name}", organisation_id, {"organisation_id": organisation_id, **payload}, actor=actor
    )


def _audit(db: Session, actor_id: str | None, action: str, entity: str, row) -> None:
    """One audit record per state change, in the same transaction. The row is flushed first so a new one has its id."""
    db.flush()
    db.add(
        AuditEntry(
            organisation_id=row.organisation_id,
            actor=actor_id,
            action=action,
            entity=entity,
            entity_id=row.id,
            occurred_at=clock(),
        )
    )


def _rule(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except RuleError as e:
        raise from_rule(e) from e


def _q(db: Session, model):
    return scoped(db, select(model), model)


def _get(db: Session, model, row_id: str, what: str, *, lock: bool = False):
    q = _q(db, model).where(model.id == row_id)
    if lock:
        q = q.with_for_update()
    row = db.scalar(q)
    if row is None:
        raise not_found(what)
    return row


def _iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime) and value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _offset(cursor: str | None) -> int:
    try:
        value = int(cursor) if cursor else 0
    except ValueError as e:
        raise ProcurementError(400, "invalid_cursor", "invalid cursor") from e
    if value < 0:
        raise ProcurementError(400, "invalid_cursor", "invalid cursor")
    return value


def _page(rows: list, cursor: str | None, limit: int, render) -> dict:
    offset = _offset(cursor)
    chunk = rows[offset : offset + limit]
    return {
        "items": [render(r) for r in chunk],
        "next_cursor": str(offset + limit) if len(rows) > offset + limit else None,
    }


def _duplicate_is_409(code: str, message: str):
    """A write that takes a unique value (a running number, a GSTIN or PAN, a quote per vendor, a vendor's invoice
    number). When a concurrent request took the same value after the checks, the database refuses it at a flush or at
    the commit; either way the answer is 409, like the check before it, and nothing is kept."""

    def wrap(fn):
        @wraps(fn)
        def run(db: Session, *args, **kwargs):
            try:
                return fn(db, *args, **kwargs)
            except IntegrityError as e:
                db.rollback()
                raise conflict(code, message) from e

        return run

    return wrap


def _next_number(db: Session, model, prefix: str) -> str:
    """The next running number of the organisation, e.g. IND-00001. Rows are never deleted, so the count is stable.
    On Postgres a transaction-level advisory lock per organisation and table makes concurrent creates take turns,
    as maintenance does; the unique constraint still answers 409 if anything slips past."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"procurement:number:{model.__tablename__}:{db.info.get('organisation_id', '')}"},
        )
    count = db.scalar(scoped(db, select(func.count()).select_from(model), model)) or 0
    return f"{prefix}-{count + 1:05d}"


def _text(value: str | None) -> str:
    return (value or "").strip()


# ---------------------------------------------------------------- items


def _items(raw: list[dict], *, priced: bool) -> list[dict]:
    """Request items to stored items: quantities and prices as exact decimal strings."""
    out = []
    for n, item in enumerate(raw):
        field = f"items[{n}]"
        stored = {
            "description": _text(item.get("description")),
            "specification": _text(item.get("specification")),
            "quantity": str(_rule(parse_quantity, item["quantity"], f"{field}.quantity")),
            "unit": _text(item.get("unit")),
        }
        if not stored["description"] or not stored["unit"]:
            raise invalid("invalid_item", "every item needs a description and a unit", "items")
        if item.get("unit_price") is not None:
            stored["unit_price"] = str(_rule(parse_money, item["unit_price"], f"{field}.unit_price", positive=False))
        elif priced:
            raise invalid("price_required", "every item of an order needs a unit_price", "items")
        if item.get("tax_percent") is not None:
            tax = Decimal(str(item["tax_percent"]))
            if not tax.is_finite() or tax < 0 or tax > rules.MAX_TAX_PERCENT:
                raise invalid("invalid_tax_percent", "tax_percent must be between 0 and 100", f"{field}.tax_percent")
            stored["tax_percent"] = str(tax)
        out.append(stored)
    return out


def _item_out(item: dict) -> dict:
    out = {
        "description": item["description"],
        "specification": item.get("specification", ""),
        "quantity": number(Decimal(item["quantity"])),
        "unit": item["unit"],
    }
    if item.get("unit_price") is not None:
        out["unit_price"] = money(item["unit_price"])
    if item.get("tax_percent") is not None:
        out["tax_percent"] = number(Decimal(item["tax_percent"]))
    return out


# ---------------------------------------------------------------- vendors


def _vendor_names(db: Session, ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    return {v.id: v.name for v in db.scalars(_q(db, Vendor).where(Vendor.id.in_(ids)))}


def _order_stats(db: Session, vendor_ids: list[str]) -> dict[str, tuple[int, Decimal]]:
    stats: dict[str, list] = defaultdict(lambda: [0, ZERO])
    if vendor_ids:
        q = _q(db, PurchaseOrder).where(PurchaseOrder.vendor_id.in_(vendor_ids), PurchaseOrder.status.in_(ISSUED_EVER))
        for po in db.scalars(q):
            stats[po.vendor_id][0] += 1
            stats[po.vendor_id][1] += Decimal(po.total)
    return {vid: (stats[vid][0], stats[vid][1]) for vid in vendor_ids}


def vendor_dict(v: Vendor, stats: tuple[int, Decimal] = (0, ZERO)) -> dict:
    bank = None
    if v.bank_account_last4 or v.bank_ifsc:
        bank = {"account_last4": v.bank_account_last4 or "", "ifsc": v.bank_ifsc or ""}
    return {
        "id": v.id,
        "organisation_id": v.organisation_id,
        "name": v.name,
        "categories": list(v.categories or []),
        "contact_name": v.contact_name,
        "email": v.email,
        "phone": v.phone,
        "address": v.address,
        "gstin": v.gstin,
        "pan": v.pan,
        "msme_registration": v.msme_registration,
        "bank_account": bank,
        "status": v.status,
        "status_reason": v.status_reason,
        "orders_count": stats[0],
        "orders_value": money(stats[1]),
    }


def list_vendors(
    db: Session, status: str | None, category: str | None, q_text: str | None, cursor: str | None, limit: int
) -> dict:
    q = _q(db, Vendor)
    if status:
        q = q.where(Vendor.status == status)
    rows = list(db.scalars(q.order_by(Vendor.name, Vendor.id)))
    if category:
        rows = [v for v in rows if category.lower() in {c.lower() for c in v.categories or []}]
    if q_text:
        needle = q_text.lower()
        rows = [v for v in rows if needle in v.name.lower() or needle in (v.gstin or "").lower()]
    offset = _offset(cursor)
    stats = _order_stats(db, [v.id for v in rows[offset : offset + limit]])
    return _page(rows, cursor, limit, lambda v: vendor_dict(v, stats[v.id]))


def get_vendor(db: Session, vendor_id: str) -> dict:
    v = _get(db, Vendor, vendor_id, "vendor")
    return vendor_dict(v, _order_stats(db, [v.id])[v.id])


def _vendor_values(db: Session, v: Vendor, body: dict) -> None:
    gstin = _text(body.get("gstin")).upper() or None
    pan = _text(body.get("pan")).upper() or None
    for col, value in (("gstin", gstin), ("pan", pan)):
        if value is None:
            continue
        q = _q(db, Vendor).where(getattr(Vendor, col) == value)
        if v.id:
            q = q.where(Vendor.id != v.id)
        if db.scalar(q) is not None:
            raise conflict("vendor_exists", f"a vendor with this {col.upper()} exists")
    categories = sorted({_text(c) for c in body["categories"] if _text(c)})
    if not categories:
        raise invalid("invalid_categories", "a vendor needs at least one category", "categories")
    bank = body.get("bank_account")
    if bank is None:
        v.bank_account_last4 = v.bank_ifsc = None
    else:
        if bank.get("account_number"):
            v.bank_account_last4 = _rule(rules.account_last4, bank["account_number"])
        elif not v.bank_account_last4:
            raise invalid("invalid_account_number", "a new bank account needs its account_number", "bank_account")
        v.bank_ifsc = _text(bank.get("ifsc")).upper() or None
    v.name = _text(body["name"])
    v.categories = categories
    v.contact_name = _text(body.get("contact_name"))
    v.email = _text(body.get("email"))
    v.phone = _text(body.get("phone"))
    v.address = _text(body.get("address"))
    v.gstin, v.pan = gstin, pan
    v.msme_registration = _text(body.get("msme_registration")) or None
    if not v.name:
        raise invalid("invalid_name", "name is required", "name")


@_duplicate_is_409("vendor_exists", "a vendor with this GSTIN or PAN exists")
def create_vendor(db: Session, actor: Actor, body: dict) -> dict:
    v = Vendor(organisation_id=actor.organisation_id, status="pending")
    _vendor_values(db, v, body)
    db.add(v)
    _audit(db, actor.user_id, "vendor.registered", "vendor", v)
    db.commit()
    return vendor_dict(v)


@_duplicate_is_409("vendor_exists", "a vendor with this GSTIN or PAN exists")
def update_vendor(db: Session, actor: Actor, vendor_id: str, body: dict) -> dict:
    v = _get(db, Vendor, vendor_id, "vendor", lock=True)
    _vendor_values(db, v, body)
    _audit(db, actor.user_id, "vendor.updated", "vendor", v)
    db.commit()
    return get_vendor(db, v.id)


def set_vendor_status(db: Session, actor: Actor, vendor_id: str, status: str, reason: str) -> dict:
    reason = _text(reason)
    if not reason:
        raise invalid("reason_required", "a status change needs a reason", "reason")
    v = _get(db, Vendor, vendor_id, "vendor", lock=True)
    if v.status == "blacklisted":
        raise conflict("vendor_blacklisted", "a blacklisted vendor can no longer be approved or suspended")
    if v.status == status:
        raise conflict("status_unchanged", f"the vendor is already {status}")
    v.status, v.status_reason = status, reason
    if status == "blacklisted":
        _publish(db, "vendor.blacklisted", v.organisation_id, {"vendor_id": v.id, "reason": reason}, actor.user_id)
    _audit(db, actor.user_id, f"vendor.{status}", "vendor", v)
    db.commit()
    return get_vendor(db, v.id)


def _approved_vendor(db: Session, vendor_id: str, *, status: int = 422) -> Vendor:
    v = _get(db, Vendor, vendor_id, "vendor")
    if v.status != "approved":
        raise ProcurementError(status, "vendor_not_approved", f"vendor {v.name} is {v.status}, not approved")
    return v


# ---------------------------------------------------------------- indents


def _order_ids_by_indent(db: Session, indent_ids: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    if indent_ids:
        for link in db.scalars(_q(db, OrderIndent).where(OrderIndent.indent_id.in_(indent_ids))):
            out[link.indent_id].append(link.purchase_order_id)
    return out


def indent_dict(i: Indent, order_ids: list[str] | None = None) -> dict:
    return {
        "id": i.id,
        "organisation_id": i.organisation_id,
        "number": i.number,
        "title": i.title,
        "justification": i.justification,
        "department_id": i.department_id,
        "line_id": i.line_id,
        "items": [_item_out(x) for x in i.items or []],
        "estimated_cost": money(i.estimated_cost),
        "needed_by": _iso(i.needed_by),
        "document_ids": list(i.document_ids or []),
        "status": i.status,
        "purchase_method": i.purchase_method,
        "requested_by": i.requested_by,
        "requested_by_name": "",  # identity names are not available to modules yet
        "decided_by": i.decided_by,
        "note": i.note,
        "purchase_order_ids": sorted(order_ids or []),
        "created_at": _iso(i.created_at),
    }


def _indent_dicts(db: Session, rows: list[Indent]) -> list[dict]:
    orders = _order_ids_by_indent(db, [i.id for i in rows])
    return [indent_dict(i, orders[i.id]) for i in rows]


def list_indents(db: Session, status: str | None, department_id: str | None, cursor: str | None, limit: int) -> dict:
    q = _q(db, Indent)
    if status:
        q = q.where(Indent.status == status)
    if department_id:
        q = q.where(Indent.department_id == department_id)
    rows = list(db.scalars(q.order_by(Indent.created_at.desc(), Indent.number.desc())))
    offset = _offset(cursor)
    orders = _order_ids_by_indent(db, [i.id for i in rows[offset : offset + limit]])
    return _page(rows, cursor, limit, lambda i: indent_dict(i, orders[i.id]))


def my_indents(db: Session, actor: Actor) -> list[dict]:
    q = _q(db, Indent).where(Indent.requested_by == actor.user_id)
    return _indent_dicts(db, list(db.scalars(q.order_by(Indent.created_at.desc(), Indent.number.desc()))))


def _readable_indent(db: Session, actor: Actor, indent_id: str, approve_permission: str) -> Indent:
    i = _get(db, Indent, indent_id, "indent")
    if not actor.can(approve_permission) and i.requested_by != actor.user_id:
        raise forbidden("you can see only your own indents")
    return i


def get_indent(db: Session, actor: Actor, indent_id: str, approve_permission: str) -> dict:
    i = _readable_indent(db, actor, indent_id, approve_permission)
    return _indent_dicts(db, [i])[0]


def _indent_values(i: Indent, body: dict) -> None:
    i.title = _text(body["title"])
    if not i.title:
        raise invalid("invalid_title", "title is required", "title")
    i.justification = _text(body.get("justification"))
    i.department_id = body.get("department_id")
    i.line_id = body["line_id"]
    i.items = _items(body["items"], priced=False)
    i.estimated_cost = _rule(parse_money, body["estimated_cost"], "estimated_cost")
    i.needed_by = body.get("needed_by")
    i.document_ids = [d for d in body.get("document_ids") or [] if d]


@_duplicate_is_409("number_taken", "another request took the same number; try again")
def create_indent(db: Session, actor: Actor, body: dict) -> dict:
    i = Indent(
        organisation_id=actor.organisation_id,
        number=_next_number(db, Indent, "IND"),
        status="draft",
        requested_by=actor.user_id,
    )
    _indent_values(i, body)
    db.add(i)
    _audit(db, actor.user_id, "indent.created", "indent", i)
    db.commit()
    return indent_dict(i)


def _own_editable_indent(db: Session, actor: Actor, indent_id: str) -> Indent:
    i = _get(db, Indent, indent_id, "indent", lock=True)
    if i.requested_by != actor.user_id:
        raise forbidden("you can change only your own indents")
    if i.status not in rules.EDITABLE:
        raise conflict("not_editable", "the indent is not a draft or returned")
    return i


def update_indent(db: Session, actor: Actor, indent_id: str, body: dict) -> dict:
    i = _own_editable_indent(db, actor, indent_id)
    _indent_values(i, body)
    _audit(db, actor.user_id, "indent.updated", "indent", i)
    db.commit()
    return indent_dict(i)


def submit_indent(db: Session, actor: Actor, indent_id: str) -> dict:
    i = _own_editable_indent(db, actor, indent_id)
    i.status, i.decided_by, i.note = "submitted", None, None
    _publish(
        db,
        "indent.submitted",
        i.organisation_id,
        {
            "indent_id": i.id,
            "number": i.number,
            "requested_by": i.requested_by,
            "department_id": i.department_id,
            "estimated_cost": money(i.estimated_cost),
        },
        actor.user_id,
    )
    _audit(db, actor.user_id, "indent.submitted", "indent", i)
    db.commit()
    return indent_dict(i)


def _unavailable(message: str) -> ProcurementError:
    return ProcurementError(503, "budget_check_unavailable", message)


def _availability(actor: Actor, line_id: str, amount: Decimal) -> tuple[Decimal, bool]:
    """budget-grants GET /availability with the caller's token: (available, sufficient). Nothing is reserved (#221)."""
    try:
        r = budget_grants.availability(load_settings().budget_grants_url, actor.token, line_id, money(amount))
    except budget_grants.BudgetGrantsNotConfiguredError as e:
        raise _unavailable(str(e)) from e
    except httpx.HTTPError as e:
        raise _unavailable("budget-grants could not be reached") from e
    if r.status == 404:
        raise invalid("insufficient_budget", "the line is not in an approved budget or active grant", "line_id")
    if r.status != 200:
        raise _unavailable(f"budget-grants refused the availability check ({r.status})")
    try:
        available = parse_money(r.body["available"], "available", positive=False)
        sufficient = r.body["sufficient"]
    except (KeyError, RuleError) as e:
        raise _unavailable("budget-grants gave an unreadable availability answer") from e
    if not isinstance(sufficient, bool):
        raise _unavailable("budget-grants gave an unreadable availability answer")
    return available, sufficient


def _check_budget(actor: Actor, line_id: str, amount: Decimal) -> None:
    """Indent approval: the line can cover the estimated cost."""
    available, sufficient = _availability(actor, line_id, amount)
    if not sufficient:
        raise invalid(
            "insufficient_budget", f"the line has {money(available)} available, less than {money(amount)}", "line_id"
        )


def _lock_line(db: Session, organisation_id: str, line_id: str) -> None:
    """Serialise purchase order approvals on one line until the transaction ends, so two approvals never spend the same
    balance. A transaction-level advisory lock on Postgres; SQLite (tests, local) has a single writer anyway."""
    if db.get_bind().dialect.name != "postgresql":
        return
    digest = hashlib.sha256(f"procurement.line:{organisation_id}:{line_id}".encode()).digest()
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": int.from_bytes(digest[:8], "big", signed=True)})


def _check_order_budget(db: Session, actor: Actor, po: PurchaseOrder) -> None:
    """The order total is covered by its line (decided by the owner; see #335). budget-grants records a commitment only when it receives
    procurement.purchase-order.issued, which may not have arrived yet, so the orders this organisation issued on the line
    that budget-grants has no commitment for are taken off what it reports as available. Runs under _lock_line."""
    total = Decimal(po.total)
    available, _ = _availability(actor, po.line_id, total)
    try:
        recorded = budget_grants.procurement_commitments(load_settings().budget_grants_url, actor.token, po.line_id)
    except budget_grants.BudgetGrantsRefusedError as e:
        raise _unavailable(f"budget-grants refused the commitments listing ({e.status})") from e
    except httpx.HTTPError as e:
        raise _unavailable("budget-grants could not be reached") from e
    q = _q(db, PurchaseOrder).where(
        PurchaseOrder.line_id == po.line_id, PurchaseOrder.status.in_(ISSUED_EVER), PurchaseOrder.id != po.id
    )
    pending = sum((Decimal(o.total) for o in db.scalars(q) if o.id not in recorded), ZERO)
    left = available - pending
    if total > left:
        held = f" ({money(pending)} of it held by issued orders budget-grants has not recorded yet)" if pending else ""
        raise invalid(
            "insufficient_budget",
            f"the line has {money(available)} available{held}, so {money(left)} is left, less than the order total "
            f"{money(total)}",
            "line_id",
        )


def decide_indent(db: Session, actor: Actor, indent_id: str, decision: str, note: str | None) -> dict:
    i = _get(db, Indent, indent_id, "indent")
    if i.status != "submitted":
        raise conflict("not_submitted", "the indent is not submitted")
    if i.requested_by == actor.user_id:
        raise forbidden("you cannot decide an indent you raised")
    method = None
    if decision == "approved":
        settings = load_settings()
        method = _rule(
            rules.purchase_method, Decimal(i.estimated_cost), settings.direct_purchase_limit, settings.quotation_limit
        )
        _check_budget(actor, i.line_id, Decimal(i.estimated_cost))  # before the row lock: an HTTP call
    db.rollback()
    i = _get(db, Indent, indent_id, "indent", lock=True)
    if i.status != "submitted":
        raise conflict("not_submitted", "the indent is not submitted")
    i.status, i.decided_by, i.note = decision, actor.user_id, _text(note) or None
    if decision == "approved":
        i.purchase_method = method
        _publish(
            db,
            "indent.approved",
            i.organisation_id,
            {
                "indent_id": i.id,
                "number": i.number,
                "requested_by": i.requested_by,
                "line_id": i.line_id,
                "estimated_cost": money(i.estimated_cost),
                "purchase_method": method,
            },
            actor.user_id,
        )
    elif decision == "rejected":
        _publish(
            db,
            "indent.rejected",
            i.organisation_id,
            {"indent_id": i.id, "number": i.number, "requested_by": i.requested_by, "note": i.note or ""},
            actor.user_id,
        )
    _audit(db, actor.user_id, f"indent.{decision}", "indent", i)
    db.commit()
    return _indent_dicts(db, [i])[0]


def _indent_in_use(
    db: Session, indent_id: str, *, except_order: str | None = None, except_tender: str | None = None
) -> bool:
    """An indent belongs to at most one open tender or order: a tender that can still lead to an award, or an order
    that is not cancelled. An awarded tender's indents are held by the order the award drafted. The contract has no
    way to cancel a tender, so one that can no longer be awarded (a draft past its closing date, or a tender that
    closed without a quote) lets its indents go."""
    tq = (
        select(Tender)
        .join(TenderIndent, TenderIndent.tender_id == Tender.id)
        .where(TenderIndent.indent_id == indent_id, Tender.status.in_(("draft", "published")))
    )
    for t in db.scalars(scoped(db, tq, Tender)):
        if t.id != except_tender and _tender_can_be_awarded(db, t):
            return True
    oq = (
        select(OrderIndent.id)
        .join(PurchaseOrder, PurchaseOrder.id == OrderIndent.purchase_order_id)
        .where(OrderIndent.indent_id == indent_id, PurchaseOrder.status != "cancelled")
    )
    if except_order:
        oq = oq.where(PurchaseOrder.id != except_order)
    return db.scalar(scoped(db, oq, OrderIndent)) is not None


def _usable_indents(db: Session, indent_ids: list[str], **excepts) -> list[Indent]:
    """Approved indents on one line, none already held by another open tender or order. The indents are locked, in a
    fixed order, so two requests for the same indent take turns and the second sees the first one's tender or order."""
    ids = sorted(set(indent_ids))
    indents = [_get(db, Indent, x, "indent", lock=True) for x in ids]
    for i in indents:
        if i.status != "approved":
            raise conflict("indent_not_approved", f"indent {i.number} is {i.status}, not approved")
        if _indent_in_use(db, i.id, **excepts):
            raise conflict("indent_in_use", f"indent {i.number} already belongs to an open tender or order")
    if len({i.line_id for i in indents}) > 1:
        raise invalid("lines_differ", "indents combined into one tender or order must share one line", "indent_ids")
    return indents


def _set_indent_status(
    db: Session, actor_id: str | None, indent_ids: list[str], status: str, action: str | None = None
) -> None:
    for indent_id in indent_ids:
        i = db.scalar(_q(db, Indent).where(Indent.id == indent_id))
        if i is not None and i.status != status:
            i.status = status
            _audit(db, actor_id, action or f"indent.{status}", "indent", i)


# ---------------------------------------------------------------- tenders


def _tender_can_be_awarded(db: Session, t: Tender) -> bool:
    """A draft that can still be published, a tender open for quotes, or a closed one with a quote that can still be
    awarded (unexpired, priced, from a vendor still approved)."""
    if t.status not in ("draft", "published"):
        return False
    if _aware(t.closes_at) > clock():
        return True
    return t.status == "published" and any(_awardable(db, q) for q in _quotes(db, t.id))


def _priced(quote: Quote) -> bool:
    items = quote.items or []
    return bool(items) and all(x.get("unit_price") is not None for x in items)


def _awardable(db: Session, quote: Quote) -> bool:
    """Whether an award of this quote could succeed: not expired, priced items, and its vendor still approved."""
    if _expired(quote) or not _priced(quote):
        return False
    vendor = db.scalar(_q(db, Vendor).where(Vendor.id == quote.vendor_id))
    return vendor is not None and vendor.status == "approved"


def _tender_status(t: Tender) -> str:
    """A published tender is closed for quotes once closes_at has passed."""
    if t.status == "published" and _aware(t.closes_at) <= clock():
        return "closed"
    return t.status


def _tender_indent_ids(db: Session, tender_id: str) -> list[str]:
    return sorted(x.indent_id for x in db.scalars(_q(db, TenderIndent).where(TenderIndent.tender_id == tender_id)))


def _quotes(db: Session, tender_id: str) -> list[Quote]:
    rows = list(db.scalars(_q(db, Quote).where(Quote.tender_id == tender_id)))
    return sorted(rows, key=lambda x: (Decimal(x.total), _aware(x.created_at), x.id))


def _expired(quote: Quote) -> bool:
    """A quote is valid through its valid_until date (IST) and expired from the next day (decided by the owner; see #335)."""
    return quote.valid_until is not None and quote.valid_until < business_today()


def tender_dict(db: Session, t: Tender) -> dict:
    quotes = _quotes(db, t.id)
    names = _vendor_names(db, {x.vendor_id for x in quotes})
    return {
        "id": t.id,
        "organisation_id": t.organisation_id,
        "number": t.number,
        "title": t.title,
        "indent_ids": _tender_indent_ids(db, t.id),
        "method": t.method,
        "invited_vendor_ids": list(t.invited_vendor_ids or []),
        "category": t.category,
        "closes_at": _iso(_aware(t.closes_at)),
        "terms": t.terms,
        "document_ids": list(t.document_ids or []),
        "status": _tender_status(t),
        "line_id": t.line_id,
        "quotes": [
            {
                "id": x.id,
                "vendor_id": x.vendor_id,
                "vendor_name": names.get(x.vendor_id, ""),
                "rank": n,
                "items": [_item_out(it) for it in x.items or []],
                "total": money(x.total),
                "delivery_days": x.delivery_days,
                "valid_until": _iso(x.valid_until),
                "document_id": x.document_id,
            }
            for n, x in enumerate(quotes, start=1)
        ],
        "awarded_quote_id": t.awarded_quote_id,
        "award_justification": t.award_justification,
    }


def list_tenders(db: Session, status: str | None) -> list[dict]:
    rows = list(db.scalars(_q(db, Tender).order_by(Tender.created_at.desc(), Tender.number.desc())))
    if status:
        rows = [t for t in rows if _tender_status(t) == status]
    return [tender_dict(db, t) for t in rows]


def get_tender(db: Session, tender_id: str) -> dict:
    return tender_dict(db, _get(db, Tender, tender_id, "tender"))


@_duplicate_is_409("number_taken", "another request took the same number; try again")
def create_tender(db: Session, actor: Actor, body: dict) -> dict:
    indents = _usable_indents(db, body["indent_ids"])
    settings = load_settings()
    total = sum((Decimal(i.estimated_cost) for i in indents), ZERO)
    required = _rule(rules.purchase_method, total, settings.direct_purchase_limit, settings.quotation_limit)
    for i in indents:
        if rules.PURCHASE_METHODS.index(i.purchase_method or "direct") > rules.PURCHASE_METHODS.index(required):
            required = i.purchase_method
    if not rules.method_allows(body["method"], required):
        raise invalid("method_too_loose", f"these indents need a {required}, not a {body['method']}", "method")
    invited = list(dict.fromkeys(body.get("invited_vendor_ids") or []))
    for vendor_id in invited:
        _approved_vendor(db, vendor_id)
    category = _text(body.get("category"))
    if not invited and not category:
        raise invalid("category_required", "without invited vendors the tender needs a category", "category")
    closes_at = _aware(body["closes_at"])
    if closes_at <= clock():
        raise invalid("invalid_closes_at", "closes_at must be in the future", "closes_at")
    t = Tender(
        organisation_id=actor.organisation_id,
        number=_next_number(db, Tender, "RFQ" if body["method"] == "quotation" else "TDR"),
        title=_text(body["title"]),
        method=body["method"],
        line_id=indents[0].line_id,
        category=category,
        invited_vendor_ids=invited,
        closes_at=closes_at,
        terms=_text(body.get("terms")),
        document_ids=[d for d in body.get("document_ids") or [] if d],
        status="draft",
        created_by=actor.user_id,
    )
    if not t.title:
        raise invalid("invalid_title", "title is required", "title")
    db.add(t)
    db.flush()
    for i in indents:
        db.add(TenderIndent(organisation_id=actor.organisation_id, tender_id=t.id, indent_id=i.id))
    _audit(db, actor.user_id, "tender.created", "tender", t)
    db.commit()
    return tender_dict(db, t)


def _category_vendors(db: Session, category: str) -> list[Vendor]:
    rows = db.scalars(_q(db, Vendor).where(Vendor.status == "approved"))
    return [v for v in rows if category.lower() in {c.lower() for c in v.categories or []}]


def publish_tender(db: Session, actor: Actor, tender_id: str) -> dict:
    t = _get(db, Tender, tender_id, "tender", lock=True)
    if t.status != "draft":
        raise conflict("not_draft", "only a draft tender is published")
    if _aware(t.closes_at) <= clock():
        raise invalid(
            "invalid_closes_at", "closes_at has passed; edit is not possible, create a new tender", "closes_at"
        )
    if t.invited_vendor_ids:
        for vendor_id in t.invited_vendor_ids:
            _approved_vendor(db, vendor_id)
    elif not _category_vendors(db, t.category):
        raise invalid("no_vendors", f"no approved vendor in category {t.category}", "category")
    t.status = "published"
    _publish(
        db,
        "tender.published",
        t.organisation_id,
        {
            "tender_id": t.id,
            "number": t.number,
            "method": t.method,
            "category": t.category,
            "closes_at": _iso(_aware(t.closes_at)),
        },
        actor.user_id,
    )
    _audit(db, actor.user_id, "tender.published", "tender", t)
    db.commit()
    return tender_dict(db, t)


@_duplicate_is_409("quote_exists", "a quote from this vendor is already recorded")
def record_quote(db: Session, actor: Actor, tender_id: str, body: dict) -> dict:
    t = _get(db, Tender, tender_id, "tender", lock=True)
    if _tender_status(t) != "published":
        raise conflict("tender_closed", "quotes are recorded only while the tender is published and open")
    v = _approved_vendor(db, body["vendor_id"], status=409)
    if t.invited_vendor_ids:
        if v.id not in t.invited_vendor_ids:
            raise conflict("vendor_not_invited", f"vendor {v.name} was not invited")
    elif t.category.lower() not in {c.lower() for c in v.categories or []}:
        raise conflict("vendor_not_invited", f"vendor {v.name} is not in category {t.category}")
    if db.scalar(_q(db, Quote).where(Quote.tender_id == t.id, Quote.vendor_id == v.id)) is not None:
        raise conflict("quote_exists", f"a quote from {v.name} is already recorded")
    items = _items(body["items"], priced=True)
    if not items:
        raise invalid("price_required", "a quote lists its priced items", "items")
    total = _rule(parse_money, body["total"], "total")
    computed = _rule(rules.order_totals, items)[2]
    if total != computed:
        raise invalid(
            "quote_total_mismatch",
            f"total {money(total)} differs from the items' total including tax, {money(computed)}",
            "total",
        )
    q = Quote(
        organisation_id=t.organisation_id,
        tender_id=t.id,
        vendor_id=v.id,
        items=items,
        total=total,
        delivery_days=body.get("delivery_days"),
        valid_until=body.get("valid_until"),
        document_id=body.get("document_id"),
        recorded_by=actor.user_id,
    )
    db.add(q)
    _audit(db, actor.user_id, "quote.recorded", "quote", q)
    db.commit()
    return tender_dict(db, t)


@_duplicate_is_409("number_taken", "another request took the same number; try again")
def award_tender(db: Session, actor: Actor, tender_id: str, quote_id: str, justification: str | None) -> dict:
    t = _get(db, Tender, tender_id, "tender", lock=True)
    status = _tender_status(t)
    if status != "closed":
        raise conflict("not_closed", f"a tender is awarded after it closes; it is {status}")
    quotes = _quotes(db, t.id)
    quote = next((x for x in quotes if x.id == quote_id), None)
    if quote is None:
        raise not_found("quote of this tender")
    if _expired(quote):
        raise conflict("quote_expired", f"the quote was valid until {_iso(quote.valid_until)}")
    vendor = _approved_vendor(db, quote.vendor_id, status=409)
    if not _priced(quote):
        raise invalid("price_required", "the awarded quote needs priced items to draft the order", "quote_id")
    lowest = min(Decimal(x.total) for x in quotes if _awardable(db, x))
    justification = _text(justification)
    if Decimal(quote.total) > lowest and not justification:
        raise invalid(
            "justification_required", "awarding other than the lowest quote needs a justification", "justification"
        )
    items = quote.items
    subtotal, tax_total, total = _rule(rules.order_totals, items)
    po = PurchaseOrder(
        organisation_id=t.organisation_id,
        number=_next_number(db, PurchaseOrder, "PO"),
        vendor_id=vendor.id,
        tender_id=t.id,
        line_id=t.line_id,
        items=items,
        delivery_by=business_today() + timedelta(days=quote.delivery_days or 0),
        delivery_address="",
        terms=t.terms,
        status="draft",
        subtotal=subtotal,
        tax_total=tax_total,
        total=total,
        prepared_by=actor.user_id,
    )
    db.add(po)
    db.flush()
    for indent_id in _tender_indent_ids(db, t.id):
        db.add(OrderIndent(organisation_id=t.organisation_id, purchase_order_id=po.id, indent_id=indent_id))
    t.status, t.awarded_quote_id, t.award_justification = "awarded", quote.id, justification or None
    _publish(
        db,
        "tender.awarded",
        t.organisation_id,
        {"tender_id": t.id, "vendor_id": vendor.id, "quote_id": quote.id, "total": money(quote.total)},
        actor.user_id,
    )
    _audit(db, actor.user_id, "tender.awarded", "tender", t)
    _audit(db, actor.user_id, "purchase_order.created", "purchase_order", po)
    db.commit()
    return po_dict(db, po)


# ---------------------------------------------------------------- purchase orders


def _accepted(db: Session, po_id: str) -> dict[int, Decimal]:
    """Accepted quantity per item index, over all receipts of an order."""
    out: dict[int, Decimal] = defaultdict(lambda: Decimal(0))
    for gr in db.scalars(_q(db, GoodsReceipt).where(GoodsReceipt.purchase_order_id == po_id)):
        for x in gr.items or []:
            out[int(x["item_index"])] += Decimal(x["accepted"])
    return dict(out)


def _invoices_of(db: Session, po_id: str) -> list[VendorInvoice]:
    return list(db.scalars(_q(db, VendorInvoice).where(VendorInvoice.purchase_order_id == po_id)))


def _overdue(po: PurchaseOrder) -> bool:
    return po.status in rules.OPEN_ORDER_STATUSES and business_today() > po.delivery_by


def po_dict(db: Session, po: PurchaseOrder) -> dict:
    invoices = _invoices_of(db, po.id)
    links = db.scalars(_q(db, OrderIndent).where(OrderIndent.purchase_order_id == po.id))
    return {
        "id": po.id,
        "organisation_id": po.organisation_id,
        "number": po.number,
        "status": po.status,
        "vendor_id": po.vendor_id,
        "vendor_name": _vendor_names(db, {po.vendor_id}).get(po.vendor_id, ""),
        "indent_ids": sorted(x.indent_id for x in links),
        "tender_id": po.tender_id,
        "line_id": po.line_id,
        "items": [_item_out(x) for x in po.items or []],
        "delivery_by": _iso(po.delivery_by),
        "delivery_address": po.delivery_address,
        "terms": po.terms,
        "subtotal": money(po.subtotal),
        "tax_total": money(po.tax_total),
        "total": money(po.total),
        "invoiced_total": money(sum((Decimal(x.amount) for x in invoices if x.status != "rejected"), ZERO)),
        "paid_total": money(sum((Decimal(x.amount) for x in invoices if x.status == "paid"), ZERO)),
        "overdue": _overdue(po),
        "document_id": po.document_id,  # the order PDF waits for the documents SDK
        "prepared_by": po.prepared_by,
        "approved_by": po.approved_by,
        "issued_at": _iso(po.issued_at),
    }


def list_orders(db: Session, status: str | None, vendor_id: str | None, cursor: str | None, limit: int) -> dict:
    q = _q(db, PurchaseOrder)
    if status:
        q = q.where(PurchaseOrder.status == status)
    if vendor_id:
        q = q.where(PurchaseOrder.vendor_id == vendor_id)
    rows = list(db.scalars(q.order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.number.desc())))
    return _page(rows, cursor, limit, lambda po: po_dict(db, po))


def get_order(db: Session, po_id: str) -> dict:
    return po_dict(db, _get(db, PurchaseOrder, po_id, "purchase order"))


def _delivery_date(day: date) -> date:
    """An order is not due before today (IST): a date in the past would make it overdue the moment it is issued."""
    if day < business_today():
        raise invalid("invalid_date", "delivery_by cannot be before today", "delivery_by")
    return day


def _order_values(db: Session, po: PurchaseOrder, body: dict) -> list[Indent]:
    if body.get("tender_id"):
        raise invalid("awarded_order", "an order for a tender is drafted by awarding the tender", "tender_id")
    indents = _usable_indents(db, body["indent_ids"], except_order=po.id)
    for i in indents:
        if i.purchase_method != "direct":
            raise invalid("tender_required", f"indent {i.number} needs a {i.purchase_method}", "indent_ids")
    vendor = _approved_vendor(db, body["vendor_id"])
    items = _items(body["items"], priced=True)
    po.subtotal, po.tax_total, po.total = _rule(rules.order_totals, items)
    settings = load_settings()
    estimate = sum((Decimal(i.estimated_cost) for i in indents), ZERO)
    needed = _rule(
        rules.purchase_method,
        max(estimate, Decimal(po.total)),
        settings.direct_purchase_limit,
        settings.quotation_limit,
    )
    if needed != "direct":
        raise invalid(
            "tender_required",
            f"the indents together ({money(estimate)}) or the order total ({money(po.total)}) are above the direct "
            f"purchase limit; buy through a {needed}",
            "indent_ids",
        )
    po.vendor_id, po.line_id, po.items = vendor.id, indents[0].line_id, items
    po.delivery_by = _delivery_date(body["delivery_by"])
    po.delivery_address = _text(body.get("delivery_address"))
    po.terms = _text(body.get("terms"))
    return indents


def _link_indents(db: Session, po: PurchaseOrder, indent_ids: list[str]) -> None:
    for link in db.scalars(_q(db, OrderIndent).where(OrderIndent.purchase_order_id == po.id)):
        db.delete(link)  # a draft's links, replaced with the edited ones
    db.flush()
    for indent_id in dict.fromkeys(indent_ids):
        db.add(OrderIndent(organisation_id=po.organisation_id, purchase_order_id=po.id, indent_id=indent_id))


@_duplicate_is_409("number_taken", "another request took the same number; try again")
def create_order(db: Session, actor: Actor, body: dict) -> dict:
    po = PurchaseOrder(
        organisation_id=actor.organisation_id,
        number=_next_number(db, PurchaseOrder, "PO"),
        status="draft",
        prepared_by=actor.user_id,
    )
    indents = _order_values(db, po, body)
    db.add(po)
    db.flush()
    _link_indents(db, po, [i.id for i in indents])
    _audit(db, actor.user_id, "purchase_order.created", "purchase_order", po)
    db.commit()
    return po_dict(db, po)


def _editable_order(db: Session, po_id: str) -> PurchaseOrder:
    po = _get(db, PurchaseOrder, po_id, "purchase order", lock=True)
    if po.status not in rules.EDITABLE:
        raise conflict("not_editable", "the order is not a draft or returned")
    return po


def update_order(db: Session, actor: Actor, po_id: str, body: dict) -> dict:
    po = _editable_order(db, po_id)
    if po.tender_id:
        # An awarded order keeps its tender, vendor, indents and the awarded quote's items and prices: the award was
        # decided on them. Only the delivery date, address and terms change.
        if body.get("tender_id") not in (None, po.tender_id) or body["vendor_id"] != po.vendor_id:
            raise invalid("awarded_order", "an awarded order keeps its tender and vendor", "vendor_id")
        current = {x.indent_id for x in db.scalars(_q(db, OrderIndent).where(OrderIndent.purchase_order_id == po.id))}
        if set(body["indent_ids"]) != current:
            raise invalid("awarded_order", "an awarded order keeps the tender's indents", "indent_ids")
        if _items(body["items"], priced=True) != po.items:
            raise invalid("awarded_order", "an awarded order keeps the awarded quote's items and prices", "items")
        _approved_vendor(db, po.vendor_id)
        po.delivery_by = _delivery_date(body["delivery_by"])
        po.delivery_address, po.terms = _text(body.get("delivery_address")), _text(body.get("terms"))
    else:
        indents = _order_values(db, po, body)
        _link_indents(db, po, [i.id for i in indents])
    po.prepared_by = actor.user_id  # whoever edits an order prepares it, and cannot approve it
    _audit(db, actor.user_id, "purchase_order.updated", "purchase_order", po)
    db.commit()
    return po_dict(db, po)


def submit_order(db: Session, actor: Actor, po_id: str) -> dict:
    po = _editable_order(db, po_id)
    _delivery_date(po.delivery_by)  # a draft left until after its delivery date is corrected before it is sent
    po.status, po.prepared_by, po.submitted_at = "submitted", actor.user_id, clock()
    _audit(db, actor.user_id, "purchase_order.submitted", "purchase_order", po)
    db.commit()
    return po_dict(db, po)


PREPARING_ACTIONS = ("purchase_order.created", "purchase_order.updated", "purchase_order.submitted")


def _prepared_order(db: Session, po: PurchaseOrder, user_id: str) -> bool:
    """Whether this user created, edited or submitted the order at any point (the audit trail), not only last:
    whoever submits becomes prepared_by, which must not let an earlier preparer approve."""
    q = _q(db, AuditEntry).where(
        AuditEntry.entity == "purchase_order",
        AuditEntry.entity_id == po.id,
        AuditEntry.actor == user_id,
        AuditEntry.action.in_(PREPARING_ACTIONS),
    )
    return db.scalar(q) is not None


def decide_order(db: Session, actor: Actor, po_id: str, decision: str, note: str | None) -> dict:
    if decision not in ("approved", "returned"):
        raise invalid("invalid_decision", "an order is approved or returned", "decision")
    po = _get(db, PurchaseOrder, po_id, "purchase order", lock=True)
    if po.status != "submitted":
        raise conflict("not_submitted", "the order is not submitted")
    if po.prepared_by == actor.user_id or _prepared_order(db, po, actor.user_id):
        raise forbidden("you cannot approve an order you prepared")
    po.decision_note = _text(note) or None
    indent_ids = [x.indent_id for x in db.scalars(_q(db, OrderIndent).where(OrderIndent.purchase_order_id == po.id))]
    if decision == "returned":
        po.status = "returned"
    else:
        _approved_vendor(db, po.vendor_id, status=409)
        _lock_line(db, po.organisation_id, po.line_id)
        try:
            _check_order_budget(db, actor, po)
        except ProcurementError:
            db.rollback()  # the order stays submitted, nothing is published, and the line lock is released
            raise
        po.status, po.approved_by, po.issued_at = "issued", actor.user_id, clock()
        _set_indent_status(db, actor.user_id, indent_ids, "ordered")
        _publish(
            db,
            "purchase-order.issued",
            po.organisation_id,
            {
                "purchase_order_id": po.id,
                "number": po.number,
                "vendor_id": po.vendor_id,
                "line_id": po.line_id,
                "total": money(po.total),
                "delivery_by": _iso(po.delivery_by),
                "document_id": po.document_id or "",
            },
            actor.user_id,
        )
    _audit(db, actor.user_id, f"purchase_order.{po.status}", "purchase_order", po)
    db.commit()
    return po_dict(db, po)


def cancel_order(db: Session, actor: Actor, po_id: str, reason: str) -> dict:
    reason = _text(reason)
    if not reason:
        raise invalid("reason_required", "cancelling needs a reason", "reason")
    po = _get(db, PurchaseOrder, po_id, "purchase order", lock=True)
    if po.status in rules.EDITABLE:
        # Never issued: nothing was committed in budget-grants, so no event; its indents can be ordered again.
        po.status, po.cancel_reason = "cancelled", reason
        _audit(db, actor.user_id, "purchase_order.cancelled", "purchase_order", po)
        db.commit()
        return po_dict(db, po)
    if po.status not in rules.OPEN_ORDER_STATUSES:
        raise conflict(
            "not_cancellable",
            f"a draft, returned or issued undelivered order is cancelled; this one is {po.status}",
        )
    accepted = _accepted(db, po.id)
    delivered = rules.accepted_value(po.items, accepted)
    indent_ids = [x.indent_id for x in db.scalars(_q(db, OrderIndent).where(OrderIndent.purchase_order_id == po.id))]
    if any(q > 0 for q in accepted.values()):
        po.status = "closed"  # the undelivered remainder is closed
        _set_indent_status(db, actor.user_id, indent_ids, "closed")
    else:
        po.status = "cancelled"  # nothing received: the indents can be ordered again
        _set_indent_status(db, actor.user_id, indent_ids, "approved", "indent.reopened")
    po.cancel_reason = reason
    released = max(Decimal(po.total) - delivered, ZERO)
    _publish(
        db,
        "purchase-order.cancelled",
        po.organisation_id,
        {"purchase_order_id": po.id, "line_id": po.line_id, "released_amount": money(released), "reason": reason},
        actor.user_id,
    )
    _audit(db, actor.user_id, f"purchase_order.{po.status}", "purchase_order", po)
    db.commit()
    return po_dict(db, po)


# ---------------------------------------------------------------- goods receipts


def receipt_dict(gr: GoodsReceipt) -> dict:
    return {
        "id": gr.id,
        "organisation_id": gr.organisation_id,
        "number": gr.number,
        "purchase_order_id": gr.purchase_order_id,
        "received_on": _iso(gr.received_on),
        "delivery_note": gr.delivery_note,
        "items": [
            {
                "item_index": x["item_index"],
                "received": number(Decimal(x["received"])),
                "accepted": number(Decimal(x["accepted"])),
                **({"rejection_reason": x["rejection_reason"]} if x.get("rejection_reason") else {}),
            }
            for x in gr.items or []
        ],
        "document_id": gr.document_id,
        "recorded_by": gr.recorded_by,
    }


def list_receipts(db: Session, po_id: str) -> list[dict]:
    po = _get(db, PurchaseOrder, po_id, "purchase order")
    q = _q(db, GoodsReceipt).where(GoodsReceipt.purchase_order_id == po.id)
    return [receipt_dict(x) for x in db.scalars(q.order_by(GoodsReceipt.received_on, GoodsReceipt.number))]


@_duplicate_is_409("number_taken", "another request took the same number; try again")
def record_receipt(db: Session, actor: Actor, po_id: str, body: dict) -> dict:
    po = _get(db, PurchaseOrder, po_id, "purchase order", lock=True)
    if po.status not in rules.OPEN_ORDER_STATUSES:
        raise conflict("order_not_open", f"goods are received against an issued order; it is {po.status}")
    if body["received_on"] > business_today():
        raise invalid("invalid_date", "received_on cannot be in the future", "received_on")
    if po.issued_at is not None and body["received_on"] < business_date(po.issued_at):
        raise invalid("invalid_date", "received_on cannot be before the order was issued", "received_on")
    accepted_so_far = _accepted(db, po.id)
    seen: set[int] = set()
    lines = []
    for x in body["items"]:
        n = x["item_index"]
        if n in seen or not 0 <= n < len(po.items):
            raise invalid("invalid_item", f"item_index {n} is not an item of the order or appears twice", "items")
        seen.add(n)
        received = _rule(parse_quantity, x["received"], "received", positive=False)
        accepted = _rule(parse_quantity, x["accepted"], "accepted", positive=False)
        if accepted > received:
            raise invalid("invalid_quantity", "accepted cannot exceed received", "items")
        outstanding = Decimal(po.items[n]["quantity"]) - accepted_so_far.get(n, Decimal(0))
        if received > outstanding:
            raise invalid(
                "quantity_exceeds_outstanding",
                f"item {n} has {number(outstanding)} outstanding, less than {number(received)} received",
                "items",
            )
        if accepted < received and not _text(x.get("rejection_reason")):
            raise invalid("rejection_reason_required", "rejected quantities need a rejection_reason", "items")
        lines.append(
            {
                "item_index": n,
                "received": str(received),
                "accepted": str(accepted),
                "rejection_reason": _text(x.get("rejection_reason")),
            }
        )
    if not any(Decimal(x["received"]) > 0 for x in lines):
        raise invalid("invalid_quantity", "a receipt records something received", "items")
    gr = GoodsReceipt(
        organisation_id=po.organisation_id,
        number=_next_number(db, GoodsReceipt, "GRN"),
        purchase_order_id=po.id,
        received_on=body["received_on"],
        delivery_note=_text(body.get("delivery_note")),
        items=lines,
        document_id=body.get("document_id"),
        recorded_by=actor.user_id,
    )
    db.add(gr)
    db.flush()
    accepted_now = _accepted(db, po.id)
    if all(accepted_now.get(n, Decimal(0)) >= Decimal(item["quantity"]) for n, item in enumerate(po.items)):
        po.status = "received"
        links = db.scalars(_q(db, OrderIndent).where(OrderIndent.purchase_order_id == po.id))
        _set_indent_status(db, actor.user_id, [x.indent_id for x in links], "closed")
    elif any(q > 0 for q in accepted_now.values()):
        po.status = "partially_received"
    _publish(
        db,
        "goods-receipt.recorded",
        po.organisation_id,
        {
            "goods_receipt_id": gr.id,
            "purchase_order_id": po.id,
            "vendor_id": po.vendor_id,
            "received_on": _iso(gr.received_on),
            "items": [
                {
                    "item_index": x["item_index"],
                    "description": po.items[x["item_index"]]["description"],
                    "unit": po.items[x["item_index"]]["unit"],
                    "received": number(Decimal(x["received"])),
                    "accepted": number(Decimal(x["accepted"])),
                }
                for x in lines
            ],
        },
        actor.user_id,
    )
    _audit(db, actor.user_id, "goods_receipt.recorded", "goods_receipt", gr)
    _audit(db, actor.user_id, f"purchase_order.{po.status}", "purchase_order", po)
    db.commit()
    return receipt_dict(gr)


# ---------------------------------------------------------------- vendor invoices


def _match(db: Session, inv: VendorInvoice, po: PurchaseOrder) -> dict:
    accepted = rules.accepted_value(po.items, _accepted(db, po.id))
    previously = sum(
        (Decimal(x.amount) for x in _invoices_of(db, po.id) if x.id != inv.id and x.status != "rejected"), ZERO
    )
    tolerance = load_settings().invoice_match_tolerance_percent
    return {
        "ordered": money(po.total),
        "accepted_value": money(accepted),
        "previously_invoiced": money(previously),
        "within_tolerance": rules.within_tolerance(previously + Decimal(inv.amount), accepted, tolerance),
    }


def invoice_dict(db: Session, inv: VendorInvoice, po: PurchaseOrder | None = None) -> dict:
    po = po or _get(db, PurchaseOrder, inv.purchase_order_id, "purchase order")
    return {
        "id": inv.id,
        "organisation_id": inv.organisation_id,
        "purchase_order_id": inv.purchase_order_id,
        "invoice_number": inv.invoice_number,
        "invoice_date": _iso(inv.invoice_date),
        "amount": money(inv.amount),
        "tax_amount": money(inv.tax_amount),
        "document_id": inv.document_id,
        "vendor_id": inv.vendor_id,
        "vendor_name": _vendor_names(db, {inv.vendor_id}).get(inv.vendor_id, ""),
        "status": inv.status,
        "match": _match(db, inv, po),
        "recorded_by": inv.recorded_by,
        "approved_by": inv.approved_by,
        "paid_on": _iso(inv.paid_on),
        "payment_reference": inv.payment_reference,
        "tds_deducted": money(inv.tds_deducted),
    }


def list_invoices(db: Session, status: str | None, vendor_id: str | None, cursor: str | None, limit: int) -> dict:
    q = _q(db, VendorInvoice)
    if status:
        q = q.where(VendorInvoice.status == status)
    if vendor_id:
        q = q.where(VendorInvoice.vendor_id == vendor_id)
    rows = list(db.scalars(q.order_by(VendorInvoice.created_at.desc(), VendorInvoice.invoice_number)))
    return _page(rows, cursor, limit, lambda inv: invoice_dict(db, inv))


def get_invoice(db: Session, invoice_id: str) -> dict:
    return invoice_dict(db, _get(db, VendorInvoice, invoice_id, "vendor invoice"))


@_duplicate_is_409("invoice_exists", "this invoice number of the vendor is already recorded")
def record_invoice(db: Session, actor: Actor, body: dict) -> dict:
    po = _get(db, PurchaseOrder, body["purchase_order_id"], "purchase order")
    if po.status not in rules.INVOICEABLE_ORDER_STATUSES:
        raise conflict("order_not_issued", f"invoices are recorded against an issued order; it is {po.status}")
    number_ = _text(body["invoice_number"])
    if not number_:
        raise invalid("invalid_invoice_number", "invoice_number is required", "invoice_number")
    q = _q(db, VendorInvoice).where(VendorInvoice.vendor_id == po.vendor_id, VendorInvoice.invoice_number == number_)
    if db.scalar(q) is not None:
        raise conflict("invoice_exists", f"invoice {number_} of this vendor is already recorded")
    if body["invoice_date"] > business_today():
        raise invalid("invalid_date", "invoice_date cannot be in the future", "invoice_date")
    amount = _rule(parse_money, body["amount"], "amount")
    tax = _rule(parse_money, body.get("tax_amount") or "0", "tax_amount", positive=False)
    if tax > amount:
        raise invalid("invalid_amount", "tax_amount cannot exceed amount", "tax_amount")
    inv = VendorInvoice(
        organisation_id=po.organisation_id,
        purchase_order_id=po.id,
        vendor_id=po.vendor_id,
        invoice_number=number_,
        invoice_date=body["invoice_date"],
        amount=amount,
        tax_amount=tax,
        document_id=body.get("document_id"),
        status="recorded",
        recorded_by=actor.user_id,
        tds_deducted=ZERO,
    )
    db.add(inv)
    _audit(db, actor.user_id, "vendor_invoice.recorded", "vendor_invoice", inv)
    db.commit()
    return invoice_dict(db, inv, po)


def decide_invoice(db: Session, actor: Actor, invoice_id: str, decision: str, note: str | None) -> dict:
    if decision not in ("approved", "rejected"):
        raise invalid("invalid_decision", "an invoice is approved for payment or rejected", "decision")
    inv = _get(db, VendorInvoice, invoice_id, "vendor invoice", lock=True)
    if inv.status != "recorded":
        raise conflict("not_recorded", f"the invoice is {inv.status}")
    if inv.recorded_by == actor.user_id:
        raise forbidden("you cannot decide an invoice you recorded")
    note = _text(note) or None
    po = _get(db, PurchaseOrder, inv.purchase_order_id, "purchase order")
    if decision == "approved":
        if not _match(db, inv, po)["within_tolerance"] and not note:
            raise invalid(
                "invoice_mismatch",
                "the invoice exceeds the accepted value of the order; approve with a note to override",
                "decision",
            )
        inv.approved_by = actor.user_id
        _publish(
            db,
            "vendor-invoice.approved",
            inv.organisation_id,
            {
                "vendor_invoice_id": inv.id,
                "purchase_order_id": po.id,
                "vendor_id": inv.vendor_id,
                "amount": money(inv.amount),
            },
            actor.user_id,
        )
    inv.status, inv.decision_note = decision, note
    _audit(db, actor.user_id, f"vendor_invoice.{decision}", "vendor_invoice", inv)
    db.commit()
    return invoice_dict(db, inv, po)


def mark_paid(db: Session, actor: Actor, invoice_id: str, body: dict) -> dict:
    inv = _get(db, VendorInvoice, invoice_id, "vendor invoice", lock=True)
    if inv.status != "approved":
        raise conflict("not_approved", f"the invoice is {inv.status}, not approved")
    paid_on = body["paid_on"]
    if paid_on > business_today() or paid_on < inv.invoice_date:
        raise invalid("invalid_date", "paid_on must be between the invoice date and today", "paid_on")
    reference = _text(body["payment_reference"])
    if not reference:
        raise invalid("invalid_reference", "payment_reference is required", "payment_reference")
    tds = _rule(parse_money, body.get("tds_deducted") or "0", "tds_deducted", positive=False)
    if tds > Decimal(inv.amount):
        raise invalid("invalid_amount", "tds_deducted cannot exceed the invoice amount", "tds_deducted")
    po = _get(db, PurchaseOrder, inv.purchase_order_id, "purchase order")
    inv.status, inv.paid_on, inv.payment_reference, inv.tds_deducted = "paid", paid_on, reference, tds
    _publish(
        db,
        "vendor-invoice.paid",
        inv.organisation_id,
        {
            "vendor_invoice_id": inv.id,
            "purchase_order_id": po.id,
            "vendor_id": inv.vendor_id,
            "line_id": po.line_id,
            "amount": money(inv.amount),
            "paid_on": _iso(paid_on),
        },
        actor.user_id,
    )
    _audit(db, actor.user_id, "vendor_invoice.paid", "vendor_invoice", inv)
    db.commit()
    return invoice_dict(db, inv, po)
