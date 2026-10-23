"""Use cases of budget-grants. Authenticated calls arrive with the caller's organisation pinned on the session
(api/deps); event handlers and jobs run inside organisation_scope for the event's organisation. Every state change
publishes its budget-grants.* event to the eos_core outbox in the same transaction, which is the audit trail until
the audit SDK exists. Preparer and approver are always different people."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal

from eos_core import events
from eos_core.db import scoped, utcnow
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import ZERO, RuleError, money, parse_money
from ..infrastructure.config import load_settings
from ..infrastructure.models import (
    Alert,
    Budget,
    BudgetHead,
    Expenditure,
    FundsReceived,
    Grant,
    Investigator,
    Line,
    Reappropriation,
    UtilisationCertificate,
)
from . import access as perm
from .access import Actor
from .errors import BudgetError, conflict, forbidden, from_rule, invalid, not_found

MODULE = "budget-grants"


def clock() -> datetime:
    """Now, in UTC. Tests replace it."""
    return utcnow()


def today() -> date:
    return clock().date()


def _publish(db: Session, name: str, organisation_id: str, payload: dict, actor: str | None = None) -> None:
    events.publish(
        db, f"{MODULE}.{name}", organisation_id, {"organisation_id": organisation_id, **payload}, actor=actor
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


def _offset(cursor: str | None) -> int:
    try:
        value = int(cursor) if cursor else 0
    except ValueError as e:
        raise BudgetError(400, "invalid_cursor", "invalid cursor") from e
    if value < 0:
        raise BudgetError(400, "invalid_cursor", "invalid cursor")
    return value


# ---------------------------------------------------------------- line amounts


def line_totals(db: Session, line_ids: list[str]) -> dict[str, tuple[Decimal, Decimal]]:
    """(committed, spent) per line, from entries that are not reversed."""
    out: dict[str, list[Decimal]] = defaultdict(lambda: [ZERO, ZERO])
    if line_ids:
        q = _q(db, Expenditure).where(Expenditure.line_id.in_(line_ids), Expenditure.reversed.is_(False))
        for e in db.scalars(q):
            out[e.line_id][0 if e.kind == "commitment" else 1] += Decimal(e.amount)
    return {lid: (out[lid][0], out[lid][1]) for lid in line_ids}


def _heads(db: Session) -> dict[str, BudgetHead]:
    return {h.id: h for h in db.scalars(_q(db, BudgetHead))}


def line_dicts(db: Session, lines: list[Line]) -> list[dict]:
    totals = line_totals(db, [x.id for x in lines])
    heads = _heads(db)
    out = []
    for x in lines:
        committed, spent = totals[x.id]
        out.append(
            {
                "id": x.id,
                "budget_head_id": x.budget_head_id,
                "budget_head_name": heads[x.budget_head_id].name if x.budget_head_id in heads else "",
                "allocated": money(x.allocated),
                "committed": money(committed),
                "spent": money(spent),
                "available": money(rules.available(Decimal(x.allocated), committed, spent)),
            }
        )
    return out


def _lines_of(db: Session, *, budget_id: str | None = None, grant_id: str | None = None) -> list[Line]:
    q = _q(db, Line)
    q = q.where(Line.budget_id == budget_id) if budget_id else q.where(Line.grant_id == grant_id)
    return list(db.scalars(q.order_by(Line.id)))


def _line_is_open(db: Session, line: Line) -> bool:
    if line.kind == "budget":
        b = db.scalar(_q(db, Budget).where(Budget.id == line.budget_id))
        return b is not None and b.status == "approved"
    g = db.scalar(_q(db, Grant).where(Grant.id == line.grant_id))
    return g is not None and g.status == "active"


def open_line(db: Session, line_id: str, *, lock: bool = False) -> Line:
    """A line of an approved budget or an active grant, or 404."""
    line = db.scalar(
        _q(db, Line).where(Line.id == line_id).with_for_update() if lock else _q(db, Line).where(Line.id == line_id)
    )
    if line is None or not _line_is_open(db, line):
        raise not_found("line in an approved budget or active grant")
    return line


def line_available(db: Session, line: Line) -> Decimal:
    committed, spent = line_totals(db, [line.id])[line.id]
    return rules.available(Decimal(line.allocated), committed, spent)


def check_thresholds(db: Session, line: Line) -> None:
    """Publish line.threshold-reached once per line and threshold, the first time committed plus spent crosses it."""
    committed, spent = line_totals(db, [line.id])[line.id]
    pct = rules.used_percent(Decimal(line.allocated), committed, spent)
    sent = {a.key for a in db.scalars(_q(db, Alert).where(Alert.kind == "threshold", Alert.subject_id == line.id))}
    for t in rules.thresholds_crossed(pct, list(load_settings().alert_percents)):
        if str(t) in sent:
            continue
        db.add(
            Alert(
                organisation_id=line.organisation_id, kind="threshold", subject_id=line.id, key=str(t), sent_at=clock()
            )
        )
        _publish(
            db,
            "line.threshold-reached",
            line.organisation_id,
            {
                "line_id": line.id,
                "kind": line.kind,
                "percent": t,
                "allocated": money(line.allocated),
                "used": money(committed + spent),
            },
        )


def record_expenditure(
    db: Session,
    line: Line,
    *,
    kind: str,
    amount: Decimal,
    day: date,
    description: str,
    actor_id: str | None,
    source_module: str = "manual",
    source_reference: str | None = None,
    purchase_order_id: str | None = None,
    document_id: str | None = None,
) -> Expenditure:
    e = Expenditure(
        organisation_id=line.organisation_id,
        line_id=line.id,
        kind=kind,
        amount=amount,
        date=day,
        description=description[:300],
        source_module=source_module,
        source_reference=source_reference,
        purchase_order_id=purchase_order_id,
        document_id=document_id,
        reversed=False,
        recorded_by=actor_id,
        recorded_at=clock(),
    )
    db.add(e)
    db.flush()
    check_thresholds(db, line)
    return e


# ---------------------------------------------------------------- serialisers


def head_dict(h: BudgetHead) -> dict:
    return {
        "id": h.id,
        "organisation_id": h.organisation_id,
        "code": h.code,
        "name": h.name,
        "kind": h.kind,
        "active": h.active,
    }


def budget_dict(db: Session, b: Budget) -> dict:
    lines = line_dicts(db, _lines_of(db, budget_id=b.id))
    return {
        "id": b.id,
        "organisation_id": b.organisation_id,
        "financial_year": b.financial_year,
        "department_id": b.department_id,
        "department_name": None,  # departments are not available to modules yet
        "title": b.title,
        "status": b.status,
        "lines": lines,
        "allocated_total": money(sum((Decimal(x["allocated"]) for x in lines), ZERO)),
        "spent_total": money(sum((Decimal(x["spent"]) for x in lines), ZERO)),
        "prepared_by": b.prepared_by,
        "approved_by": b.approved_by,
        "approved_at": _iso(b.approved_at),
    }


def reappropriation_dict(r: Reappropriation) -> dict:
    return {
        "id": r.id,
        "organisation_id": r.organisation_id,
        "from_line_id": r.from_line_id,
        "to_line_id": r.to_line_id,
        "amount": money(r.amount),
        "reason": r.reason,
        "status": r.status,
        "requested_by": r.requested_by,
        "decided_by": r.decided_by,
        "decided_at": _iso(r.decided_at),
    }


def expenditure_dict(e: Expenditure) -> dict:
    return {
        "id": e.id,
        "organisation_id": e.organisation_id,
        "line_id": e.line_id,
        "kind": e.kind,
        "amount": money(e.amount),
        "date": _iso(e.date),
        "description": e.description,
        "source": {"module": e.source_module, "reference": e.source_reference or ""},
        "reversed": e.reversed,
        "document_id": e.document_id,
        "recorded_at": _iso(e.recorded_at),
    }


def _covered_until(db: Session, grant_id: str) -> date | None:
    q = _q(db, UtilisationCertificate).where(
        UtilisationCertificate.grant_id == grant_id, UtilisationCertificate.status.in_(("approved", "submitted"))
    )
    ends = [c.period_to for c in db.scalars(q)]
    return max(ends) if ends else None


def grant_next_uc_due(db: Session, g: Grant) -> date | None:
    if g.status != "active":
        return None
    return rules.next_uc_due(g.start_date, g.end_date, g.uc_frequency, _covered_until(db, g.id))


def _received_total(db: Session, grant_id: str) -> Decimal:
    q = _q(db, FundsReceived).where(FundsReceived.grant_id == grant_id)
    return sum((Decimal(f.amount) for f in db.scalars(q)), ZERO)


def grant_dict(db: Session, g: Grant) -> dict:
    lines = line_dicts(db, _lines_of(db, grant_id=g.id))
    received = list(
        db.scalars(_q(db, FundsReceived).where(FundsReceived.grant_id == g.id).order_by(FundsReceived.received_on))
    )
    received_total = sum((Decimal(f.amount) for f in received), ZERO)
    spent = sum((Decimal(x["spent"]) for x in lines), ZERO)
    investigators = list(
        db.scalars(_q(db, Investigator).where(Investigator.grant_id == g.id).order_by(Investigator.role.desc()))
    )
    return {
        "id": g.id,
        "organisation_id": g.organisation_id,
        "code": g.code,
        "title": g.title,
        "funder": g.funder,
        "scheme": g.scheme,
        "sanctioned_amount": money(g.sanctioned_amount),
        "received_total": money(received_total),
        "committed_total": money(sum((Decimal(x["committed"]) for x in lines), ZERO)),
        "spent_total": money(spent),
        "balance": money(received_total - spent),
        "start_date": _iso(g.start_date),
        "end_date": _iso(g.end_date),
        "status": g.status,
        "department_id": g.department_id,
        "investigators": [{"user_id": i.user_id, "name": "", "role": i.role} for i in investigators],
        "uc_frequency": g.uc_frequency,
        "next_uc_due": _iso(grant_next_uc_due(db, g)),
        "lines": lines,
        "funds_received": [
            {"amount": money(f.amount), "received_on": _iso(f.received_on), "reference": f.reference or ""}
            for f in received
        ],
        "unspent_action": g.unspent_action,
    }


def certificate_dict(c: UtilisationCertificate) -> dict:
    return {
        "id": c.id,
        "organisation_id": c.organisation_id,
        "grant_id": c.grant_id,
        "period_from": _iso(c.period_from),
        "period_to": _iso(c.period_to),
        "opening_balance": money(c.opening_balance),
        "received": money(c.received),
        "spent": money(c.spent),
        "closing_balance": money(c.closing_balance),
        "by_head": list(c.by_head or []),
        "status": c.status,
        "document_id": c.document_id,
        "prepared_by": c.prepared_by,
        "approved_by": c.approved_by,
        "submitted_on": _iso(c.submitted_on),
    }


# ---------------------------------------------------------------- budget heads


def list_heads(db: Session) -> list[dict]:
    return [head_dict(h) for h in db.scalars(_q(db, BudgetHead).order_by(BudgetHead.code))]


def _code_taken(db: Session, code: str, except_id: str | None = None) -> bool:
    q = _q(db, BudgetHead).where(BudgetHead.code == code)
    if except_id:
        q = q.where(BudgetHead.id != except_id)
    return db.scalar(q) is not None


def create_head(db: Session, actor: Actor, body: dict) -> dict:
    if _code_taken(db, body["code"]):
        raise conflict("code_taken", f"budget head code {body['code']} is already used")
    h = BudgetHead(organisation_id=actor.organisation_id, **body)
    db.add(h)
    _commit_unique(db, f"budget head code {body['code']} is already used")
    return head_dict(h)


def _commit_unique(db: Session, message: str) -> None:
    """Commit; a concurrent request that took the same unique code answers 409 like the check before it."""
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise conflict("code_taken", message) from e


def update_head(db: Session, actor: Actor, head_id: str, body: dict) -> dict:
    h = _get(db, BudgetHead, head_id, "budget head")
    if _code_taken(db, body["code"], except_id=h.id):
        raise conflict("code_taken", f"budget head code {body['code']} is already used")
    for key, value in body.items():
        setattr(h, key, value)
    _commit_unique(db, f"budget head code {body['code']} is already used")
    return head_dict(h)


def _checked_lines(
    db: Session, items: list[dict], amount_key: str, *, positive: bool, existing: set[str] | None = None
) -> list[tuple[str, Decimal, str]]:
    """(budget_head_id, amount, note) for each item: a head of the organisation, at most once, and active unless the
    line already exists (a head deactivated later must not block revising what was sanctioned)."""
    heads = _heads(db)
    seen, out = set(), []
    for i, item in enumerate(items):
        head = heads.get(item["budget_head_id"])
        if head is None or (not head.active and head.id not in (existing or set())):
            raise invalid(
                "unknown_budget_head", "every line needs an active budget head of your organisation", f"lines[{i}]"
            )
        if head.id in seen:
            raise invalid("duplicate_budget_head", "each budget head appears once", f"lines[{i}]")
        seen.add(head.id)
        out.append(
            (
                head.id,
                _rule(parse_money, item[amount_key], f"lines[{i}].{amount_key}", positive=positive),
                item.get("note") or "",
            )
        )
    return out


# ---------------------------------------------------------------- budgets


def list_budgets(db: Session, financial_year: str | None, department_id: str | None, status: str | None) -> list[dict]:
    q = _q(db, Budget).order_by(Budget.financial_year.desc(), Budget.created_at)
    if financial_year:
        q = q.where(Budget.financial_year == financial_year)
    if department_id:
        q = q.where(Budget.department_id == department_id)
    if status:
        q = q.where(Budget.status == status)
    return [budget_dict(db, b) for b in db.scalars(q)]


def get_budget(db: Session, budget_id: str) -> dict:
    return budget_dict(db, _get(db, Budget, budget_id, "budget"))


def _budget_exists(db: Session, financial_year: str, department_id: str | None, except_id: str | None = None) -> bool:
    q = _q(db, Budget).where(Budget.financial_year == financial_year, Budget.status != "closed")
    q = (
        q.where(Budget.department_id.is_(None))
        if department_id is None
        else q.where(Budget.department_id == department_id)
    )
    if except_id:
        q = q.where(Budget.id != except_id)
    return db.scalar(q) is not None


def line_in_use(db: Session, line_id: str) -> bool:
    """Whether any entry (even a reversed or released one) or reappropriation refers to the line."""
    if db.scalar(_q(db, Expenditure).where(Expenditure.line_id == line_id)) is not None:
        return True
    q = _q(db, Reappropriation).where(
        or_(Reappropriation.from_line_id == line_id, Reappropriation.to_line_id == line_id)
    )
    return db.scalar(q) is not None


def _set_budget_lines(db: Session, b: Budget, lines: list[tuple[str, Decimal, str]]) -> None:
    for old in _lines_of(db, budget_id=b.id):
        if line_in_use(db, old.id):  # an event can name a line of a draft budget; its record is kept
            raise conflict("line_in_use", "a budget line with entries cannot be replaced")
        db.delete(old)
    db.flush()
    for head_id, allocated, note in lines:
        db.add(
            Line(
                organisation_id=b.organisation_id,
                kind="budget",
                budget_id=b.id,
                budget_head_id=head_id,
                allocated=allocated,
                note=note,
            )
        )


def create_budget(db: Session, actor: Actor, body: dict) -> dict:
    _rule(rules.financial_year_bounds, body["financial_year"], load_settings().financial_year_start_month)
    if _budget_exists(db, body["financial_year"], body.get("department_id")):
        raise conflict("budget_exists", "a budget for this year and cost centre already exists")
    lines = _checked_lines(db, body["lines"], "allocated", positive=False)
    b = Budget(
        organisation_id=actor.organisation_id,
        financial_year=body["financial_year"],
        department_id=body.get("department_id"),
        title=body.get("title") or "",
        status="draft",
        prepared_by=actor.user_id,
    )
    db.add(b)
    db.flush()
    _set_budget_lines(db, b, lines)
    db.commit()
    return budget_dict(db, b)


def update_budget(db: Session, actor: Actor, budget_id: str, body: dict) -> dict:
    b = _get(db, Budget, budget_id, "budget", lock=True)
    if b.status not in rules.EDITABLE_BUDGET_STATUSES:
        raise conflict("not_editable", f"the budget is {b.status}; approved budgets change only by reappropriation")
    _rule(rules.financial_year_bounds, body["financial_year"], load_settings().financial_year_start_month)
    if _budget_exists(db, body["financial_year"], body.get("department_id"), except_id=b.id):
        raise conflict("budget_exists", "a budget for this year and cost centre already exists")
    lines = _checked_lines(db, body["lines"], "allocated", positive=False)
    b.financial_year, b.department_id, b.title = (
        body["financial_year"],
        body.get("department_id"),
        body.get("title") or "",
    )
    _set_budget_lines(db, b, lines)
    b.prepared_by = actor.user_id  # the person who last shaped it may not approve it
    db.commit()
    return budget_dict(db, b)


def submit_budget(db: Session, actor: Actor, budget_id: str) -> dict:
    b = _get(db, Budget, budget_id, "budget", lock=True)
    if b.status not in rules.EDITABLE_BUDGET_STATUSES:
        raise conflict("not_submittable", f"the budget is {b.status}")
    b.status, b.prepared_by = "submitted", actor.user_id
    db.commit()
    return budget_dict(db, b)


def decide_budget(db: Session, actor: Actor, budget_id: str, decision: str, note: str | None) -> dict:
    if decision not in ("approved", "returned"):
        raise invalid("invalid_decision", "a budget is approved or returned", "decision")
    b = _get(db, Budget, budget_id, "budget", lock=True)
    if b.status != "submitted":
        raise conflict("not_submitted", "the budget is not submitted")
    if b.prepared_by == actor.user_id:
        raise forbidden("you cannot decide a budget you prepared")
    b.decision_note = note
    if decision == "returned":
        b.status = "returned"
    else:
        b.status, b.approved_by, b.approved_at = "approved", actor.user_id, clock()
        total = sum((Decimal(x.allocated) for x in _lines_of(db, budget_id=b.id)), ZERO)
        _publish(
            db,
            "budget.approved",
            b.organisation_id,
            {
                "budget_id": b.id,
                "financial_year": b.financial_year,
                "department_id": b.department_id,
                "allocated_total": money(total),
            },
            actor.user_id,
        )
    db.commit()
    return budget_dict(db, b)


# ---------------------------------------------------------------- reappropriations


def list_reappropriations(db: Session, status: str | None) -> list[dict]:
    q = _q(db, Reappropriation).order_by(Reappropriation.created_at.desc())
    if status:
        q = q.where(Reappropriation.status == status)
    return [reappropriation_dict(r) for r in db.scalars(q)]


def _budget_line_pair(db: Session, from_id: str, to_id: str, *, lock: bool = False) -> tuple[Line, Line]:
    if from_id == to_id:
        raise invalid("same_line", "money moves between two different lines", "to_line_id")
    src, dst = open_line(db, from_id, lock=lock), open_line(db, to_id, lock=lock)
    if src.kind != "budget" or dst.kind != "budget" or src.budget_id != dst.budget_id:
        raise invalid("different_budgets", "both lines must belong to the same approved budget", "to_line_id")
    return src, dst


def request_reappropriation(db: Session, actor: Actor, body: dict) -> dict:
    src, _ = _budget_line_pair(db, body["from_line_id"], body["to_line_id"])
    amount = _rule(parse_money, body["amount"])
    if amount > line_available(db, src):
        raise invalid(
            "exceeds_available",
            f"amount exceeds the {money(line_available(db, src))} available on the source line",
            "amount",
        )
    r = Reappropriation(
        organisation_id=actor.organisation_id,
        from_line_id=src.id,
        to_line_id=body["to_line_id"],
        amount=amount,
        reason=body["reason"],
        status="requested",
        requested_by=actor.user_id,
    )
    db.add(r)
    db.commit()
    return reappropriation_dict(r)


def decide_reappropriation(db: Session, actor: Actor, reappropriation_id: str, decision: str, note: str | None) -> dict:
    if decision not in ("approved", "rejected"):
        raise invalid("invalid_decision", "a reappropriation is approved or rejected", "decision")
    r = _get(db, Reappropriation, reappropriation_id, "reappropriation", lock=True)
    if r.status != "requested":
        raise conflict("already_decided", f"the reappropriation is already {r.status}")
    if r.requested_by == actor.user_id:
        raise forbidden("you cannot decide a reappropriation you requested")
    r.decided_by, r.decided_at, r.decision_note = actor.user_id, clock(), note
    if decision == "rejected":
        r.status = "rejected"
        db.commit()
        return reappropriation_dict(r)
    src, dst = _budget_line_pair(db, r.from_line_id, r.to_line_id, lock=True)
    if Decimal(r.amount) > line_available(db, src):  # spending since the request may have used it
        raise invalid(
            "exceeds_available", f"only {money(line_available(db, src))} is now available on the source line", "amount"
        )
    src.allocated = Decimal(src.allocated) - Decimal(r.amount)
    dst.allocated = Decimal(dst.allocated) + Decimal(r.amount)
    r.status = "approved"
    _publish(
        db,
        "reappropriation.approved",
        r.organisation_id,
        {"reappropriation_id": r.id, "from_line_id": src.id, "to_line_id": dst.id, "amount": money(r.amount)},
        actor.user_id,
    )
    check_thresholds(db, src)
    db.commit()
    return reappropriation_dict(r)


# ---------------------------------------------------------------- availability, lines, expenditure


def availability(db: Session, line_id: str, amount: str) -> dict:
    value = _rule(parse_money, amount)
    line = open_line(db, line_id)
    left = line_available(db, line)
    return {"line_id": line.id, "available": money(left), "sufficient": value <= left}


def list_lines(db: Session, financial_year: str | None, department_id: str | None, q_text: str | None) -> list[dict]:
    heads = _heads(db)
    out = []
    bq = _q(db, Budget).where(Budget.status == "approved")
    if financial_year:
        bq = bq.where(Budget.financial_year == financial_year)
    if department_id:
        bq = bq.where(Budget.department_id == department_id)
    for b in db.scalars(bq):
        for x in _lines_of(db, budget_id=b.id):
            out.append((x, f"{b.financial_year} {b.title or 'Institution'} / {heads[x.budget_head_id].name}"))
    gq = _q(db, Grant).where(Grant.status == "active")
    if department_id:
        gq = gq.where(Grant.department_id == department_id)
    for g in db.scalars(gq):
        for x in _lines_of(db, grant_id=g.id):
            out.append((x, f"{g.code} / {heads[x.budget_head_id].name}"))
    if q_text:
        out = [(x, label) for x, label in out if q_text.lower() in label.lower()]
    totals = line_totals(db, [x.id for x, _ in out])
    return [
        {
            "line_id": x.id,
            "kind": x.kind,
            "label": label,
            "available": money(rules.available(Decimal(x.allocated), *totals[x.id])),
        }
        for x, label in out
    ]


def list_expenditures(db: Session, filters: dict, cursor: str | None, limit: int) -> dict:
    offset = _offset(cursor)
    q = _q(db, Expenditure)
    if filters.get("line_id"):
        q = q.where(Expenditure.line_id == filters["line_id"])
    if filters.get("kind"):
        q = q.where(Expenditure.kind == filters["kind"])
    if filters.get("from"):
        q = q.where(Expenditure.date >= filters["from"])
    if filters.get("to"):
        q = q.where(Expenditure.date <= filters["to"])
    rows = list(
        db.scalars(q.order_by(Expenditure.date.desc(), Expenditure.recorded_at.desc()).offset(offset).limit(limit + 1))
    )
    return {
        "items": [expenditure_dict(e) for e in rows[:limit]],
        "next_cursor": str(offset + limit) if len(rows) > limit else None,
    }


def _line_period(db: Session, line: Line) -> tuple[date, date]:
    if line.kind == "grant":
        g = _get(db, Grant, line.grant_id, "grant")
        return g.start_date, g.end_date
    b = _get(db, Budget, line.budget_id, "budget")
    return rules.financial_year_bounds(b.financial_year, load_settings().financial_year_start_month)


def record_manual_expenditure(db: Session, actor: Actor, body: dict) -> dict:
    line = open_line(db, body["line_id"], lock=True)
    amount = _rule(parse_money, body["amount"])
    first, last = _line_period(db, line)
    if not first <= body["date"] <= last:
        raise invalid("date_outside_period", f"the date must be between {first} and {last}", "date")
    left = line_available(db, line)
    if amount > left:
        raise invalid("exceeds_available", f"amount exceeds the {money(left)} available on the line", "amount")
    e = record_expenditure(
        db,
        line,
        kind="actual",
        amount=amount,
        day=body["date"],
        description=body["description"],
        actor_id=actor.user_id,
        document_id=body.get("document_id"),
    )
    db.commit()
    return expenditure_dict(e)


def reverse_expenditure(db: Session, actor: Actor, expenditure_id: str, reason: str) -> dict:
    e = _get(db, Expenditure, expenditure_id, "expenditure", lock=True)
    if e.source_module != "manual":
        raise conflict("from_another_module", f"this entry came from {e.source_module}; its own event reverses it")
    if e.reversed:
        raise conflict("already_reversed", "the entry is already reversed")
    e.reversed, e.reversal_reason = True, reason
    db.commit()
    return expenditure_dict(e)


# ---------------------------------------------------------------- grants


def _investigator_ids(db: Session, grant_id: str) -> set[str]:
    return {i.user_id for i in db.scalars(_q(db, Investigator).where(Investigator.grant_id == grant_id))}


def list_grants(
    db: Session, status: str | None, funder: str | None, principal_investigator_id: str | None
) -> list[dict]:
    q = _q(db, Grant).order_by(Grant.start_date.desc())
    if status:
        q = q.where(Grant.status == status)
    if funder:
        q = q.where(Grant.funder == funder)
    grants = list(db.scalars(q))
    if principal_investigator_id:
        ids = {
            i.grant_id
            for i in db.scalars(
                _q(db, Investigator).where(
                    Investigator.user_id == principal_investigator_id, Investigator.role == "principal"
                )
            )
        }
        grants = [g for g in grants if g.id in ids]
    return [grant_dict(db, g) for g in grants]


def _readable_grant(db: Session, actor: Actor, grant_id: str) -> Grant:
    g = _get(db, Grant, grant_id, "grant")
    if not actor.can(perm.GRANT_READ) and actor.user_id not in _investigator_ids(db, g.id):
        raise not_found("grant")  # not revealed to people who are neither staff nor investigators
    return g


def get_grant(db: Session, actor: Actor, grant_id: str) -> dict:
    return grant_dict(db, _readable_grant(db, actor, grant_id))


def _grant_values(
    db: Session, body: dict, existing: set[str] | None = None
) -> tuple[dict, list[tuple[str, Decimal, str]], list[dict]]:
    sanctioned = _rule(parse_money, body["sanctioned_amount"], "sanctioned_amount")
    if body["end_date"] <= body["start_date"]:
        raise invalid("invalid_period", "end_date must be after start_date", "end_date")
    lines = _checked_lines(db, body["lines"], "sanctioned", positive=False, existing=existing)
    if sum((x[1] for x in lines), ZERO) != sanctioned:
        raise invalid("lines_not_sanctioned_total", "line totals must equal the sanctioned amount", "lines")
    investigators = body["investigators"]
    if not any(i["role"] == "principal" for i in investigators):
        raise invalid("no_principal", "a grant needs a principal investigator", "investigators")
    if len({i["user_id"] for i in investigators}) != len(investigators):
        raise invalid("duplicate_investigator", "each investigator appears once", "investigators")
    values = {
        "code": body["code"],
        "title": body["title"],
        "funder": body["funder"],
        "scheme": body.get("scheme") or "",
        "sanction_order_document_id": body.get("sanction_order_document_id"),
        "sanctioned_amount": sanctioned,
        "start_date": body["start_date"],
        "end_date": body["end_date"],
        "department_id": body.get("department_id"),
        "uc_frequency": body.get("uc_frequency") or "yearly",
    }
    return values, lines, investigators


def _grant_code_taken(db: Session, code: str, except_id: str | None = None) -> bool:
    q = _q(db, Grant).where(Grant.code == code)
    if except_id:
        q = q.where(Grant.id != except_id)
    return db.scalar(q) is not None


def _set_investigators(db: Session, g: Grant, investigators: list[dict]) -> None:
    for old in db.scalars(_q(db, Investigator).where(Investigator.grant_id == g.id)):
        db.delete(old)
    db.flush()
    for i in investigators:
        db.add(Investigator(organisation_id=g.organisation_id, grant_id=g.id, user_id=i["user_id"], role=i["role"]))


def create_grant(db: Session, actor: Actor, body: dict) -> dict:
    values, lines, investigators = _grant_values(db, body)
    if _grant_code_taken(db, values["code"]):
        raise conflict("code_taken", f"grant {values['code']} is already recorded")
    g = Grant(organisation_id=actor.organisation_id, status="active", **values)
    db.add(g)
    db.flush()
    for head_id, sanctioned, note in lines:
        db.add(
            Line(
                organisation_id=g.organisation_id,
                kind="grant",
                grant_id=g.id,
                budget_head_id=head_id,
                allocated=sanctioned,
                note=note,
            )
        )
    _set_investigators(db, g, investigators)
    db.flush()
    principal = next(i["user_id"] for i in investigators if i["role"] == "principal")
    _publish(
        db,
        "grant.sanctioned",
        g.organisation_id,
        {
            "grant_id": g.id,
            "code": g.code,
            "funder": g.funder,
            "sanctioned_amount": money(g.sanctioned_amount),
            "principal_investigator_id": principal,
            "start_date": _iso(g.start_date),
            "end_date": _iso(g.end_date),
        },
        actor.user_id,
    )
    db.commit()
    return grant_dict(db, g)


def update_grant(db: Session, actor: Actor, grant_id: str, body: dict) -> dict:
    """A revised sanction: details, investigators and lines. A line keeps its entries; a head that has commitments or
    spend cannot be dropped."""
    g = _get(db, Grant, grant_id, "grant", lock=True)
    if g.status != "active":
        raise conflict("grant_closed", "a closed grant cannot be revised")
    existing = {x.budget_head_id: x for x in _lines_of(db, grant_id=g.id)}
    values, lines, investigators = _grant_values(db, body, existing=set(existing))
    if _grant_code_taken(db, values["code"], except_id=g.id):
        raise conflict("code_taken", f"grant {values['code']} is already recorded")
    wanted = {head_id: (sanctioned, note) for head_id, sanctioned, note in lines}
    totals = line_totals(db, [x.id for x in existing.values()])
    changed = []
    for head_id, line in existing.items():
        if head_id not in wanted:
            if line_in_use(db, line.id):
                raise conflict("line_in_use", "a grant line with entries cannot be removed")
            db.delete(line)
    for head_id, (sanctioned, note) in wanted.items():
        if head_id in existing:
            committed, spent = totals[existing[head_id].id]
            if sanctioned < committed + spent:
                raise conflict(
                    "below_used", f"a line cannot be revised below the {money(committed + spent)} already used on it"
                )
            existing[head_id].allocated, existing[head_id].note = sanctioned, note
            changed.append(existing[head_id])
        else:
            db.add(
                Line(
                    organisation_id=g.organisation_id,
                    kind="grant",
                    grant_id=g.id,
                    budget_head_id=head_id,
                    allocated=sanctioned,
                    note=note,
                )
            )
    for key, value in values.items():
        setattr(g, key, value)
    _set_investigators(db, g, investigators)
    db.flush()
    for line in changed:
        check_thresholds(db, line)
    _commit_unique(db, f"grant {values['code']} is already recorded")
    return grant_dict(db, g)


def funds_received(db: Session, actor: Actor, grant_id: str, body: dict) -> dict:
    g = _get(db, Grant, grant_id, "grant", lock=True)
    if g.status != "active":
        raise conflict("grant_closed", "the grant is closed")
    amount = _rule(parse_money, body["amount"])
    db.add(
        FundsReceived(
            organisation_id=g.organisation_id,
            grant_id=g.id,
            amount=amount,
            received_on=body["received_on"],
            reference=body.get("reference"),
        )
    )
    _publish(
        db,
        "grant.funds-received",
        g.organisation_id,
        {"grant_id": g.id, "amount": money(amount), "received_on": _iso(body["received_on"])},
        actor.user_id,
    )
    db.commit()
    return grant_dict(db, g)


def close_grant(db: Session, actor: Actor, grant_id: str, unspent_action: str, note: str | None) -> dict:
    g = _get(db, Grant, grant_id, "grant", lock=True)
    if g.status != "active":
        raise conflict("grant_closed", "the grant is already closed")
    lines = _lines_of(db, grant_id=g.id)
    spent = sum((t[1] for t in line_totals(db, [x.id for x in lines]).values()), ZERO)
    unspent = _received_total(db, g.id) - spent
    g.status, g.unspent_action, g.close_note, g.closed_at = "closed", unspent_action, note, clock()
    _publish(
        db,
        "grant.closed",
        g.organisation_id,
        {"grant_id": g.id, "unspent": money(unspent), "unspent_action": unspent_action},
        actor.user_id,
    )
    db.commit()
    return grant_dict(db, g)


def my_grants(db: Session, actor: Actor) -> list[dict]:
    roles = {i.grant_id: i.role for i in db.scalars(_q(db, Investigator).where(Investigator.user_id == actor.user_id))}
    if not roles:
        return []
    grants = db.scalars(_q(db, Grant).where(Grant.id.in_(list(roles))).order_by(Grant.end_date))
    out = []
    for g in grants:
        d = grant_dict(db, g)
        out.append(
            {
                "id": g.id,
                "organisation_id": g.organisation_id,
                "code": g.code,
                "title": g.title,
                "funder": g.funder,
                "my_role": roles[g.id],
                "sanctioned_amount": d["sanctioned_amount"],
                "spent_total": d["spent_total"],
                "balance": d["balance"],
                "end_date": d["end_date"],
                "next_uc_due": d["next_uc_due"],
            }
        )
    return out


# ---------------------------------------------------------------- utilisation certificates


def list_certificates(db: Session, actor: Actor, grant_id: str) -> list[dict]:
    g = _readable_grant(db, actor, grant_id)
    q = (
        _q(db, UtilisationCertificate)
        .where(UtilisationCertificate.grant_id == g.id)
        .order_by(UtilisationCertificate.period_from)
    )
    return [certificate_dict(c) for c in db.scalars(q)]


def draft_certificate(db: Session, actor: Actor, grant_id: str, period_from: date, period_to: date) -> dict:
    """Received, spent by head and balances for a period, computed from the records."""
    g = _get(db, Grant, grant_id, "grant")
    if period_to < period_from:
        raise invalid("invalid_period", "period_to must not be before period_from", "period_to")
    if period_from < g.start_date or period_to > g.end_date:
        raise invalid("outside_grant", f"the period must lie within {g.start_date} and {g.end_date}", "period_from")
    lines = _lines_of(db, grant_id=g.id)
    heads = _heads(db)
    receipts = list(db.scalars(_q(db, FundsReceived).where(FundsReceived.grant_id == g.id)))
    spends = list(
        db.scalars(
            _q(db, Expenditure).where(
                Expenditure.line_id.in_([x.id for x in lines]),
                Expenditure.kind == "actual",
                Expenditure.reversed.is_(False),
            )
        )
    )
    received_before = sum((Decimal(f.amount) for f in receipts if f.received_on < period_from), ZERO)
    spent_before = sum((Decimal(e.amount) for e in spends if e.date < period_from), ZERO)
    received = sum((Decimal(f.amount) for f in receipts if period_from <= f.received_on <= period_to), ZERO)
    in_period = [e for e in spends if period_from <= e.date <= period_to]
    spent = sum((Decimal(e.amount) for e in in_period), ZERO)
    opening = received_before - spent_before
    by_line = defaultdict(lambda: ZERO)
    for e in in_period:
        by_line[e.line_id] += Decimal(e.amount)
    c = UtilisationCertificate(
        organisation_id=g.organisation_id,
        grant_id=g.id,
        period_from=period_from,
        period_to=period_to,
        opening_balance=opening,
        received=received,
        spent=spent,
        closing_balance=opening + received - spent,
        by_head=[
            {
                "budget_head_name": heads[x.budget_head_id].name if x.budget_head_id in heads else "",
                "sanctioned": money(x.allocated),
                "spent": money(by_line[x.id]),
            }
            for x in lines
        ],
        status="draft",
        prepared_by=actor.user_id,
    )
    db.add(c)
    db.commit()
    return certificate_dict(c)


def decide_certificate(db: Session, actor: Actor, certificate_id: str, decision: str, note: str | None) -> dict:
    if decision not in ("approved", "returned"):
        raise invalid("invalid_decision", "a certificate is approved or returned", "decision")
    c = _get(db, UtilisationCertificate, certificate_id, "utilisation certificate", lock=True)
    if c.status != "draft":  # a returned certificate is redrafted with POST, never certified as it stands
        raise conflict("not_draft", f"the certificate is {c.status}")
    if c.prepared_by == actor.user_id:
        raise forbidden("you cannot certify a certificate you prepared")
    c.decision_note = note
    if decision == "approved":
        # The PDF is generated in platform/documents once its SDK exists; document_id stays empty until then.
        c.status, c.approved_by = "approved", actor.user_id
    else:
        c.status = "returned"
    db.commit()
    return certificate_dict(c)


def mark_certificate_submitted(db: Session, actor: Actor, certificate_id: str, body: dict) -> dict:
    c = _get(db, UtilisationCertificate, certificate_id, "utilisation certificate", lock=True)
    if c.status != "approved":
        raise conflict("not_approved", f"only an approved certificate is sent; this one is {c.status}")
    c.status = "submitted"
    c.submitted_on = body.get("submitted_on") or today()
    c.submission_reference = body.get("reference")
    _publish(
        db,
        "utilisation-certificate.submitted",
        c.organisation_id,
        {
            "certificate_id": c.id,
            "grant_id": c.grant_id,
            "period_from": _iso(c.period_from),
            "period_to": _iso(c.period_to),
            "spent": money(c.spent),
        },
        actor.user_id,
    )
    db.commit()
    return certificate_dict(c)
