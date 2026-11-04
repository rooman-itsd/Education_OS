"""Use cases of library (docs/prd.md, docs/user-stories.md). Each one checks the domain rules, changes state, writes
an audit entry, and publishes the matching event from contracts/events.yaml to the outbox in the same transaction.

A person is identified by their identity user id (the token subject). Money is exact (Decimal) inside and a decimal
string ("25.00") at the API, as the contract's Money schema says."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import Policy, RefusedError, RuleViolationError, money, money_str
from ..infrastructure import repository as repo
from ..infrastructure.models import (
    AuditEntry,
    Copy,
    DigitalResource,
    Fine,
    Loan,
    LoanPolicy,
    Member,
    Reservation,
    Title,
    iso,
)

MODULE = "library"
CATALOGUE_READ = "library:catalogue:read"
CATALOGUE_MANAGE = "library:catalogue:manage"
MEMBER_MANAGE = "library:member:manage"
POLICY_MANAGE = "library:policy:manage"
CIRCULATION_MANAGE = "library:circulation:manage"
FINE_MANAGE = "library:fine:manage"
SELF_READ = "library:self:read"
SELF_BORROW = "library:self:borrow"

# Domain rule code -> HTTP status. Refusals (the contract's Refusal codes) are always 409.
RULE_STATUS = {"invalid_amount": 422}


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


class LibraryError(Exception):
    """A refusal with an HTTP status and an error body ({code, message})."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def body(self) -> dict:
        return {"code": self.code, "message": self.message}


def _not_found(what: str) -> LibraryError:
    return LibraryError(404, "not_found", f"{what} not found in your organisation")


def _conflict(code: str, message: str) -> LibraryError:
    return LibraryError(409, code, message)


def _flush_unique(db: Session, code: str, message: str) -> None:
    """Write now, so a duplicate that slipped past the check (two requests at once) is a 409, not a 500."""
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _conflict(code, message) from None


def _rule(v: RuleViolationError) -> LibraryError:
    if isinstance(v, RefusedError):
        return LibraryError(409, v.code, v.message)
    return LibraryError(RULE_STATUS.get(v.code, 422), v.code, v.message)


def _audit(db: Session, actor: Actor | None, action: str, entity: str, entity_id: str, organisation_id: str) -> None:
    db.add(
        AuditEntry(
            organisation_id=organisation_id,
            actor=actor.user_id if actor else None,
            action=action,
            entity=entity,
            entity_id=entity_id,
            occurred_at=clock(),
        )
    )


def _publish(db: Session, actor: Actor | None, name: str, organisation_id: str, payload: dict) -> None:
    events.publish(
        db,
        f"{MODULE}.{name}",
        organisation_id,
        {"organisation_id": organisation_id, **payload},
        actor=actor.user_id if actor else None,
    )


def _get(db: Session, model, row_id: str, what: str):
    row = repo.get(db, model, row_id)
    if row is None:
        raise _not_found(what)
    return row


def _amount(text: str) -> Decimal:
    try:
        return rules.parse_money(text)
    except RuleViolationError as v:
        raise _rule(v) from v


# ---------------------------------------------------------------- policies


def _policy(row: LoanPolicy | None) -> Policy | None:
    if row is None:
        return None
    return Policy(
        max_loans=row.max_loans,
        loan_days=row.loan_days,
        max_renewals=row.max_renewals,
        fine_per_day=money(row.fine_per_day),
        max_unpaid_fines=money(row.max_unpaid_fines),
        hold_days=row.hold_days,
    )


def _policy_of(db: Session, person_id: str, organisation_id: str | None = None) -> Policy | None:
    """The member's loan policy. organisation_id pins it when called from a job in platform scope."""
    m = repo.member(db, person_id, organisation_id)
    return _policy(repo.policy_for(db, m.category, organisation_id)) if m else None


# ---------------------------------------------------------------- serialisation


def title_dict(db: Session, t: Title, copies: list[Copy] | None = None) -> dict:
    copies = copies if copies is not None else repo.copies_of(db, [t.id])
    return {
        "id": t.id,
        "organisation_id": t.organisation_id,
        "isbn": t.isbn,
        "title": t.title,
        "authors": list(t.authors or []),
        "publisher": t.publisher,
        "year": t.year,
        "subjects": list(t.subjects or []),
        "kind": t.kind,
        "copies_total": sum(1 for c in copies if c.status != "withdrawn"),
        "copies_available": sum(1 for c in copies if c.status == "available"),
    }


def copy_dict(c: Copy) -> dict:
    return {
        "id": c.id,
        "organisation_id": c.organisation_id,
        "title_id": c.title_id,
        "accession_no": c.accession_no,
        "barcode": c.barcode,
        "location": c.location,
        "status": c.status,
    }


def policy_dict(p: LoanPolicy) -> dict:
    return {
        "member_category": p.member_category,
        "max_loans": p.max_loans,
        "loan_days": p.loan_days,
        "max_renewals": p.max_renewals,
        "fine_per_day": money_str(p.fine_per_day),
        "max_unpaid_fines": money_str(p.max_unpaid_fines),
        "hold_days": p.hold_days,
    }


def member_dict(m: Member) -> dict:
    return {
        "organisation_id": m.organisation_id,
        "person_id": m.person_id,
        "person_name": m.person_name,
        "category": m.category,
        "blocked": m.blocked,
        "block_reason": m.block_reason,
    }


def loan_dict(db: Session, loan: Loan) -> dict:
    """Accrued fine and renewals left follow the loan's own rate and limit, not today's policy."""
    title = repo.get(db, Title, loan.title_id)
    active = loan.status == "active"
    overdue = active and loan.due_on < today()
    accrued = rules.overdue_fine(loan.due_on, today(), loan.fine_per_day) if overdue else money(0)
    return {
        "id": loan.id,
        "organisation_id": loan.organisation_id,
        "copy_id": loan.copy_id,
        "title_id": loan.title_id,
        "title": title.title if title else None,
        "person_id": loan.person_id,
        "issued_at": iso(loan.issued_at),
        "due_on": iso(loan.due_on),
        "returned_at": iso(loan.returned_at),
        "renewals": loan.renewals,
        "renewals_left": max(0, loan.max_renewals - loan.renewals),
        "status": loan.status,
        "overdue": overdue,
        "fine_accrued": money_str(accrued),
    }


def reservation_dict(db: Session, r: Reservation) -> dict:
    title = repo.get(db, Title, r.title_id)
    position = None
    if r.status == "waiting":
        queue = [x.id for x in repo.waiting_queue(db, r.title_id)]
        position = queue.index(r.id) + 1 if r.id in queue else None
    return {
        "id": r.id,
        "organisation_id": r.organisation_id,
        "title_id": r.title_id,
        "title": title.title if title else None,
        "person_id": r.person_id,
        "status": r.status,
        "position": position,
        "held_copy_id": r.held_copy_id,
        "hold_expires_on": iso(r.hold_expires_on),
        "placed_at": iso(r.placed_at),
    }


def fine_dict(f: Fine) -> dict:
    return {
        "id": f.id,
        "organisation_id": f.organisation_id,
        "person_id": f.person_id,
        "loan_id": f.loan_id,
        "reason": f.reason,
        "amount": money_str(f.amount),
        "status": f.status,
        "receipt_ref": f.receipt_ref,
        "waive_reason": f.waive_reason,
        "raised_at": iso(f.raised_at),
    }


def digital_dict(d: DigitalResource) -> dict:
    return {
        "id": d.id,
        "organisation_id": d.organisation_id,
        "title": d.title,
        "provider": d.provider,
        "kind": d.kind,
        "url": d.url,
        "access": d.access,
        "active": d.active,
    }


def _page(items: list[dict], next_cursor: str | None) -> dict:
    return {"items": items, "next_cursor": next_cursor}


# ---------------------------------------------------------------- catalogue


def list_titles(
    db: Session, q: str | None, kind: str | None, available: bool | None, cursor: str | None, limit: int
) -> dict:
    query = repo.titles_query(db, q, kind)
    if available is None:
        rows, nxt = repo.page(db, query, cursor, limit)
        copies = repo.copies_of(db, [t.id for t in rows])
        return _page([title_dict(db, t, [c for c in copies if c.title_id == t.id]) for t in rows], nxt)
    # The available filter depends on the copies, so it is applied before paging.
    rows = list(db.scalars(query))
    copies = repo.copies_of(db, [t.id for t in rows])
    items = [title_dict(db, t, [c for c in copies if c.title_id == t.id]) for t in rows]
    items = [i for i in items if (i["copies_available"] > 0) == available]
    offset = repo.decode_cursor(cursor)
    chunk = items[offset : offset + limit]
    nxt = repo.encode_cursor(offset + limit) if len(items) > offset + limit else None
    return _page(chunk, nxt)


def get_title(db: Session, title_id: str) -> dict:
    t = _get(db, Title, title_id, "title")
    copies = repo.copies_of(db, [t.id])
    return {
        **title_dict(db, t, copies),
        "copies": [copy_dict(c) for c in copies],
        "reservations_waiting": len(repo.waiting_queue(db, t.id)),
    }


def create_title(db: Session, actor: Actor, data: dict) -> dict:
    if data.get("isbn") and repo.title_by_isbn(db, data["isbn"]):
        raise _conflict("isbn_exists", f"ISBN {data['isbn']} is already catalogued")
    t = Title(
        organisation_id=actor.organisation_id,
        isbn=data.get("isbn"),
        title=data["title"],
        authors=list(data.get("authors") or []),
        publisher=data.get("publisher"),
        year=data.get("year"),
        subjects=list(data.get("subjects") or []),
        kind=data["kind"],
    )
    db.add(t)
    db.flush()
    _audit(db, actor, "title.created", "title", t.id, actor.organisation_id)
    db.commit()
    return title_dict(db, t, [])


def update_title(db: Session, actor: Actor, title_id: str, data: dict) -> dict:
    t = _get(db, Title, title_id, "title")
    if data.get("isbn") and data["isbn"] != t.isbn:
        other = repo.title_by_isbn(db, data["isbn"])
        if other is not None and other.id != t.id:
            raise _conflict("isbn_exists", f"ISBN {data['isbn']} is already catalogued")
    for key in ("isbn", "title", "publisher", "year", "kind"):
        if key in data and data[key] is not None:
            setattr(t, key, data[key])
    for key in ("authors", "subjects"):
        if data.get(key) is not None:
            setattr(t, key, list(data[key]))
    _audit(db, actor, "title.updated", "title", t.id, t.organisation_id)
    db.commit()
    return title_dict(db, t)


def add_copy(db: Session, actor: Actor, title_id: str, data: dict) -> dict:
    t = _get(db, Title, title_id, "title")
    if repo.copy_by(db, accession_no=data["accession_no"]) or repo.copy_by(db, barcode=data["barcode"]):
        raise _conflict("copy_exists", "the accession number or barcode is already used")
    c = Copy(
        organisation_id=actor.organisation_id,
        title_id=t.id,
        accession_no=data["accession_no"],
        barcode=data["barcode"],
        location=data.get("location"),
        status="available",
    )
    db.add(c)
    _flush_unique(db, "copy_exists", "the accession number or barcode is already used")
    _audit(db, actor, "copy.created", "copy", c.id, actor.organisation_id)
    _hold_or_release(db, actor, c)  # someone may already be waiting for this title
    db.commit()
    return copy_dict(c)


def update_copy(db: Session, actor: Actor, copy_id: str, data: dict) -> dict:
    c = repo.copy_for_update(db, copy_id=copy_id)
    if c is None:
        raise _not_found("copy")
    if data.get("location") is not None:
        c.location = data["location"]
    if data.get("withdrawn") is True and c.status != "withdrawn":
        if c.status in ("on-loan", "on-hold"):
            raise _conflict("copy_on_loan", f"the copy is {c.status} and cannot be withdrawn")
        c.status, c.withdraw_reason = "withdrawn", data.get("reason")
        _audit(db, actor, "copy.withdrawn", "copy", c.id, c.organisation_id)
    elif data.get("withdrawn") is False and c.status == "withdrawn":
        c.status, c.withdraw_reason = "available", None
        _audit(db, actor, "copy.restored", "copy", c.id, c.organisation_id)
        _hold_or_release(db, actor, c)
    _audit(db, actor, "copy.updated", "copy", c.id, c.organisation_id)
    db.commit()
    return copy_dict(c)


# ---------------------------------------------------------------- members and policies


def list_members(db: Session, q: str | None, blocked: bool | None, cursor: str | None, limit: int) -> dict:
    rows, nxt = repo.page(db, repo.members_query(db, q, blocked), cursor, limit)
    return _page([member_dict(m) for m in rows], nxt)


def add_member(db: Session, actor: Actor, data: dict) -> dict:
    if repo.member(db, data["person_id"]):
        raise _conflict("already_member", "the person is already a member")
    m = Member(
        organisation_id=actor.organisation_id,
        person_id=data["person_id"],
        person_name=data.get("person_name"),
        category=data["category"],
        blocked=False,
    )
    db.add(m)
    _flush_unique(db, "already_member", "the person is already a member")
    _audit(db, actor, "member.added", "member", m.id, actor.organisation_id)
    db.commit()
    return member_dict(m)


def _member_or_404(db: Session, person_id: str) -> Member:
    m = repo.member(db, person_id)
    if m is None:
        raise LibraryError(404, "not_found", "the person is not a member in your organisation")
    return m


def get_member(db: Session, person_id: str) -> dict:
    m = _member_or_404(db, person_id)
    return {
        **member_dict(m),
        "loans": [loan_dict(db, loan) for loan in repo.active_loans_of(db, person_id)],
        "open_fines_total": money_str(repo.open_fines_total(db, person_id)),
    }


def update_member(db: Session, actor: Actor, person_id: str, data: dict) -> dict:
    m = _member_or_404(db, person_id)
    if data.get("category") is not None:
        m.category = data["category"]
    if data.get("blocked") is True and not m.blocked:
        reason = (data.get("reason") or "").strip()
        if len(reason) < 3:
            raise LibraryError(422, "reason_required", "a reason of at least 3 characters is required to block")
        m.blocked, m.block_reason = True, reason
        _publish(db, actor, "member.blocked", m.organisation_id, {"person_id": m.person_id, "reason": reason})
        _audit(db, actor, "member.blocked", "member", m.id, m.organisation_id)
    elif data.get("blocked") is False and m.blocked:
        m.blocked, m.block_reason = False, None
        _audit(db, actor, "member.unblocked", "member", m.id, m.organisation_id)
    _audit(db, actor, "member.updated", "member", m.id, m.organisation_id)
    db.commit()
    return member_dict(m)


def list_policies(db: Session) -> list[dict]:
    return [policy_dict(p) for p in repo.policies(db)]


def replace_policies(db: Session, actor: Actor, entries: list[dict]) -> list[dict]:
    categories = [e["member_category"] for e in entries]
    if len(set(categories)) != len(categories):
        raise LibraryError(422, "duplicate_category", "each member category may have one policy")
    parsed = {e["member_category"]: (e, _amount(e["fine_per_day"]), _amount(e["max_unpaid_fines"])) for e in entries}
    existing = {p.member_category: p for p in repo.policies(db)}
    for category, row in existing.items():
        if category not in parsed:
            db.delete(row)  # loan policies are configuration, replaced as a whole (PUT)
    for category, (e, fine, limit) in parsed.items():
        row = existing.get(category) or LoanPolicy(organisation_id=actor.organisation_id, member_category=category)
        row.max_loans, row.loan_days, row.max_renewals = e["max_loans"], e["loan_days"], e["max_renewals"]
        row.fine_per_day, row.max_unpaid_fines, row.hold_days = fine, limit, e["hold_days"]
        if category not in existing:
            db.add(row)
    _flush_unique(db, "policies_changed", "the loan policies changed at the same moment; send them again")
    _audit(db, actor, "policies.replaced", "loan_policy", actor.organisation_id, actor.organisation_id)
    db.commit()
    return list_policies(db)


# ---------------------------------------------------------------- circulation


def list_loans(
    db: Session, status: str | None, overdue: bool | None, person_id: str | None, cursor: str | None, limit: int
) -> dict:
    rows, nxt = repo.page(db, repo.loans_query(db, today(), status, overdue, person_id), cursor, limit)
    return _page([loan_dict(db, loan) for loan in rows], nxt)


def _raise_fine(db: Session, actor: Actor | None, loan: Loan, reason: str, amount: Decimal) -> Fine | None:
    if money(amount) <= 0:
        return None
    f = Fine(
        organisation_id=loan.organisation_id,
        person_id=loan.person_id,
        loan_id=loan.id,
        reason=reason,
        amount=money(amount),
        status="open",
        raised_at=clock(),
    )
    db.add(f)
    db.flush()
    _publish(
        db,
        actor,
        "fine.raised",
        f.organisation_id,
        {
            "fine_id": f.id,
            "person_id": f.person_id,
            "loan_id": loan.id,
            "reason": reason,
            "amount": money_str(f.amount),
        },
    )
    _audit(db, actor, "fine.raised", "fine", f.id, f.organisation_id)
    return f


def _hold_or_release(db: Session, actor: Actor | None, c: Copy) -> Reservation | None:
    """A copy that came back (or was added) goes on hold for the first member waiting for its title, else it is
    available. Returns the reservation now ready, if any."""
    for r in repo.waiting_queue(db, c.title_id):
        policy = _policy_of(db, r.person_id, c.organisation_id)
        hold_days = policy.hold_days if policy else rules.DEFAULT_HOLD_DAYS
        r.status, r.held_copy_id = "ready", c.id
        r.hold_expires_on = rules.hold_expiry(today(), hold_days)
        c.status = "on-hold"
        _publish(
            db,
            actor,
            "reservation.ready",
            r.organisation_id,
            {
                "reservation_id": r.id,
                "person_id": r.person_id,
                "title_id": r.title_id,
                "copy_id": c.id,
                "hold_expires_on": iso(r.hold_expires_on),
            },
        )
        _audit(db, actor, "reservation.ready", "reservation", r.id, r.organisation_id)
        return r
    c.status = "available"
    return None


def issue(db: Session, actor: Actor, barcode: str, person_id: str) -> dict:
    c = repo.copy_for_update(db, barcode=barcode)
    if c is None:
        raise _not_found("copy with that barcode")
    m = repo.member(db, person_id, lock=True)
    policy = _policy(repo.policy_for(db, m.category)) if m else None
    held = repo.ready_reservation_for_copy(db, c.id) if c.status == "on-hold" else None
    try:
        rules.check_issue(
            is_member=m is not None,
            blocked=bool(m and m.blocked),
            policy=policy,
            active_loans=len(repo.active_loans_of(db, person_id)),
            unpaid_fines=repo.open_fines_total(db, person_id),
            copy_status=c.status,
            held_for=held.person_id if held else None,
            person_id=person_id,
        )
    except RuleViolationError as v:
        raise _rule(v) from v
    if held is not None:
        held.status, held.resolved_at = "fulfilled", clock()
        _audit(db, actor, "reservation.fulfilled", "reservation", held.id, held.organisation_id)
    loan = Loan(
        organisation_id=actor.organisation_id,
        copy_id=c.id,
        title_id=c.title_id,
        person_id=person_id,
        issued_at=clock(),
        issued_by=actor.user_id,
        due_on=rules.due_date(today(), policy.loan_days),
        renewals=0,
        fine_per_day=policy.fine_per_day,
        max_renewals=policy.max_renewals,
        status="active",
    )
    c.status = "on-loan"
    db.add(loan)
    db.flush()
    _publish(
        db,
        actor,
        "loan.issued",
        loan.organisation_id,
        {
            "loan_id": loan.id,
            "person_id": person_id,
            "title_id": loan.title_id,
            "copy_id": c.id,
            "due_on": iso(loan.due_on),
        },
    )
    _audit(db, actor, "loan.issued", "loan", loan.id, loan.organisation_id)
    db.commit()
    return loan_dict(db, loan)


def return_copy(db: Session, actor: Actor, barcode: str, damage_note: str | None) -> dict:
    c = repo.copy_for_update(db, barcode=barcode)
    if c is None:
        raise _not_found("copy with that barcode")
    loan = repo.active_loan_for_copy(db, c.id)
    if loan is None:
        raise _conflict("not_on_loan", "the copy is not on loan")
    late = rules.days_late(loan.due_on, today())
    loan.status, loan.returned_at, loan.damage_note = "returned", clock(), damage_note
    _publish(
        db,
        actor,
        "loan.returned",
        loan.organisation_id,
        {
            "loan_id": loan.id,
            "person_id": loan.person_id,
            "copy_id": c.id,
            "returned_at": iso(loan.returned_at),
            "days_late": late,
        },
    )
    _audit(db, actor, "loan.returned", "loan", loan.id, loan.organisation_id)
    fine = None
    if late:
        fine = _raise_fine(db, actor, loan, "overdue", rules.overdue_fine(loan.due_on, today(), loan.fine_per_day))
    held = _hold_or_release(db, actor, c)
    db.commit()
    return {
        "loan": loan_dict(db, loan),
        "fine": fine_dict(fine) if fine else None,
        "held_for_reservation": reservation_dict(db, held) if held else None,
    }


def renew(db: Session, actor: Actor, loan_id: str) -> dict:
    loan = _get(db, Loan, loan_id, "loan")
    if not actor.can(CIRCULATION_MANAGE) and loan.person_id != actor.user_id:
        raise _not_found("loan")  # library:self:borrow covers the caller's own loans only
    if loan.status != "active":
        raise _conflict("not_active", f"cannot renew a loan that is {loan.status}")
    policy = _policy_of(db, loan.person_id)
    if policy is None:
        raise _rule(RefusedError(rules.NO_RENEWALS_LEFT, "there is no loan policy for the member's category"))
    try:
        rules.check_renew(
            renewals=loan.renewals,
            policy=replace(policy, max_renewals=loan.max_renewals),  # the limit the loan was issued with
            someone_waiting=bool(repo.waiting_queue(db, loan.title_id)),
        )
    except RuleViolationError as v:
        raise _rule(v) from v
    if loan.due_on < today():
        # Renewing late must not erase the fine for the days already late.
        _raise_fine(db, actor, loan, "overdue", rules.overdue_fine(loan.due_on, today(), loan.fine_per_day))
    loan.renewals += 1
    loan.fine_per_day = policy.fine_per_day  # a renewal takes the current rate
    loan.due_on = max(loan.due_on, rules.due_date(today(), policy.loan_days))
    loan.overdue_flagged_at = None
    _publish(
        db,
        actor,
        "loan.renewed",
        loan.organisation_id,
        {"loan_id": loan.id, "person_id": loan.person_id, "due_on": iso(loan.due_on), "renewals": loan.renewals},
    )
    _audit(db, actor, "loan.renewed", "loan", loan.id, loan.organisation_id)
    db.commit()
    return loan_dict(db, loan)


def mark_lost(db: Session, actor: Actor, loan_id: str, replacement_amount: str) -> dict:
    amount = _amount(replacement_amount)
    loan = _get(db, Loan, loan_id, "loan")
    if loan.status != "active":
        raise _conflict("not_active", f"cannot mark a loan lost that is {loan.status}")
    c = repo.copy_for_update(db, copy_id=loan.copy_id)
    loan.status = "lost"
    if c is not None:
        c.status = "lost"
    _publish(
        db,
        actor,
        "loan.lost",
        loan.organisation_id,
        {"loan_id": loan.id, "person_id": loan.person_id, "copy_id": loan.copy_id},
    )
    _audit(db, actor, "loan.lost", "loan", loan.id, loan.organisation_id)
    _raise_fine(db, actor, loan, "lost", amount)
    db.commit()
    return loan_dict(db, loan)


# ---------------------------------------------------------------- reservations


def list_reservations(db: Session, status: str | None, title_id: str | None, cursor: str | None, limit: int) -> dict:
    rows, nxt = repo.page(db, repo.reservations_query(db, status, title_id), cursor, limit)
    return _page([reservation_dict(db, r) for r in rows], nxt)


def reserve(db: Session, actor: Actor, title_id: str) -> dict:
    t = _get(db, Title, title_id, "title")
    if repo.member(db, actor.user_id) is None:
        raise _rule(RefusedError(rules.NOT_A_MEMBER, "you are not a library member"))
    if repo.first_available_copy(db, t.id) is not None:
        raise _conflict("copy_available", "a copy is available to borrow at the desk")
    if repo.active_reservation(db, actor.user_id, t.id) is not None:
        raise _conflict("already_reserved", "you have already reserved this title")
    r = Reservation(
        organisation_id=actor.organisation_id,
        title_id=t.id,
        person_id=actor.user_id,
        status="waiting",
        placed_at=clock(),
    )
    db.add(r)
    _flush_unique(db, "already_reserved", "you have already reserved this title")
    out = reservation_dict(db, r)
    _publish(
        db,
        actor,
        "reservation.placed",
        r.organisation_id,
        {"reservation_id": r.id, "person_id": r.person_id, "title_id": t.id, "position": out["position"]},
    )
    _audit(db, actor, "reservation.placed", "reservation", r.id, r.organisation_id)
    db.commit()
    return out


def cancel_reservation(db: Session, actor: Actor, reservation_id: str) -> dict:
    r = _get(db, Reservation, reservation_id, "reservation")
    if not actor.can(CIRCULATION_MANAGE) and r.person_id != actor.user_id:
        raise _not_found("reservation")
    if r.status not in rules.RESERVATION_ACTIVE:
        raise _conflict("invalid_status", f"the reservation is already {r.status}")
    held_copy = r.held_copy_id if r.status == "ready" else None
    r.status, r.resolved_at = "cancelled", clock()
    _audit(db, actor, "reservation.cancelled", "reservation", r.id, r.organisation_id)
    if held_copy:
        c = repo.copy_for_update(db, copy_id=held_copy)
        if c is not None and c.status == "on-hold":
            _hold_or_release(db, actor, c)  # the held copy goes to the next in the queue
    db.commit()
    return reservation_dict(db, r)


# ---------------------------------------------------------------- fines


def list_fines(db: Session, status: str | None, person_id: str | None, cursor: str | None, limit: int) -> dict:
    rows, nxt = repo.page(db, repo.fines_query(db, status, person_id), cursor, limit)
    return _page([fine_dict(f) for f in rows], nxt)


def _open_fine(db: Session, fine_id: str) -> Fine:
    f = _get(db, Fine, fine_id, "fine")
    if f.status != "open":
        raise _conflict("not_open", f"the fine is already {f.status}")
    return f


def _paid(db: Session, actor: Actor | None, f: Fine, receipt_ref: str) -> None:
    f.status, f.receipt_ref, f.settled_at = "paid", receipt_ref, clock()
    _publish(
        db,
        actor,
        "fine.paid",
        f.organisation_id,
        {"fine_id": f.id, "person_id": f.person_id, "amount": money_str(f.amount), "receipt_ref": receipt_ref},
    )
    _audit(db, actor, "fine.paid", "fine", f.id, f.organisation_id)


def pay_fine(db: Session, actor: Actor, fine_id: str, receipt_ref: str) -> dict:
    f = _open_fine(db, fine_id)
    _paid(db, actor, f, receipt_ref)
    db.commit()
    return fine_dict(f)


def waive_fine(db: Session, actor: Actor, fine_id: str, reason: str) -> dict:
    f = _open_fine(db, fine_id)
    f.status, f.waive_reason, f.waived_by, f.settled_at = "waived", reason, actor.user_id, clock()
    _publish(
        db,
        actor,
        "fine.waived",
        f.organisation_id,
        {"fine_id": f.id, "person_id": f.person_id, "amount": money_str(f.amount), "waived_by": actor.user_id},
    )
    _audit(db, actor, "fine.waived", "fine", f.id, f.organisation_id)
    db.commit()
    return fine_dict(f)


def fine_paid_through_fees(db: Session, fine_id: str, invoice_id: str) -> str:
    """fees-accounts invoiced the fine and it was paid there. Idempotent: an already settled fine is left as it is.
    Returns what happened."""
    f = repo.get(db, Fine, fine_id)
    if f is None:
        return "unknown fine"
    if f.status != "open":
        return f"fine already {f.status}"
    _paid(db, None, f, f"fees-accounts:{invoice_id}")
    db.commit()
    return "marked paid"


# ---------------------------------------------------------------- digital resources


def list_digital(db: Session, actor: Actor, q: str | None, kind: str | None) -> list[dict]:
    active_only = not actor.can(CATALOGUE_READ)  # members see what they can open; staff see everything
    return [digital_dict(d) for d in repo.digital_resources(db, q, kind, active_only)]


def create_digital(db: Session, actor: Actor, data: dict) -> dict:
    d = DigitalResource(
        organisation_id=actor.organisation_id,
        title=data["title"],
        provider=data.get("provider"),
        kind=data.get("kind"),
        url=data["url"],
        access=data["access"],
        active=data.get("active", True),
    )
    db.add(d)
    db.flush()
    _audit(db, actor, "digital_resource.created", "digital_resource", d.id, actor.organisation_id)
    db.commit()
    return digital_dict(d)


def update_digital(db: Session, actor: Actor, resource_id: str, data: dict) -> dict:
    d = _get(db, DigitalResource, resource_id, "digital resource")
    for key in ("title", "provider", "kind", "url", "access", "active"):
        if key in data and data[key] is not None:
            setattr(d, key, data[key])
    _audit(db, actor, "digital_resource.updated", "digital_resource", d.id, d.organisation_id)
    db.commit()
    return digital_dict(d)


# ---------------------------------------------------------------- the caller's own (/me)


def my_loans(db: Session, actor: Actor) -> list[dict]:
    return [loan_dict(db, loan) for loan in repo.active_loans_of(db, actor.user_id)]


def my_reservations(db: Session, actor: Actor) -> list[dict]:
    return [reservation_dict(db, r) for r in repo.my_reservations(db, actor.user_id)]


def my_fines(db: Session, actor: Actor) -> dict:
    fines = repo.open_fines_of(db, actor.user_id)
    return {"fines": [fine_dict(f) for f in fines], "total": money_str(sum((f.amount for f in fines), Decimal("0")))}
