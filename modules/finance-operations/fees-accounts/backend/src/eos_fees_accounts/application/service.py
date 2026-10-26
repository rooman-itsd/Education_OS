"""Use cases of fees-accounts. Authenticated calls arrive with the caller's organisation pinned on the session (api/deps);
event handlers and jobs run inside organisation_scope for the event's organisation. Every state change publishes its
fees-accounts.* event to the eos_core outbox in the same transaction, which is the audit trail until the audit SDK
exists."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from eos_core import events
from eos_core.db import scoped, utcnow
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import ZERO, RuleError, money, parse_money
from ..infrastructure import payment_adapter
from ..infrastructure.config import load_settings
from ..infrastructure.models import (
    AuditEntry,
    BulkJob,
    CollectionTarget,
    Concession,
    FeeHead,
    FeeSettings,
    FeeStructure,
    Invoice,
    InvoiceLine,
    NumberSequence,
    Payment,
    Receipt,
    Refund,
)
from . import access as perm
from .access import Actor
from .errors import FeesError, conflict, forbidden, from_rule, invalid, not_found

MODULE = "fees-accounts"


def clock() -> datetime:
    """Now, in UTC. Tests replace it."""
    return utcnow()


def today() -> date:
    return clock().date()


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
        from datetime import UTC

        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _page(rows: list, limit: int, offset: int) -> str | None:
    return str(offset + limit) if len(rows) > limit else None


def _offset(cursor: str | None) -> int:
    try:
        value = int(cursor) if cursor else 0
    except ValueError as e:
        raise FeesError(400, "invalid_cursor", "invalid cursor") from e
    if value < 0:
        raise FeesError(400, "invalid_cursor", "invalid cursor")
    return value


def _next_number(db: Session, organisation_id: str, kind: str, prefix: str) -> str:
    """Organisation-wide sequential numbers, never reused: the counter row is locked until commit."""
    seq = db.scalar(_q(db, NumberSequence).where(NumberSequence.kind == kind).with_for_update())
    if seq is None:
        seq = NumberSequence(organisation_id=organisation_id, kind=kind, last_value=0)
        db.add(seq)
    seq.last_value += 1
    db.flush()
    return f"{prefix}-{seq.last_value:06d}"


# ---------------------------------------------------------------- serialisers


def head_dict(h: FeeHead) -> dict:
    return {
        "id": h.id,
        "organisation_id": h.organisation_id,
        "code": h.code,
        "name": h.name,
        "category": h.category,
        "refundable": h.refundable,
        "active": h.active,
    }


def structure_dict(s: FeeStructure) -> dict:
    return {
        "id": s.id,
        "organisation_id": s.organisation_id,
        "name": s.name,
        "academic_year": s.academic_year,
        "programme_id": s.programme_id,
        "applies_to": s.applies_to,
        "category": s.category,
        "room_type": s.room_type,
        "route_id": s.route_id,
        "items": [{"fee_head_id": i["fee_head_id"], "amount": i["amount"]} for i in s.items],
        "instalments": [
            {"label": i["label"], "percent": float(Decimal(i["percent"])), "due_date": i["due_date"]}
            for i in s.instalments
        ],
        "allow_part_payment": s.allow_part_payment,
        "late_fee": s.late_fee,
        "status": s.status,
        "total": money(s.total),
        "published_at": _iso(s.published_at),
    }


def balance_of(inv: Invoice) -> Decimal:
    return rules.balance(
        Decimal(inv.total), Decimal(inv.late_fee), Decimal(inv.concession_total), Decimal(inv.paid_total)
    )


def payment_dict(p: Payment) -> dict:
    return {
        "id": p.id,
        "organisation_id": p.organisation_id,
        "invoice_id": p.invoice_id,
        "person_id": p.person_id,
        "amount": money(p.amount),
        "refunded_amount": money(p.refunded_amount),
        "mode": p.mode,
        "status": p.status,
        "gateway_reference": p.gateway_reference,
        "instrument_number": p.instrument_number,
        "paid_on": _iso(p.paid_on),
        "receipt_id": p.receipt_id,
        "recorded_by": p.recorded_by,
        "created_at": _iso(p.created_at),
    }


def receipt_dict(r: Receipt) -> dict:
    return {
        "id": r.id,
        "organisation_id": r.organisation_id,
        "number": r.number,
        "payment_id": r.payment_id,
        "invoice_id": r.invoice_id,
        "person_id": r.person_id,
        "amount": money(r.amount),
        "status": r.status,
        "document_id": r.document_id,
        "issued_at": _iso(r.issued_at),
    }


def refund_dict(r: Refund) -> dict:
    return {
        "id": r.id,
        "payment_id": r.payment_id,
        "amount": money(r.amount),
        "status": r.status,
        "reason": r.reason,
        "created_at": _iso(r.created_at),
    }


def concession_dict(c: Concession) -> dict:
    return {
        "id": c.id,
        "organisation_id": c.organisation_id,
        "invoice_id": c.invoice_id,
        "person_id": c.person_id,
        "kind": c.kind,
        "amount": money(c.amount),
        "percent": None if c.percent is None else float(c.percent),
        "reason": c.reason,
        "document_id": c.document_id,
        "status": c.status,
        "approved_amount": money(c.approved_amount),
        "requested_by": c.requested_by,
        "decided_by": c.decided_by,
        "decided_at": _iso(c.decided_at),
    }


def invoice_dicts(db: Session, invoices: list[Invoice]) -> list[dict]:
    """Invoices with their lines, payments and concessions, loaded in three queries for the whole page."""
    ids = [i.id for i in invoices]
    lines: dict[str, list] = {i: [] for i in ids}
    pays: dict[str, list] = {i: [] for i in ids}
    cons: dict[str, list] = {i: [] for i in ids}
    if ids:
        for line in db.scalars(
            _q(db, InvoiceLine).where(InvoiceLine.invoice_id.in_(ids)).order_by(InvoiceLine.position)
        ):
            lines[line.invoice_id].append(line)
        for p in db.scalars(_q(db, Payment).where(Payment.invoice_id.in_(ids)).order_by(Payment.created_at)):
            pays[p.invoice_id].append(payment_dict(p))
        for c in db.scalars(_q(db, Concession).where(Concession.invoice_id.in_(ids)).order_by(Concession.created_at)):
            cons[c.invoice_id].append(concession_dict(c))
    now = today()
    out = []
    for inv in invoices:
        bal = balance_of(inv)
        out.append(
            {
                "id": inv.id,
                "organisation_id": inv.organisation_id,
                "number": inv.number,
                "person_id": inv.person_id,
                "person_name": inv.person_name,
                "fee_structure_id": inv.fee_structure_id,
                "instalment": inv.instalment,
                "academic_year": inv.academic_year,
                "lines": [
                    {
                        "fee_head_id": line.fee_head_id,
                        "fee_head_name": line.fee_head_name,
                        "description": line.description,
                        "amount": money(line.amount),
                    }
                    for line in lines[inv.id]
                ],
                "total": money(inv.total),
                "concession_total": money(inv.concession_total),
                "late_fee": money(inv.late_fee),
                "paid_total": money(inv.paid_total),
                "balance": money(max(bal, ZERO)),
                "credit": money(max(-bal, ZERO)),
                "status": inv.status,
                "overdue": rules.is_overdue(inv.status, bal, inv.due_date, now),
                "due_date": _iso(inv.due_date),
                "allow_part_payment": inv.allow_part_payment,
                "source": {"module": inv.source_module, "reference": inv.source_reference}
                if inv.source_module
                else None,
                "issued_at": _iso(inv.issued_at),
                "payments": pays[inv.id],
                "concessions": cons[inv.id],
            }
        )
    return out


def invoice_dict(db: Session, inv: Invoice) -> dict:
    return invoice_dicts(db, [inv])[0]


# ---------------------------------------------------------------- fee heads


def list_fee_heads(db: Session, active: bool | None) -> list[dict]:
    q = _q(db, FeeHead).order_by(FeeHead.code)
    if active is not None:
        q = q.where(FeeHead.active.is_(active))
    return [head_dict(h) for h in db.scalars(q)]


def _code_taken(db: Session, code: str, except_id: str | None = None) -> bool:
    q = _q(db, FeeHead).where(FeeHead.code == code)
    if except_id:
        q = q.where(FeeHead.id != except_id)
    return db.scalar(q) is not None


def create_fee_head(db: Session, actor: Actor, body: dict) -> dict:
    if _code_taken(db, body["code"]):
        raise conflict("code_taken", f"fee head code {body['code']} is already used")
    h = FeeHead(organisation_id=actor.organisation_id, **body)
    db.add(h)
    _audit(db, actor.user_id, "fee_head.created", "fee_head", h)
    db.commit()
    return head_dict(h)


def update_fee_head(db: Session, actor: Actor, head_id: str, body: dict) -> dict:
    h = _get(db, FeeHead, head_id, "fee head")
    if _code_taken(db, body["code"], except_id=h.id):
        raise conflict("code_taken", f"fee head code {body['code']} is already used")
    for key, value in body.items():
        setattr(h, key, value)
    _audit(db, actor.user_id, "fee_head.updated", "fee_head", h)
    db.commit()
    return head_dict(h)


# ---------------------------------------------------------------- fee structures


def _structure_values(db: Session, body: dict) -> dict:
    heads = {h.id: h for h in db.scalars(_q(db, FeeHead))}
    items = []
    for i, item in enumerate(body["items"]):
        head = heads.get(item["fee_head_id"])
        if head is None or not head.active:
            raise invalid("unknown_fee_head", "every item needs an active fee head of your organisation", f"items[{i}]")
        items.append(
            {"fee_head_id": head.id, "amount": money(_rule(parse_money, item["amount"], f"items[{i}].amount"))}
        )
    instalments = [
        rules.Instalment(i["label"], Decimal(str(i["percent"])), date.fromisoformat(str(i["due_date"])))
        for i in body["instalments"]
    ]
    _rule(rules.check_instalments, instalments)
    late = body.get("late_fee")
    if late:
        if late.get("kind") not in rules.LATE_FEE_KINDS or late.get("amount") is None:
            raise invalid("invalid_late_fee", "late_fee needs kind flat or per_day and an amount", "late_fee")
        late = {
            "kind": late["kind"],
            "amount": money(_rule(parse_money, late["amount"], "late_fee.amount")),
            "grace_days": int(late.get("grace_days") or 0),
            "cap": money(_rule(parse_money, late["cap"], "late_fee.cap")) if late.get("cap") is not None else None,
        }
    return {
        "name": body["name"],
        "academic_year": body["academic_year"],
        "programme_id": body.get("programme_id"),
        "applies_to": body.get("applies_to") or "student",
        "category": body.get("category"),
        "room_type": body.get("room_type"),
        "route_id": body.get("route_id"),
        "items": items,
        "instalments": [
            {"label": i.label, "percent": str(i.percent), "due_date": i.due_date.isoformat()} for i in instalments
        ],
        "allow_part_payment": bool(body.get("allow_part_payment", False)),
        "late_fee": late or None,
        "total": sum((Decimal(i["amount"]) for i in items), ZERO),
    }


def list_structures(db: Session, academic_year: str | None, programme_id: str | None, status: str | None) -> list[dict]:
    q = _q(db, FeeStructure).order_by(FeeStructure.created_at.desc())
    if academic_year:
        q = q.where(FeeStructure.academic_year == academic_year)
    if programme_id:
        q = q.where(FeeStructure.programme_id == programme_id)
    if status:
        q = q.where(FeeStructure.status == status)
    return [structure_dict(s) for s in db.scalars(q)]


def get_structure(db: Session, structure_id: str) -> dict:
    return structure_dict(_get(db, FeeStructure, structure_id, "fee structure"))


def create_structure(db: Session, actor: Actor, body: dict) -> dict:
    s = FeeStructure(organisation_id=actor.organisation_id, status="draft", **_structure_values(db, body))
    db.add(s)
    _audit(db, actor.user_id, "fee_structure.created", "fee_structure", s)
    db.commit()
    return structure_dict(s)


def update_structure(db: Session, actor: Actor, structure_id: str, body: dict) -> dict:
    s = _get(db, FeeStructure, structure_id, "fee structure", lock=True)
    if s.status != "draft":
        raise conflict("not_draft", "only a draft can be edited; archive it and create a new one")
    for key, value in _structure_values(db, body).items():
        setattr(s, key, value)
    _audit(db, actor.user_id, "fee_structure.updated", "fee_structure", s)
    db.commit()
    return structure_dict(s)


def publish_structure(db: Session, actor: Actor, structure_id: str) -> dict:
    s = _get(db, FeeStructure, structure_id, "fee structure", lock=True)
    if s.status != "draft":
        raise conflict("not_draft", "only a draft can be published")
    s.status, s.published_at = "published", clock()
    _publish(
        db,
        "fee-structure.published",
        s.organisation_id,
        {
            "fee_structure_id": s.id,
            "academic_year": s.academic_year,
            "programme_id": s.programme_id,
            "applies_to": s.applies_to,
            "total": money(s.total),
        },
        actor.user_id,
    )
    _audit(db, actor.user_id, "fee_structure.published", "fee_structure", s)
    db.commit()
    return structure_dict(s)


def archive_structure(db: Session, actor: Actor, structure_id: str) -> dict:
    s = _get(db, FeeStructure, structure_id, "fee structure", lock=True)
    if s.status == "archived":
        raise conflict("already_archived", "the structure is already archived")
    s.status = "archived"
    _audit(db, actor.user_id, "fee_structure.archived", "fee_structure", s)
    db.commit()
    return structure_dict(s)


# ---------------------------------------------------------------- invoices


def _structure_lines(db: Session, s: FeeStructure, instalment: int) -> tuple[list[tuple[str, Decimal]], dict]:
    items = [(i["fee_head_id"], Decimal(i["amount"])) for i in s.items]
    percents = [Decimal(i["percent"]) for i in s.instalments]
    lines = _rule(rules.instalment_lines, items, percents, instalment)
    return lines, s.instalments[instalment - 1]


def issue_invoice(
    db: Session,
    organisation_id: str,
    *,
    person_id: str,
    lines: list[tuple[str, str, Decimal]],
    due_date: date,
    title: str,
    actor_id: str | None,
    structure: FeeStructure | None = None,
    instalment: int | None = None,
    source: dict | None = None,
    active_heads_only: bool = False,
) -> Invoice:
    """Create an invoice with its lines and publish fees-accounts.invoice.issued, in the caller's transaction.
    `lines` are (fee_head_id, description, amount); the fee heads must belong to the organisation, and to an
    active head when a user picks them (`active_heads_only`)."""
    heads = {h.id: h for h in db.scalars(_q(db, FeeHead).where(FeeHead.id.in_([line[0] for line in lines])))}
    for i, (head_id, _, amount) in enumerate(lines):
        if head_id not in heads or (active_heads_only and not heads[head_id].active):
            raise invalid("unknown_fee_head", "every line needs an active fee head of your organisation", f"lines[{i}]")
        if amount <= 0:
            raise invalid("invalid_amount", "line amounts must be greater than zero", f"lines[{i}].amount")
    if not lines:
        raise invalid("no_lines", "an invoice needs at least one line with an amount", "lines")
    settings = load_settings()
    inv = Invoice(
        organisation_id=organisation_id,
        number=_next_number(db, organisation_id, "invoice", settings.invoice_number_prefix),
        person_id=person_id,
        fee_structure_id=structure.id if structure else None,
        instalment=instalment,
        academic_year=structure.academic_year if structure else None,
        title=title[:300],
        total=sum((line[2] for line in lines), ZERO),
        concession_total=ZERO,
        late_fee=ZERO,
        paid_total=ZERO,
        status="issued",
        due_date=due_date,
        allow_part_payment=structure.allow_part_payment if structure else False,
        late_fee_rule=structure.late_fee if structure else None,
        source_module=(source or {}).get("module"),
        source_reference=(source or {}).get("reference"),
        issued_at=clock(),
        issued_by=actor_id,
    )
    db.add(inv)
    db.flush()
    for position, (head_id, description, amount) in enumerate(lines, start=1):
        db.add(
            InvoiceLine(
                organisation_id=organisation_id,
                invoice_id=inv.id,
                position=position,
                fee_head_id=head_id,
                fee_head_name=heads[head_id].name,
                description=description or heads[head_id].name,
                amount=amount,
            )
        )
    _publish(
        db,
        "invoice.issued",
        organisation_id,
        {
            "invoice_id": inv.id,
            "number": inv.number,
            "person_id": person_id,
            "total": money(inv.total),
            "due_date": due_date.isoformat(),
            "source_module": inv.source_module,
            "source_reference": inv.source_reference,
        },
        actor_id,
    )
    _audit(db, actor_id, "invoice.issued", "invoice", inv)
    db.flush()
    return inv


def _live_instalment_invoice(db: Session, person_id: str, structure_id: str, instalment: int) -> Invoice | None:
    return db.scalar(
        _q(db, Invoice).where(
            Invoice.person_id == person_id,
            Invoice.fee_structure_id == structure_id,
            Invoice.instalment == instalment,
            Invoice.status != "cancelled",
        )
    )


def invoice_from_structure(
    db: Session,
    organisation_id: str,
    structure: FeeStructure,
    instalment: int,
    person_id: str,
    actor_id: str | None,
    source: dict | None = None,
) -> Invoice:
    if structure.status != "published":
        raise conflict("not_published", "invoices are raised only from a published structure")
    if _live_instalment_invoice(db, person_id, structure.id, instalment):
        raise conflict("already_invoiced", "an invoice for this person, structure and instalment already exists")
    lines, inst = _structure_lines(db, structure, instalment)
    return issue_invoice(
        db,
        organisation_id,
        person_id=person_id,
        lines=[(head, "", amount) for head, amount in lines],
        due_date=date.fromisoformat(inst["due_date"]),
        title=f"{structure.name}: {inst['label']}",
        actor_id=actor_id,
        structure=structure,
        instalment=instalment,
        source=source,
    )


def create_invoice(db: Session, actor: Actor, body: dict) -> dict:
    source = body.get("source")
    if body.get("fee_structure_id"):
        if not body.get("instalment") or body.get("lines"):
            raise invalid("invalid_invoice", "give fee_structure_id with instalment, or lines", "instalment")
        s = _get(db, FeeStructure, body["fee_structure_id"], "fee structure")
        inv = invoice_from_structure(
            db, actor.organisation_id, s, body["instalment"], body["person_id"], actor.user_id, source
        )
    else:
        if not body.get("lines") or not body.get("due_date"):
            raise invalid("invalid_invoice", "ad hoc invoices need lines and a due_date", "lines")
        lines = [
            (
                line["fee_head_id"],
                line.get("description") or "",
                _rule(parse_money, line["amount"], f"lines[{i}].amount"),
            )
            for i, line in enumerate(body["lines"])
        ]
        first = lines[0][1]
        inv = issue_invoice(
            db,
            actor.organisation_id,
            person_id=body["person_id"],
            lines=lines,
            due_date=body["due_date"],
            title=first or "Invoice",
            actor_id=actor.user_id,
            source=source,
            active_heads_only=True,
        )
        if not first:
            inv.title = db.scalar(_q(db, InvoiceLine).where(InvoiceLine.invoice_id == inv.id)).fee_head_name
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise conflict("already_invoiced", "an invoice for this person, structure and instalment already exists") from e
    return invoice_dict(db, inv)


def bulk_invoices(db: Session, actor: Actor, body: dict) -> dict:
    settings = load_settings()
    people = list(dict.fromkeys(body["person_ids"]))
    if len(people) > settings.bulk_invoice_max:
        raise invalid("too_many_people", f"at most {settings.bulk_invoice_max} people per request", "person_ids")
    s = _get(db, FeeStructure, body["fee_structure_id"], "fee structure")
    if s.status != "published":
        raise conflict("not_published", "invoices are raised only from a published structure")
    _rule(rules.instalment_lines, [], [Decimal(i["percent"]) for i in s.instalments], body["instalment"])
    job = BulkJob(
        organisation_id=actor.organisation_id,
        fee_structure_id=s.id,
        instalment=body["instalment"],
        status="running",
        requested=len(people),
        requested_by=actor.user_id,
    )
    db.add(job)
    _audit(db, actor.user_id, "bulk_job.started", "bulk_job", job)
    db.commit()
    created = skipped = 0
    errors = []
    for person_id in people:
        try:
            invoice_from_structure(db, actor.organisation_id, s, body["instalment"], person_id, actor.user_id)
            db.commit()
            created += 1
        except FeesError as e:
            db.rollback()
            if e.code == "already_invoiced":
                skipped += 1
            else:
                errors.append({"person_id": person_id, "message": e.message})
        except IntegrityError:
            db.rollback()  # a concurrent request raised the same instalment first
            skipped += 1
    job = _get(db, BulkJob, job.id, "bulk job")
    job.created, job.skipped, job.errors, job.status = created, skipped, errors, "completed"
    _audit(db, actor.user_id, "bulk_job.completed", "bulk_job", job)
    db.commit()
    return bulk_dict(job)


def bulk_dict(job: BulkJob) -> dict:
    return {
        "id": job.id,
        "status": job.status,
        "requested": job.requested,
        "created": job.created,
        "skipped": job.skipped,
        "errors": list(job.errors or []),
    }


def get_bulk(db: Session, job_id: str) -> dict:
    return bulk_dict(_get(db, BulkJob, job_id, "bulk job"))


def list_invoices(db: Session, filters: dict, cursor: str | None, limit: int) -> dict:
    offset = _offset(cursor)
    q = _q(db, Invoice)
    for key in ("person_id", "status", "fee_structure_id"):
        if filters.get(key):
            q = q.where(getattr(Invoice, key) == filters[key])
    if filters.get("due_from"):
        q = q.where(Invoice.due_date >= filters["due_from"])
    if filters.get("due_to"):
        q = q.where(Invoice.due_date <= filters["due_to"])
    rows = list(db.scalars(q.order_by(Invoice.due_date, Invoice.number)))
    if filters.get("overdue") is not None:
        now = today()
        rows = [i for i in rows if rules.is_overdue(i.status, balance_of(i), i.due_date, now) == filters["overdue"]]
    page = rows[offset : offset + limit + 1]
    return {"items": invoice_dicts(db, page[:limit]), "next_cursor": _page(page, limit, offset)}


def get_invoice(db: Session, actor: Actor, invoice_id: str) -> dict:
    inv = _get(db, Invoice, invoice_id, "invoice")
    if not actor.can(perm.INVOICE_READ) and inv.person_id != actor.user_id:
        raise not_found("invoice")
    return invoice_dict(db, inv)


def cancel_invoice(db: Session, actor: Actor | None, invoice_id: str, reason: str) -> dict:
    inv = _get(db, Invoice, invoice_id, "invoice", lock=True)
    _cancel(db, inv, reason, actor.user_id if actor else None)
    db.commit()
    return invoice_dict(db, inv)


def _cancel(db: Session, inv: Invoice, reason: str, actor_id: str | None) -> None:
    if inv.status == "cancelled":
        raise conflict("already_cancelled", "the invoice is already cancelled")
    live = db.scalar(
        _q(db, Payment)
        .where(Payment.invoice_id == inv.id, Payment.status.in_(("completed", "partially_refunded")))
        .with_only_columns(func.count())
    )
    if live:
        raise conflict("has_payments", "the invoice has payments; refund or void them first")
    inv.status, inv.cancelled_at, inv.cancel_reason = "cancelled", clock(), reason
    _publish(
        db,
        "invoice.cancelled",
        inv.organisation_id,
        {"invoice_id": inv.id, "person_id": inv.person_id, "reason": reason},
        actor_id,
    )
    _audit(db, actor_id, "invoice.cancelled", "invoice", inv)


# ---------------------------------------------------------------- payments and receipts


def _refresh(db: Session, inv: Invoice, actor_id: str | None) -> None:
    """Follow the balance after a money change; publish invoice.paid when it first reaches zero."""
    was_paid = inv.status == "paid"
    inv.status = rules.invoice_status(inv.status, balance_of(inv), Decimal(inv.paid_total))
    if inv.status == "paid" and not was_paid:
        inv.paid_at = clock()
        _publish(
            db,
            "invoice.paid",
            inv.organisation_id,
            {
                "invoice_id": inv.id,
                "person_id": inv.person_id,
                "total": money(inv.total),
                "paid_at": _iso(inv.paid_at),
                "source_module": inv.source_module,
                "source_reference": inv.source_reference,
            },
            actor_id,
        )
    elif inv.status != "paid":
        inv.paid_at = None


def apply_payment(
    db: Session,
    inv: Invoice,
    *,
    amount: Decimal,
    mode: str,
    paid_on: date,
    actor_id: str | None,
    gateway_reference: str | None = None,
    instrument_number: str | None = None,
    bank_name: str | None = None,
    note: str | None = None,
) -> Payment:
    """Record a payment against a locked invoice, issue its receipt and publish payment.received (and invoice.paid)."""
    settings = load_settings()
    p = Payment(
        organisation_id=inv.organisation_id,
        invoice_id=inv.id,
        person_id=inv.person_id,
        amount=amount,
        refunded_amount=ZERO,
        mode=mode,
        status="completed",
        gateway_reference=gateway_reference,
        instrument_number=instrument_number,
        bank_name=bank_name,
        note=note,
        paid_on=paid_on,
        recorded_by=actor_id if mode != "online" else None,
    )
    db.add(p)
    db.flush()
    r = Receipt(
        organisation_id=inv.organisation_id,
        number=_next_number(db, inv.organisation_id, "receipt", settings.receipt_number_prefix),
        payment_id=p.id,
        invoice_id=inv.id,
        person_id=inv.person_id,
        amount=amount,
        status="valid",
        issued_at=clock(),
    )
    db.add(r)
    db.flush()
    p.receipt_id = r.id
    inv.paid_total = Decimal(inv.paid_total) + amount
    _publish(
        db,
        "payment.received",
        inv.organisation_id,
        {
            "payment_id": p.id,
            "invoice_id": inv.id,
            "person_id": inv.person_id,
            "amount": money(amount),
            "mode": mode,
            "receipt_id": r.id,
        },
        actor_id,
    )
    _refresh(db, inv, actor_id)
    _audit(db, actor_id, "payment.received", "payment", p)
    return p


def record_offline_payment(db: Session, actor: Actor, invoice_id: str, body: dict) -> dict:
    inv = _get(db, Invoice, invoice_id, "invoice", lock=True)
    if inv.status not in rules.OPEN_INVOICE_STATUSES:
        raise conflict("not_payable", f"the invoice is {inv.status}")
    amount = _rule(parse_money, body["amount"])
    if amount > balance_of(inv):
        raise invalid("exceeds_balance", f"amount exceeds the invoice balance of {money(balance_of(inv))}", "amount")
    p = apply_payment(
        db,
        inv,
        amount=amount,
        mode=body["mode"],
        paid_on=body["paid_on"],
        actor_id=actor.user_id,
        instrument_number=body.get("instrument_number"),
        bank_name=body.get("bank_name"),
        note=body.get("note"),
    )
    db.commit()
    return payment_dict(p)


def pay_online(db: Session, actor: Actor, invoice_id: str, body: dict) -> dict:
    """Ask the payment adapter for a session (purpose fee). The invoice is updated when the adapter's
    payment.succeeded event arrives (application/consumers.py)."""
    inv = _get(db, Invoice, invoice_id, "invoice")
    if inv.person_id != actor.user_id:
        raise forbidden("you can pay only your own invoices online")
    if inv.status not in rules.OPEN_INVOICE_STATUSES:
        raise conflict("not_payable", f"the invoice is {inv.status}")
    bal = balance_of(inv)
    amount = bal if body.get("amount") is None else _rule(parse_money, body["amount"])
    if amount > bal:
        raise invalid("exceeds_balance", f"amount exceeds the invoice balance of {money(bal)}", "amount")
    if amount < bal and not inv.allow_part_payment:
        raise invalid("part_payment_not_allowed", "this invoice must be paid in full", "amount")
    settings = load_settings()
    return_url = body.get("return_url") or settings.payment_return_url
    if not return_url:
        raise FeesError(503, "payment_not_configured", "no return URL is configured for online payments")
    request = {
        "purpose": "fee",
        "source_module": MODULE,
        "source_reference": inv.id,
        "amount": money(amount),
        "currency": "INR",
        "description": f"Invoice {inv.number}"[:100],
        "payer": {"person_id": inv.person_id},
        "return_url": return_url,
    }
    try:
        r = payment_adapter.start_payment(settings.payment_adapter_url, actor.token, request)
    except payment_adapter.AdapterNotConfiguredError as e:
        raise FeesError(503, "payment_not_configured", "online payment is not configured for this organisation") from e
    if r.status in (201, 409) and r.body.get("payment_url"):
        return {k: r.body.get(k) for k in ("reference", "payment_url", "expires_at")}
    if r.status == 503:
        raise FeesError(503, "payment_not_configured", "online payment is not configured for this organisation")
    raise FeesError(502, "payment_adapter_error", f"the payment adapter answered {r.status}")


def list_payments(db: Session, filters: dict, cursor: str | None, limit: int) -> dict:
    offset = _offset(cursor)
    q = _q(db, Payment)
    if filters.get("person_id"):
        q = q.where(Payment.person_id == filters["person_id"])
    if filters.get("mode"):
        q = q.where(Payment.mode == filters["mode"])
    if filters.get("from"):
        q = q.where(Payment.paid_on >= filters["from"])
    if filters.get("to"):
        q = q.where(Payment.paid_on <= filters["to"])
    rows = list(
        db.scalars(q.order_by(Payment.paid_on.desc(), Payment.created_at.desc()).offset(offset).limit(limit + 1))
    )
    return {"items": [payment_dict(p) for p in rows[:limit]], "next_cursor": _page(rows, limit, offset)}


def get_payment(db: Session, actor: Actor, payment_id: str) -> dict:
    p = _get(db, Payment, payment_id, "payment")
    if not actor.can(perm.INVOICE_READ) and p.person_id != actor.user_id:
        raise not_found("payment")
    return payment_dict(p)


def get_receipt(db: Session, actor: Actor, receipt_id: str) -> dict:
    r = _get(db, Receipt, receipt_id, "receipt")
    if not actor.can(perm.INVOICE_READ) and r.person_id != actor.user_id:
        raise not_found("receipt")
    return receipt_dict(r)


def void_payment(db: Session, actor: Actor, payment_id: str, reason: str) -> dict:
    p = _get(db, Payment, payment_id, "payment", lock=True)
    if p.mode == "online":
        raise conflict("online_payment", "online payments cannot be voided; refund them")
    if p.status != "completed":
        raise conflict("not_voidable", f"the payment is {p.status}")
    inv = _get(db, Invoice, p.invoice_id, "invoice", lock=True)
    p.status, p.voided_at, p.void_reason = "void", clock(), reason
    receipt = db.scalar(_q(db, Receipt).where(Receipt.payment_id == p.id))
    if receipt is not None:
        receipt.status = "cancelled"
    inv.paid_total = Decimal(inv.paid_total) - Decimal(p.amount)
    _refresh(db, inv, actor.user_id)
    _publish(
        db,
        "payment.voided",
        p.organisation_id,
        {
            "payment_id": p.id,
            "invoice_id": inv.id,
            "person_id": p.person_id,
            "amount": money(p.amount),
            "reason": reason,
        },
        actor.user_id,
    )
    _audit(db, actor.user_id, "payment.voided", "payment", p)
    db.commit()
    return payment_dict(p)


def refund_payment(db: Session, actor: Actor, payment_id: str, body: dict) -> dict:
    """Refund all or part of a payment, never above what is left. Online payments with mode `original` go back
    through the adapter; everything else is recorded as paid out. Money given back is no longer paid, so the
    invoice's paid total drops and its balance comes back unless a concession or cancellation covers it (an
    overpayment refunded brings the balance back to zero)."""
    p = _get(db, Payment, payment_id, "payment", lock=True)
    if p.status not in ("completed", "partially_refunded"):
        raise conflict("not_refundable", f"the payment is {p.status}")
    amount = _rule(parse_money, body["amount"])
    in_flight = db.scalar(
        _q(db, Refund)
        .where(Refund.payment_id == p.id, Refund.status == "requested")
        .with_only_columns(func.coalesce(func.sum(Refund.amount), 0))
    )
    refundable = Decimal(p.amount) - Decimal(p.refunded_amount) - Decimal(in_flight or 0)
    if amount > refundable:
        raise invalid("exceeds_refundable", f"amount exceeds the refundable balance of {money(refundable)}", "amount")
    mode = body.get("mode") or "original"
    through_gateway = p.mode == "online" and mode == "original"
    if p.mode != "online" and mode == "original":
        mode = p.mode if p.mode in rules.REFUND_MODES else "cash"
    r = Refund(
        organisation_id=p.organisation_id,
        payment_id=p.id,
        invoice_id=p.invoice_id,
        person_id=p.person_id,
        amount=amount,
        mode=mode,
        status="requested",
        reason=body["reason"],
        requested_by=actor.user_id,
    )
    db.add(r)
    db.flush()
    if through_gateway:
        try:
            answer = payment_adapter.refund(
                load_settings().payment_adapter_url,
                actor.token,
                p.gateway_reference or "",
                money(amount),
                body["reason"],
            )
        except payment_adapter.AdapterNotConfiguredError as e:
            db.rollback()
            raise FeesError(503, "payment_not_configured", "online refunds are not configured") from e
        if answer.status != 202:
            db.rollback()
            raise FeesError(502, "payment_adapter_error", f"the payment adapter answered {answer.status}")
        r.gateway_refund_id = answer.body.get("id")
        status = answer.body.get("status")
        if status == "succeeded":
            complete_refund(db, r, actor.user_id)
        elif status == "failed":
            r.status = "failed"
    else:
        complete_refund(db, r, actor.user_id)
    _audit(db, actor.user_id, f"refund.{r.status}", "refund", r)
    db.commit()
    return refund_dict(r)


def complete_refund(db: Session, r: Refund, actor_id: str | None) -> None:
    if r.status == "completed":
        return
    p = _get(db, Payment, r.payment_id, "payment", lock=True)
    r.status, r.completed_at = "completed", clock()
    p.refunded_amount = Decimal(p.refunded_amount) + Decimal(r.amount)
    p.status = "refunded" if p.refunded_amount >= Decimal(p.amount) else "partially_refunded"
    inv = _get(db, Invoice, r.invoice_id, "invoice", lock=True)
    inv.paid_total = Decimal(inv.paid_total) - Decimal(r.amount)
    _refresh(db, inv, actor_id)
    _publish(
        db,
        "refund.issued",
        r.organisation_id,
        {
            "refund_id": r.id,
            "payment_id": p.id,
            "invoice_id": r.invoice_id,
            "person_id": r.person_id,
            "amount": money(r.amount),
        },
        actor_id,
    )
    _audit(db, actor_id, "refund.completed", "refund", r)


# ---------------------------------------------------------------- concessions


def list_concessions(db: Session, person_id: str | None, status: str | None) -> list[dict]:
    q = _q(db, Concession).order_by(Concession.created_at.desc())
    if person_id:
        q = q.where(Concession.person_id == person_id)
    if status:
        q = q.where(Concession.status == status)
    return [concession_dict(c) for c in db.scalars(q)]


def request_concession(db: Session, actor: Actor, body: dict) -> dict:
    inv = _get(db, Invoice, body["invoice_id"], "invoice")
    if inv.status not in rules.OPEN_INVOICE_STATUSES:
        raise conflict("not_open", f"the invoice is {inv.status}")
    amount = _rule(parse_money, body["amount"]) if body.get("amount") is not None else None
    percent = Decimal(str(body["percent"])) if body.get("percent") is not None else None
    if percent is not None and percent != percent.quantize(Decimal("0.01")):
        raise invalid("invalid_concession", "percent has at most two decimal places", "percent")
    _rule(rules.concession_amount, Decimal(inv.total), amount, percent)
    if amount is not None and amount > Decimal(inv.total):
        raise invalid("exceeds_total", f"amount exceeds the invoice total of {money(inv.total)}", "amount")
    c = Concession(
        organisation_id=actor.organisation_id,
        invoice_id=inv.id,
        person_id=inv.person_id,
        kind=body["kind"],
        amount=amount,
        percent=percent,
        reason=body["reason"],
        document_id=body.get("document_id"),
        status="requested",
        approved_amount=ZERO,
        requested_by=actor.user_id,
    )
    db.add(c)
    _audit(db, actor.user_id, "concession.requested", "concession", c)
    db.commit()
    return concession_dict(c)


def decide_concession(db: Session, actor: Actor, concession_id: str, decision: str, note: str | None) -> dict:
    c = _get(db, Concession, concession_id, "concession", lock=True)
    if c.status != "requested":
        raise conflict("already_decided", f"the concession is already {c.status}")
    if c.requested_by == actor.user_id:
        raise forbidden("you cannot decide a concession you requested")
    c.decided_by, c.decided_at, c.decision_note = actor.user_id, clock(), note
    if decision == "rejected":
        c.status = "rejected"
        _audit(db, actor.user_id, "concession.rejected", "concession", c)
        db.commit()
        return concession_dict(c)
    inv = _get(db, Invoice, c.invoice_id, "invoice", lock=True)
    if inv.status not in rules.OPEN_INVOICE_STATUSES:
        raise conflict("not_open", f"the invoice is {inv.status}")
    worth = rules.concession_amount(Decimal(inv.total), c.amount, c.percent)
    # Capped at what is invoiced (total and late fee) less earlier concessions, not at what is still due: a later void
    # restores the balance against the whole concession, yet nothing is waived that was never invoiced, so money paid
    # above the balance stays visible as `credit` and the ledger never owes what nobody paid.
    approved = min(worth, Decimal(inv.total) + Decimal(inv.late_fee) - Decimal(inv.concession_total))
    if approved <= 0:
        raise conflict("nothing_to_waive", "earlier concessions already cover everything invoiced")
    c.status, c.approved_amount = "approved", approved
    inv.concession_total = Decimal(inv.concession_total) + approved
    _publish(
        db,
        "concession.approved",
        c.organisation_id,
        {
            "concession_id": c.id,
            "invoice_id": inv.id,
            "person_id": inv.person_id,
            "kind": c.kind,
            "approved_amount": money(approved),
        },
        actor.user_id,
    )
    _refresh(db, inv, actor.user_id)
    _audit(db, actor.user_id, "concession.approved", "concession", c)
    db.commit()
    return concession_dict(c)


# ---------------------------------------------------------------- self service, dues and statements


def _open_invoices(db: Session, person_id: str) -> list[Invoice]:
    q = _q(db, Invoice).where(Invoice.person_id == person_id, Invoice.status.in_(rules.OPEN_INVOICE_STATUSES))
    return [i for i in db.scalars(q.order_by(Invoice.due_date, Invoice.number)) if balance_of(i) > 0]


def my_dues(db: Session, actor: Actor) -> dict:
    now = today()
    online = bool(load_settings().payment_adapter_url) and actor.can(perm.SELF_PAY)
    invoices = _open_invoices(db, actor.user_id)
    total = sum((balance_of(i) for i in invoices), ZERO)
    overdue = sum((balance_of(i) for i in invoices if i.due_date < now), ZERO)
    upcoming = [i.due_date for i in invoices if i.due_date >= now]
    return {
        "total_due": money(total),
        "overdue": money(overdue),
        "next_due_date": _iso(min(upcoming)) if upcoming else None,
        "invoices": [
            {
                "id": i.id,
                "number": i.number,
                "title": i.title,
                "balance": money(balance_of(i)),
                "due_date": _iso(i.due_date),
                "overdue": i.due_date < now,
                "can_pay_online": online,
            }
            for i in invoices
        ],
    }


def my_invoices(db: Session, actor: Actor, cursor: str | None, limit: int) -> dict:
    return list_invoices(db, {"person_id": actor.user_id}, cursor, limit)


def my_receipts(db: Session, actor: Actor) -> list[dict]:
    q = _q(db, Receipt).where(Receipt.person_id == actor.user_id).order_by(Receipt.issued_at.desc())
    return [receipt_dict(r) for r in db.scalars(q)]


def dues(db: Session, person_id: str, source_module: str | None, source_reference: str | None) -> dict:
    """GET /dues for other modules: what one person still owes, optionally for one source module and reference."""
    if source_reference and not source_module:
        raise invalid("needs_source_module", "source_reference needs source_module", "source_reference")
    now = today()
    invoices = _open_invoices(db, person_id)
    if source_module:
        invoices = [i for i in invoices if i.source_module == source_module]
    if source_reference:
        invoices = [i for i in invoices if i.source_reference == source_reference]
    return {
        "person_id": person_id,
        "balance": money(sum((balance_of(i) for i in invoices), ZERO)),
        "overdue": money(sum((balance_of(i) for i in invoices if i.due_date < now), ZERO)),
        "invoices": [
            {
                "id": i.id,
                "number": i.number,
                "balance": money(balance_of(i)),
                "due_date": _iso(i.due_date),
                "overdue": i.due_date < now,
                "source": {"module": i.source_module, "reference": i.source_reference} if i.source_module else None,
            }
            for i in invoices
        ],
    }


def statement(db: Session, person_id: str, start: date | None, end: date | None) -> dict:
    """A person's ledger. Debits: invoices, late fees, voided payments, refunds paid out. Credits: concessions,
    payments, cancellations of what was still due. The balance is what the person owes."""
    entries: list[tuple[date, int, str, str, Decimal, Decimal]] = []
    invoices = list(db.scalars(_q(db, Invoice).where(Invoice.person_id == person_id)))
    for inv in invoices:
        entries.append((inv.issued_at.date(), 0, "invoice", inv.number, Decimal(inv.total), ZERO))
        if Decimal(inv.late_fee) > 0:
            entries.append(
                (inv.late_fee_updated_on or inv.due_date, 1, "late_fee", inv.number, Decimal(inv.late_fee), ZERO)
            )
        if inv.status == "cancelled" and inv.cancelled_at:
            remaining = Decimal(inv.total) + Decimal(inv.late_fee) - Decimal(inv.concession_total)
            entries.append((inv.cancelled_at.date(), 5, "cancellation", inv.number, ZERO, remaining))
    numbers = {i.id: i.number for i in invoices}
    for c in db.scalars(_q(db, Concession).where(Concession.person_id == person_id, Concession.status == "approved")):
        entries.append(
            (c.decided_at.date(), 2, "concession", numbers.get(c.invoice_id, ""), ZERO, Decimal(c.approved_amount))
        )
    receipts = {r.payment_id: r.number for r in db.scalars(_q(db, Receipt).where(Receipt.person_id == person_id))}
    for p in db.scalars(_q(db, Payment).where(Payment.person_id == person_id)):
        entries.append((p.paid_on, 3, "payment", receipts.get(p.id, ""), ZERO, Decimal(p.amount)))
        if p.status == "void" and p.voided_at:
            entries.append((p.voided_at.date(), 4, "void", receipts.get(p.id, ""), Decimal(p.amount), ZERO))
    for r in db.scalars(_q(db, Refund).where(Refund.person_id == person_id, Refund.status == "completed")):
        entries.append((r.completed_at.date(), 4, "refund", receipts.get(r.payment_id, ""), Decimal(r.amount), ZERO))
    entries.sort(key=lambda e: (e[0], e[1]))
    opening = ZERO
    running = ZERO
    out = []
    for day, _, kind, reference, debit, credit in entries:
        if start and day < start:
            opening += debit - credit
            running = opening
            continue
        if end and day > end:
            continue
        running += debit - credit
        out.append(
            {
                "date": day.isoformat(),
                "kind": kind,
                "reference": reference,
                "debit": money(debit),
                "credit": money(credit),
                "balance": money(running),
            }
        )
    return {
        "person_id": person_id,
        "opening_balance": money(opening),
        "closing_balance": money(running),
        "entries": out,
    }


# ---------------------------------------------------------------- settings and targets


def _settings_row(db: Session) -> FeeSettings | None:
    return db.scalar(_q(db, FeeSettings))


def get_settings(db: Session) -> dict:
    row = _settings_row(db)
    return {
        "invoice_library_fines": bool(row and row.invoice_library_fines),
        "invoice_staff_transport": bool(row and row.invoice_staff_transport),
    }


def put_settings(db: Session, actor: Actor, body: dict) -> dict:
    row = _settings_row(db) or FeeSettings(organisation_id=actor.organisation_id)
    row.invoice_library_fines = bool(body.get("invoice_library_fines", False))
    row.invoice_staff_transport = bool(body.get("invoice_staff_transport", False))
    db.add(row)
    _audit(db, actor.user_id, "settings.updated", "settings", row)
    db.commit()
    return get_settings(db)


def target_dict(t: CollectionTarget) -> dict:
    return {"period": t.period, "amount": money(t.amount), "fee_head_id": t.fee_head_id}


def list_targets(db: Session, academic_year: str | None) -> list[dict]:
    q = _q(db, CollectionTarget).order_by(CollectionTarget.period)
    if academic_year:
        q = q.where(CollectionTarget.academic_year == academic_year)
    return [target_dict(t) for t in db.scalars(q)]


def put_targets(db: Session, actor: Actor, academic_year: str, targets: list[dict]) -> list[dict]:
    months = set(_rule(rules.academic_year_months, academic_year, load_settings().academic_year_start_month))
    heads = {h.id for h in db.scalars(_q(db, FeeHead))}
    seen: set[tuple[str, str | None]] = set()
    rows = []
    for i, t in enumerate(targets):
        if t.get("fee_head_id") and t["fee_head_id"] not in heads:
            raise invalid("unknown_fee_head", "fee_head_id is not a fee head of your organisation", f"targets[{i}]")
        if (t["period"], t.get("fee_head_id")) in seen:
            raise invalid("duplicate_target", f"{t['period']} is given twice for the same head", f"targets[{i}]")
        seen.add((t["period"], t.get("fee_head_id")))
        if t["period"] not in months:
            raise invalid(
                "period_outside_year", f"{t['period']} is not a month of {academic_year}", f"targets[{i}].period"
            )
        rows.append(
            CollectionTarget(
                organisation_id=actor.organisation_id,
                academic_year=academic_year,
                period=t["period"],
                fee_head_id=t.get("fee_head_id"),
                amount=_rule(parse_money, t["amount"], f"targets[{i}].amount", positive=False),
            )
        )
    for old in db.scalars(_q(db, CollectionTarget).where(CollectionTarget.academic_year == academic_year)):
        db.delete(old)
    db.add_all(rows)
    for t in rows:
        _audit(db, actor.user_id, "collection_target.set", "collection_target", t)
    db.commit()
    return list_targets(db, academic_year)


def day_bounds(day: date) -> tuple[datetime, datetime]:
    from datetime import UTC

    start = datetime.combine(day, time.min, UTC)
    return start, start + timedelta(days=1)
