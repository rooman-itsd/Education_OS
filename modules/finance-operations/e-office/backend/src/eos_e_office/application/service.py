"""Use cases of e-office. Authenticated calls arrive with the caller's organisation pinned on the session (api/deps).
Every state change writes an audit record and, where the contract defines one, publishes its e-office.* event to the
eos_core outbox in the same transaction. Note text never goes into an event, and a confidential file's subject is
never published (decided by the owner; see #336).

Visibility: a file is visible to everyone who has held it (e_office_file_holder). With e-office:file:read-all every
non-confidential file is visible too; a confidential file stays visible to its holders only. A file the caller cannot
see answers 404, exactly like one that does not exist. Only the current holder of an open file notes, attaches,
forwards, decides, closes and requests dispatch; anyone else who can see it gets 409."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from functools import wraps

from eos_core import events
from eos_core.db import scoped, utcnow
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import RuleError
from ..infrastructure.config import load_settings
from ..infrastructure.models import (
    Attachment,
    AuditEntry,
    Category,
    Dispatch,
    File,
    FileHolder,
    Movement,
    Note,
    Receipt,
)
from .access import CORRESPONDENCE_MANAGE, FILE_READ_ALL, Actor
from .errors import EOfficeError, conflict, from_rule, invalid, not_found

MODULE = "e-office"
DECISION_LABEL = {"approved": "Approved", "rejected": "Rejected", "returned": "Returned for revision"}


def clock() -> datetime:
    """Now, in UTC. Tests replace it."""
    return utcnow()


# Business dates are Indian (decided by the owner; see #336). Asia/Kolkata has kept UTC+05:30 without daylight saving
# since 1945, so a fixed offset is exact and needs no time-zone database (tzdata is not on the approved stack).
BUSINESS_TZ = timezone(timedelta(hours=5, minutes=30), "Asia/Kolkata")


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def business_date(moment: datetime) -> date:
    """The Indian calendar date of a moment; timestamps themselves stay UTC."""
    return _aware(moment).astimezone(BUSINESS_TZ).date()


def business_today() -> date:
    """Today in Asia/Kolkata: the date due dates, overdue and "not in the future" are judged against."""
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
    if isinstance(value, datetime):
        value = _aware(value)
    return value.isoformat()


def _offset(cursor: str | None) -> int:
    try:
        value = int(cursor) if cursor else 0
    except ValueError as e:
        raise EOfficeError(400, "invalid_cursor", "invalid cursor") from e
    if value < 0:
        raise EOfficeError(400, "invalid_cursor", "invalid cursor")
    return value


def _page(rows: list, cursor: str | None, limit: int, render) -> dict:
    offset = _offset(cursor)
    chunk = rows[offset : offset + limit]
    return {
        "items": [render(r) for r in chunk],
        "next_cursor": str(offset + limit) if len(rows) > offset + limit else None,
    }


def _duplicate_is_409(code: str, message: str):
    """A write that takes a unique value (a file, receipt or dispatch number, a category code, a note's paragraph
    number). When a concurrent request took the same value after the checks, the database refuses it at a flush or at
    the commit; either way the answer is 409, and nothing is kept."""

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


def _lock(db: Session, key: str) -> None:
    """On Postgres a transaction-level advisory lock per organisation and key makes concurrent writers of the same
    running number take turns, as procurement does; the unique constraints still answer 409 if anything slips past."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"e-office:{key}:{db.info.get('organisation_id', '')}"},
        )


def _text(value: str | None) -> str:
    return (value or "").strip()


def _required(value: str | None, field: str) -> str:
    out = _text(value)
    if not out:
        raise invalid(f"invalid_{field}", f"{field} is required", field)
    return out


def user_ref(user_id: str | None) -> dict | None:
    """A platform/identity user. Names and designations are not available to modules yet, so they are empty."""
    if user_id is None:
        return None
    return {"user_id": user_id, "name": "", "designation": None}


# ---------------------------------------------------------------- categories


def category_dict(c: Category) -> dict:
    return {
        "id": c.id,
        "organisation_id": c.organisation_id,
        "code": c.code,
        "name": c.name,
        "retention_years": c.retention_years,
        "active": c.active,
    }


def list_categories(db: Session) -> list[dict]:
    return [category_dict(c) for c in db.scalars(_q(db, Category).order_by(Category.code, Category.id))]


def _category_values(db: Session, c: Category, body: dict) -> None:
    code = _rule(rules.category_code, body["code"])
    q = _q(db, Category).where(Category.code == code)
    if c.id:
        q = q.where(Category.id != c.id)
    if db.scalar(q) is not None:
        raise conflict("category_exists", f"a category with code {code} exists")
    c.code = code
    c.name = _required(body["name"], "name")
    c.retention_years = body.get("retention_years")
    c.active = True if body.get("active") is None else bool(body["active"])


@_duplicate_is_409("category_exists", "a category with this code exists")
def create_category(db: Session, actor: Actor, body: dict) -> dict:
    c = Category(organisation_id=actor.organisation_id)
    _category_values(db, c, body)
    db.add(c)
    _audit(db, actor.user_id, "category.created", "category", c)
    db.commit()
    return category_dict(c)


@_duplicate_is_409("category_exists", "a category with this code exists")
def update_category(db: Session, actor: Actor, category_id: str, body: dict) -> dict:
    """Existing file numbers keep the code they were given; a new code applies to files opened from now on."""
    c = _get(db, Category, category_id, "category", lock=True)
    _category_values(db, c, body)
    _audit(db, actor.user_id, "category.updated", "category", c)
    db.commit()
    return category_dict(c)


# ---------------------------------------------------------------- visibility


def _held_ids(db: Session, user_id: str):
    return scoped(db, select(FileHolder.file_id), FileHolder).where(FileHolder.user_id == user_id)


def _visible(db: Session, actor: Actor, q):
    """Restrict a File query to the files the caller may see."""
    seen = File.id.in_(_held_ids(db, actor.user_id))
    if actor.can(FILE_READ_ALL):
        return q.where(or_(seen, File.confidential.is_(False)))
    return q.where(seen)


def _visible_file(db: Session, actor: Actor, file_id: str, *, lock: bool = False) -> File:
    q = _visible(db, actor, _q(db, File).where(File.id == file_id))
    if lock:
        q = q.with_for_update()
    f = db.scalar(q)
    if f is None:
        raise not_found("file")
    return f


def _held_file(db: Session, actor: Actor, file_id: str) -> File:
    """An open file the caller holds, locked so two actions on it take turns."""
    f = _visible_file(db, actor, file_id, lock=True)
    if f.status == "closed":
        raise conflict("file_closed", f"file {f.number} is closed")
    if f.holder_id != actor.user_id:
        raise conflict("not_holder", f"you do not hold file {f.number}")
    return f


def _add_holder(db: Session, f: File, user_id: str, at: datetime) -> None:
    q = scoped(db, select(FileHolder.id), FileHolder).where(FileHolder.file_id == f.id, FileHolder.user_id == user_id)
    if db.scalar(q) is None:
        db.add(FileHolder(organisation_id=f.organisation_id, file_id=f.id, user_id=user_id, first_held_at=at))
        db.flush()


# ---------------------------------------------------------------- rendering


def _due(f: File, days: dict[str, int]) -> date:
    return rules.due_date(f.due_on, business_date(f.held_since), f.priority, days)


def _overdue(f: File, today: date, days: dict[str, int]) -> bool:
    return f.status == "open" and rules.is_overdue(_due(f, days), today)


def file_summary(f: File, today: date, days: dict[str, int]) -> dict:
    return {
        "id": f.id,
        "organisation_id": f.organisation_id,
        "number": f.number,
        "subject": f.subject,
        "category_id": f.category_id,
        "department_id": f.department_id,
        "priority": f.priority,
        "confidential": f.confidential,
        "status": f.status,
        "holder": user_ref(f.holder_id),
        "held_since": _iso(f.held_since),
        "action_required": f.action_required,
        "due_on": _iso(f.due_on),
        "overdue": _overdue(f, today, days),
    }


def _summaries():
    today, days = business_today(), load_settings().default_due_days
    return lambda f: file_summary(f, today, days)


def note_dict(n: Note) -> dict:
    return {
        "id": n.id,
        "sequence": n.sequence,
        "kind": n.kind,
        "text": n.text,
        "author": user_ref(n.author_id),
        "attachment_ids": list(n.attachment_ids or []),
        "created_at": _iso(n.created_at),
    }


def attachment_dict(a: Attachment) -> dict:
    return {
        "id": a.id,
        "document_id": a.document_id,
        "title": a.title,
        "kind": a.kind,
        "receipt_id": a.receipt_id,
        "added_by": user_ref(a.added_by),
        "added_at": _iso(a.created_at),
    }


def _notes(db: Session, file_id: str) -> list[Note]:
    return list(db.scalars(_q(db, Note).where(Note.file_id == file_id).order_by(Note.sequence)))


def _attachments(db: Session, file_id: str) -> list[Attachment]:
    q = _q(db, Attachment).where(Attachment.file_id == file_id)
    return list(db.scalars(q.order_by(Attachment.created_at, Attachment.id)))


def file_dict(db: Session, f: File) -> dict:
    out = file_summary(f, business_today(), load_settings().default_due_days)
    out.update(
        {
            "created_by": user_ref(f.created_by),
            "last_decision": f.last_decision,
            "notes": [note_dict(n) for n in _notes(db, f.id)],
            "attachments": [attachment_dict(a) for a in _attachments(db, f.id)],
            "created_at": _iso(f.created_at),
            "closed_at": _iso(f.closed_at),
        }
    )
    return out


def movement_dict(m: Movement) -> dict:
    return {
        "id": m.id,
        "kind": m.kind,
        "from": user_ref(m.from_user_id),
        "to": user_ref(m.to_user_id),
        "remark": m.remark,
        "action_required": m.action_required,
        "due_on": _iso(m.due_on),
        "at": _iso(m.at),
        "held_for_hours": round(m.held_seconds / 3600, 2),
    }


# ---------------------------------------------------------------- the note sheet and movements


def _add_note(db: Session, f: File, author_id: str, kind: str, body: str, attachment_ids: list[str] = ()) -> Note:
    """Append a numbered paragraph. The file row is locked by the caller, so numbers are taken in turn."""
    last = db.scalar(scoped(db, select(func.max(Note.sequence)), Note).where(Note.file_id == f.id)) or 0
    note = Note(
        organisation_id=f.organisation_id,
        file_id=f.id,
        sequence=last + 1,
        kind=kind,
        text=body,
        author_id=author_id,
        attachment_ids=list(attachment_ids),
        created_at=clock(),
    )
    db.add(note)
    db.flush()  # the session does not autoflush: the next paragraph in this transaction must see this one
    return note


def _move(db: Session, f: File, kind: str, to_user_id: str, at: datetime, **fields) -> Movement:
    """One line of the movement history. `held_seconds` is how long the sender had held the file."""
    held = 0
    if kind in ("forwarded", "decided", "closed"):
        held = max(int((_aware(at) - _aware(f.held_since)).total_seconds()), 0)
    last = db.scalar(scoped(db, select(func.max(Movement.sequence)), Movement).where(Movement.file_id == f.id)) or 0
    m = Movement(
        organisation_id=f.organisation_id,
        file_id=f.id,
        sequence=last + 1,
        kind=kind,
        to_user_id=to_user_id,
        held_seconds=held,
        at=at,
        from_user_id=fields.get("from_user_id"),
        remark=fields.get("remark"),
        action_required=fields.get("action_required"),
        due_on=fields.get("due_on"),
    )
    db.add(m)
    db.flush()  # a second movement in the same step must see this one
    return m


def _file_attachment_ids(db: Session, file_id: str) -> set[str]:
    q = scoped(db, select(Attachment.id), Attachment).where(Attachment.file_id == file_id)
    return set(db.scalars(q))


def _next_file_number(db: Session, c: Category, year: int) -> tuple[int, str]:
    _lock(db, f"file-number:{c.id}:{year}")
    q = scoped(db, select(func.max(File.sequence)), File).where(File.category_id == c.id, File.year == year)
    sequence = (db.scalar(q) or 0) + 1
    return sequence, rules.file_number(c.code, year, sequence)


def _next_register_number(db: Session, model, prefix: str, year: int) -> str:
    """The next inward (IN) or outward (OUT) register number of the organisation this year. Rows are never deleted,
    so the count is stable."""
    _lock(db, f"{model.__tablename__}:{year}")
    q = scoped(db, select(func.count()).select_from(model), model).where(model.number.like(f"{prefix}/{year}/%"))
    return rules.register_number(prefix, year, (db.scalar(q) or 0) + 1)


# ---------------------------------------------------------------- files


def list_files(db: Session, actor: Actor, filters: dict, cursor: str | None, limit: int) -> dict:
    q = _visible(db, actor, _q(db, File))
    for key in ("status", "category_id", "department_id"):
        if filters.get(key):
            q = q.where(getattr(File, key) == filters[key])
    if filters.get("holder_id"):
        q = q.where(File.holder_id == filters["holder_id"])
    needle = _text(filters.get("q")).lower()
    if needle:
        q = q.where(or_(func.lower(File.number).contains(needle), func.lower(File.subject).contains(needle)))
    rows = list(db.scalars(q.order_by(File.created_at.desc(), File.number.desc())))
    return _page(rows, cursor, limit, _summaries())


def get_file(db: Session, actor: Actor, file_id: str) -> dict:
    return file_dict(db, _visible_file(db, actor, file_id))


def _active_category(db: Session, category_id: str) -> Category:
    c = db.scalar(_q(db, Category).where(Category.id == category_id))
    if c is None:
        raise invalid("unknown_category", "the category does not exist in your organisation", "category_id")
    if not c.active:
        raise invalid("inactive_category", f"category {c.code} is no longer in use", "category_id")
    return c


@_duplicate_is_409("number_taken", "another request took the same number; try again")
def create_file(db: Session, actor: Actor, body: dict) -> dict:
    """Open a file held by its creator. With `receipt_id`, the receipt sent to the caller is attached to it."""
    c = _active_category(db, body["category_id"])
    subject = _required(body["subject"], "subject")
    receipt = _receivable(db, actor, body["receipt_id"]) if body.get("receipt_id") else None
    now = clock()
    year = business_date(now).year
    sequence, number = _next_file_number(db, c, year)
    f = File(
        organisation_id=actor.organisation_id,
        number=number,
        year=year,
        sequence=sequence,
        subject=subject,
        category_id=c.id,
        department_id=body.get("department_id"),
        priority=body.get("priority") or "normal",
        confidential=bool(body.get("confidential")),
        status="open",
        created_by=actor.user_id,
        holder_id=actor.user_id,
        held_since=now,
        created_at=now,
    )
    db.add(f)
    db.flush()
    _add_holder(db, f, actor.user_id, now)
    _move(db, f, "created", actor.user_id, now)
    if _text(body.get("first_note")):
        _add_note(db, f, actor.user_id, "noting", _text(body["first_note"]))
    if receipt is not None:
        _attach_receipt(db, actor, receipt, f, now)
    _publish(
        db,
        "file.created",
        f.organisation_id,
        {
            "file_id": f.id,
            "number": f.number,
            "category_id": f.category_id,
            "department_id": f.department_id,
            "created_by": f.created_by,
            "confidential": f.confidential,
        },
        actor.user_id,
    )
    _audit(db, actor.user_id, "file.created", "file", f)
    db.commit()
    return file_dict(db, f)


@_duplicate_is_409("concurrent_change", "the file changed at the same moment; try again")
def add_note(db: Session, actor: Actor, file_id: str, body: dict) -> dict:
    f = _held_file(db, actor, file_id)
    words = _required(body["text"], "text")
    refs = list(dict.fromkeys(body.get("attachment_ids") or []))
    if set(refs) - _file_attachment_ids(db, f.id):
        raise invalid("unknown_attachment", "a noting can refer only to this file's attachments", "attachment_ids")
    note = _add_note(db, f, actor.user_id, "noting", words, refs)
    _audit(db, actor.user_id, "file.noted", "file", f)
    db.commit()
    return note_dict(note)


def add_attachment(db: Session, actor: Actor, file_id: str, body: dict) -> dict:
    """Record a platform/documents id on the file. Nothing is uploaded here and the id is not checked against the
    documents service, which has no SDK yet."""
    f = _held_file(db, actor, file_id)
    a = Attachment(
        organisation_id=f.organisation_id,
        file_id=f.id,
        document_id=_required(body["document_id"], "document_id"),
        title=_required(body["title"], "title"),
        kind=body.get("kind") or "reference",
        added_by=actor.user_id,
        created_at=clock(),
    )
    db.add(a)
    _audit(db, actor.user_id, "file.attached", "file", f)
    db.commit()
    return attachment_dict(a)


def _forward(
    db: Session,
    actor: Actor,
    f: File,
    to_user_id: str,
    now: datetime,
    *,
    remark: str | None = None,
    action_required: str | None = None,
    due_on: date | None = None,
) -> None:
    """Hand the file to the next holder: a movement, a new holding (due date and overdue flag start again), the
    recipient added to the people who can see the file, and e-office.file.forwarded for notification."""
    to_user_id = _text(to_user_id)
    if not to_user_id:
        raise invalid("invalid_to_user_id", "to_user_id is required", "to_user_id")
    if to_user_id == actor.user_id:
        raise invalid("same_holder", "you already hold the file", "to_user_id")
    _rule(rules.not_in_past, due_on, business_today(), "due_on")
    action_required = _text(action_required) or None
    _move(
        db,
        f,
        "forwarded",
        to_user_id,
        now,
        from_user_id=actor.user_id,
        remark=_text(remark) or None,
        action_required=action_required,
        due_on=due_on,
    )
    f.holder_id, f.held_since = to_user_id, now
    f.action_required, f.due_on, f.overdue_flagged_at = action_required, due_on, None
    _add_holder(db, f, to_user_id, now)
    _publish(
        db,
        "file.forwarded",
        f.organisation_id,
        {
            "file_id": f.id,
            "number": f.number,
            "subject": "" if f.confidential else f.subject,
            "from_user_id": actor.user_id,
            "to_user_id": to_user_id,
            "action_required": action_required or "",
            "priority": f.priority,
            "due_on": _iso(due_on),
        },
        actor.user_id,
    )


@_duplicate_is_409("concurrent_change", "the file changed at the same moment; try again")
def forward_file(db: Session, actor: Actor, file_id: str, body: dict) -> dict:
    f = _held_file(db, actor, file_id)
    _forward(
        db,
        actor,
        f,
        body["to_user_id"],
        clock(),
        remark=body.get("remark"),
        action_required=body.get("action_required"),
        due_on=body.get("due_on"),
    )
    _audit(db, actor.user_id, "file.forwarded", "file", f)
    db.commit()
    return file_dict(db, f)


@_duplicate_is_409("concurrent_change", "the file changed at the same moment; try again")
def decide_file(db: Session, actor: Actor, file_id: str, body: dict) -> dict:
    """The competent authority's decision becomes a paragraph of the note sheet and a movement, and is published
    without its remark. With forward_to_user_id the file goes on to that person in the same step."""
    f = _held_file(db, actor, file_id)
    decision = body["decision"]
    remark = _required(body["remark"], "remark")
    now = clock()
    _add_note(db, f, actor.user_id, "decision", f"{DECISION_LABEL[decision]}. {remark}")
    _move(db, f, "decided", actor.user_id, now, from_user_id=actor.user_id, remark=remark)
    f.last_decision = decision
    _publish(
        db,
        "file.decided",
        f.organisation_id,
        {"file_id": f.id, "number": f.number, "decision": decision, "decided_by": actor.user_id},
        actor.user_id,
    )
    _audit(db, actor.user_id, f"file.{decision}", "file", f)
    if body.get("forward_to_user_id"):
        _forward(db, actor, f, body["forward_to_user_id"], now, action_required=f"decision {decision}")
        _audit(db, actor.user_id, "file.forwarded", "file", f)
    db.commit()
    return file_dict(db, f)


@_duplicate_is_409("concurrent_change", "the file changed at the same moment; try again")
def close_file(db: Session, actor: Actor, file_id: str, remark: str) -> dict:
    f = _held_file(db, actor, file_id)
    remark = _required(remark, "remark")
    now = clock()
    _add_note(db, f, actor.user_id, "system", f"File closed. {remark}")
    _move(db, f, "closed", actor.user_id, now, from_user_id=actor.user_id, remark=remark)
    f.status, f.closed_at, f.closed_by = "closed", now, actor.user_id
    _publish(
        db,
        "file.closed",
        f.organisation_id,
        {"file_id": f.id, "number": f.number, "closed_by": actor.user_id},
        actor.user_id,
    )
    _audit(db, actor.user_id, "file.closed", "file", f)
    db.commit()
    return file_dict(db, f)


@_duplicate_is_409("concurrent_change", "the file changed at the same moment; try again")
def reopen_file(db: Session, actor: Actor, file_id: str, remark: str) -> dict:
    """Anyone with e-office:file:create who can see a closed file reopens it and becomes its holder. The contract
    defines no event for it."""
    f = _visible_file(db, actor, file_id, lock=True)
    if f.status != "closed":
        raise conflict("not_closed", f"file {f.number} is open")
    remark = _required(remark, "remark")
    now = clock()
    _move(db, f, "reopened", actor.user_id, now, from_user_id=f.holder_id, remark=remark)
    f.status, f.closed_at, f.closed_by = "open", None, None
    f.holder_id, f.held_since = actor.user_id, now
    f.action_required, f.due_on, f.overdue_flagged_at = None, None, None
    _add_holder(db, f, actor.user_id, now)
    _add_note(db, f, actor.user_id, "system", f"File reopened. {remark}")
    _audit(db, actor.user_id, "file.reopened", "file", f)
    db.commit()
    return file_dict(db, f)


def movements(db: Session, actor: Actor, file_id: str) -> list[dict]:
    f = _visible_file(db, actor, file_id)
    q = _q(db, Movement).where(Movement.file_id == f.id).order_by(Movement.sequence)
    return [movement_dict(m) for m in db.scalars(q)]


def _unattached_receipts(db: Session, user_id: str) -> int:
    q = scoped(db, select(func.count()).select_from(Receipt), Receipt)
    return db.scalar(q.where(Receipt.send_to_user_id == user_id, Receipt.status == "registered")) or 0


def inbox(db: Session, actor: Actor, cursor: str | None, limit: int) -> dict:
    """Open files the caller holds, oldest received first. `urgent` counts urgent and immediate files. Backs the
    e-office.files-pending widget."""
    q = _q(db, File).where(File.holder_id == actor.user_id, File.status == "open")
    rows = list(db.scalars(q.order_by(File.held_since, File.number)))
    today, days = business_today(), load_settings().default_due_days
    page = _page(rows, cursor, limit, lambda f: file_summary(f, today, days))
    return {
        "total": len(rows),
        "overdue": sum(1 for f in rows if _overdue(f, today, days)),
        "urgent": sum(1 for f in rows if f.priority != "normal"),
        "oldest_held_since": _iso(rows[0].held_since) if rows else None,
        "items": page["items"],
        "unattached_receipts": _unattached_receipts(db, actor.user_id),
        "next_cursor": page["next_cursor"],
    }


def sent(db: Session, actor: Actor, cursor: str | None, limit: int) -> dict:
    """Files the caller forwarded, most recently forwarded first, as they are now (holder, status)."""
    q = _q(db, Movement).where(Movement.from_user_id == actor.user_id, Movement.kind == "forwarded")
    order = list(dict.fromkeys(m.file_id for m in db.scalars(q.order_by(Movement.at.desc(), Movement.sequence.desc()))))
    files = {f.id: f for f in db.scalars(_visible(db, actor, _q(db, File).where(File.id.in_(order))))} if order else {}
    rows = [files[i] for i in order if i in files]
    return _page(rows, cursor, limit, _summaries())


# ---------------------------------------------------------------- inward receipts


def receipt_dict(r: Receipt) -> dict:
    return {
        "id": r.id,
        "organisation_id": r.organisation_id,
        "number": r.number,
        "received_on": _iso(r.received_on),
        "sender": r.sender,
        "sender_reference": r.sender_reference,
        "subject": r.subject,
        "mode": r.mode,
        "document_id": r.document_id,
        "send_to_user_id": r.send_to_user_id,
        "status": r.status,
        "file_id": r.file_id,
        "registered_by": user_ref(r.registered_by),
        "created_at": _iso(r.created_at),
    }


@_duplicate_is_409("number_taken", "another request took the same number; try again")
def register_receipt(db: Session, actor: Actor, body: dict) -> dict:
    """The scan is a platform/documents id, optional until the documents service exists."""
    now = clock()
    received_on = _rule(rules.not_in_future, body["received_on"], business_date(now), "received_on")
    r = Receipt(
        organisation_id=actor.organisation_id,
        number=_next_register_number(db, Receipt, "IN", business_date(now).year),
        received_on=received_on,
        sender=_required(body["sender"], "sender"),
        sender_reference=_text(body.get("sender_reference")) or None,
        subject=_required(body["subject"], "subject"),
        mode=body.get("mode"),
        document_id=_text(body.get("document_id")) or None,
        send_to_user_id=_required(body["send_to_user_id"], "send_to_user_id"),
        status="registered",
        registered_by=actor.user_id,
        created_at=now,
    )
    db.add(r)
    db.flush()
    _publish(
        db,
        "receipt.registered",
        r.organisation_id,
        {
            "receipt_id": r.id,
            "number": r.number,
            "send_to_user_id": r.send_to_user_id,
            "received_on": _iso(r.received_on),
        },
        actor.user_id,
    )
    _audit(db, actor.user_id, "receipt.registered", "receipt", r)
    db.commit()
    return receipt_dict(r)


def _receipts_query(db: Session, status: str | None, day_from: date | None, day_to: date | None):
    q = _q(db, Receipt)
    if status:
        q = q.where(Receipt.status == status)
    if day_from:
        q = q.where(Receipt.received_on >= day_from)
    if day_to:
        q = q.where(Receipt.received_on <= day_to)
    return q.order_by(Receipt.received_on.desc(), Receipt.number.desc())


def list_receipts(
    db: Session, status: str | None, day_from: date | None, day_to: date | None, cursor: str | None, limit: int
) -> dict:
    return _page(list(db.scalars(_receipts_query(db, status, day_from, day_to))), cursor, limit, receipt_dict)


def my_receipts(db: Session, actor: Actor, status: str | None, cursor: str | None, limit: int) -> dict:
    q = _receipts_query(db, status, None, None).where(Receipt.send_to_user_id == actor.user_id)
    return _page(list(db.scalars(q)), cursor, limit, receipt_dict)


def _readable_receipt(db: Session, actor: Actor, receipt_id: str, *, lock: bool = False) -> Receipt:
    """The registry sees every receipt; anyone else only those sent to them (others answer 404)."""
    r = _get(db, Receipt, receipt_id, "receipt", lock=lock)
    if not actor.can(CORRESPONDENCE_MANAGE) and r.send_to_user_id != actor.user_id:
        raise not_found("receipt")
    return r


def get_receipt(db: Session, actor: Actor, receipt_id: str) -> dict:
    return receipt_dict(_readable_receipt(db, actor, receipt_id))


def _receivable(db: Session, actor: Actor, receipt_id: str) -> Receipt:
    """A receipt the caller may attach: sent to them and not attached yet."""
    r = _readable_receipt(db, actor, receipt_id, lock=True)
    if r.send_to_user_id != actor.user_id:
        raise EOfficeError(403, "forbidden", "only the person a receipt was sent to attaches it to a file")
    if r.status != "registered":
        raise conflict("receipt_attached", f"receipt {r.number} is already attached to a file")
    return r


def _attach_receipt(db: Session, actor: Actor, r: Receipt, f: File, now: datetime) -> None:
    db.add(
        Attachment(
            organisation_id=f.organisation_id,
            file_id=f.id,
            document_id=r.document_id,
            title=f"{r.number}: {r.subject}"[:300],
            kind="correspondence",
            receipt_id=r.id,
            added_by=actor.user_id,
            created_at=now,
        )
    )
    r.status, r.file_id, r.attached_by, r.attached_at = "attached", f.id, actor.user_id, now
    _add_note(db, f, actor.user_id, "system", f"Receipt {r.number} from {r.sender} attached.")
    _audit(db, actor.user_id, "receipt.attached", "receipt", r)


@_duplicate_is_409("concurrent_change", "the file changed at the same moment; try again")
def attach_receipt(db: Session, actor: Actor, receipt_id: str, file_id: str) -> dict:
    r = _receivable(db, actor, receipt_id)
    f = _held_file(db, actor, file_id)
    _attach_receipt(db, actor, r, f, clock())
    _audit(db, actor.user_id, "file.attached", "file", f)
    db.commit()
    return receipt_dict(r)


# ---------------------------------------------------------------- outward dispatches


def dispatch_dict(d: Dispatch, file_number: str | None = None) -> dict:
    return {
        "id": d.id,
        "organisation_id": d.organisation_id,
        "number": d.number,
        "file_id": d.file_id,
        "file_number": file_number,
        "attachment_id": d.attachment_id,
        "addressee": d.addressee,
        "address": d.address,
        "email": d.email,
        "status": d.status,
        "mode": d.mode,
        "sent_on": _iso(d.sent_on),
        "reference": d.reference,
        "requested_by": user_ref(d.requested_by),
        "requested_at": _iso(d.created_at),
    }


def _file_numbers(db: Session, ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    return dict(db.execute(scoped(db, select(File.id, File.number), File).where(File.id.in_(ids))).all())


@_duplicate_is_409("number_taken", "another request took the same number; try again")
def request_dispatch(db: Session, actor: Actor, body: dict) -> dict:
    """The holder of an approved file asks the registry to send a letter attached to it."""
    f = _held_file(db, actor, body["file_id"])
    if f.last_decision != "approved":
        raise conflict("not_approved", f"file {f.number} has no approval decision")
    attachment_id = body["attachment_id"]
    if attachment_id not in _file_attachment_ids(db, f.id):
        raise invalid("unknown_attachment", "the letter must be an attachment of the file", "attachment_id")
    addressee = _required(body["addressee"], "addressee")
    pending = _q(db, Dispatch).where(
        Dispatch.attachment_id == attachment_id, Dispatch.addressee == addressee, Dispatch.status == "pending"
    )
    if db.scalar(pending) is not None:
        raise conflict("dispatch_exists", "this letter is already waiting to be sent to this addressee")
    now = clock()
    d = Dispatch(
        organisation_id=f.organisation_id,
        number=_next_register_number(db, Dispatch, "OUT", business_date(now).year),
        file_id=f.id,
        attachment_id=attachment_id,
        addressee=addressee,
        address=_text(body.get("address")) or None,
        email=_text(body.get("email")) or None,
        status="pending",
        requested_by=actor.user_id,
        created_at=now,
    )
    db.add(d)
    _add_note(db, f, actor.user_id, "system", f"Dispatch {d.number} requested to {addressee}.")
    _audit(db, actor.user_id, "dispatch.requested", "dispatch", d)
    db.commit()
    return dispatch_dict(d, f.number)


def list_dispatches(db: Session, status: str | None, cursor: str | None, limit: int) -> dict:
    q = _q(db, Dispatch)
    if status:
        q = q.where(Dispatch.status == status)
    rows = list(db.scalars(q.order_by(Dispatch.created_at.desc(), Dispatch.number.desc())))
    offset = _offset(cursor)
    numbers = _file_numbers(db, {d.file_id for d in rows[offset : offset + limit]})
    return _page(rows, cursor, limit, lambda d: dispatch_dict(d, numbers.get(d.file_id)))


@_duplicate_is_409("concurrent_change", "the file changed at the same moment; try again")
def mark_sent(db: Session, actor: Actor, dispatch_id: str, body: dict) -> dict:
    """The registry records how and when the letter went. The file's note sheet records the dispatch number, even
    when the file has since been closed: it is a record, not a movement."""
    d = _get(db, Dispatch, dispatch_id, "dispatch", lock=True)
    if d.status == "sent":
        raise conflict("already_sent", f"dispatch {d.number} was already sent")
    sent_on = _rule(rules.not_in_future, body["sent_on"], business_today(), "sent_on")
    if sent_on < business_date(d.created_at):
        raise invalid("invalid_date", "sent_on cannot be before the dispatch was requested", "sent_on")
    d.status, d.mode, d.sent_on = "sent", body["mode"], sent_on
    d.reference, d.sent_by = _text(body.get("reference")) or None, actor.user_id
    f = db.scalar(_q(db, File).where(File.id == d.file_id).with_for_update())
    reference = f"; reference {d.reference}" if d.reference else ""
    _add_note(
        db, f, actor.user_id, "system", f"Dispatch {d.number} sent by {d.mode} on {sent_on.isoformat()}{reference}."
    )
    _publish(
        db,
        "dispatch.sent",
        d.organisation_id,
        {"dispatch_id": d.id, "number": d.number, "file_id": d.file_id, "mode": d.mode, "sent_on": _iso(sent_on)},
        actor.user_id,
    )
    _audit(db, actor.user_id, "dispatch.sent", "dispatch", d)
    db.commit()
    return dispatch_dict(d, f.number)


# ---------------------------------------------------------------- overdue


def flag_overdue(db: Session) -> int:
    """Flag every open file held past its due date (the one set when it was sent, or the default days for its
    priority) and publish e-office.file.overdue once per holding. Idempotent: a flagged holding is skipped, and a new
    holding (forward, reopen) starts unflagged. Runs over the organisations the session can see: one organisation
    in its scope, every organisation in platform scope (the scheduler's platform job)."""
    today, days = business_today(), load_settings().default_due_days
    q = _q(db, File).where(File.status == "open", File.overdue_flagged_at.is_(None))
    if db.get_bind().dialect.name == "postgresql":
        q = q.with_for_update(skip_locked=True)
    flagged = 0
    for f in db.scalars(q.order_by(File.held_since)):
        due = _due(f, days)
        if not rules.is_overdue(due, today):
            continue
        f.overdue_flagged_at = clock()
        _publish(
            db,
            "file.overdue",
            f.organisation_id,
            {"file_id": f.id, "number": f.number, "holder_id": f.holder_id, "due_on": due.isoformat()},
        )
        _audit(db, None, "file.overdue", "file", f)
        flagged += 1
    db.commit()
    return flagged
