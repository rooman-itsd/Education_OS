"""Use cases of helpdesk (docs/prd.md, contracts/openapi.yaml). Each one checks the caller's permission and the
domain rules, changes state, writes an audit entry, and publishes the matching event from contracts/events.yaml to
the outbox in the same transaction. Event payloads carry exactly the fields events.yaml lists; titles,
descriptions, replies, notes and feedback are never published.

Who may act follows the contract as written: helpdesk:ticket:work for replies, notes, hold, start, resolve and
links on a ticket the caller can see; the assignee rule only where the contract states one (PATCH priority, and
self-assignment through /assign). A ticket the caller cannot see answers 404.

Where the contract leaves a detail open, the choice made here is noted at the function."""

from __future__ import annotations

from datetime import UTC, datetime

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import tickets as rules
from ..domain.errors import DomainRuleError
from ..domain.stats import CountedTicket
from ..domain.windows import can_reopen, reopen_within_window
from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from ..infrastructure.models import AuditEntry, Category, Comment, Queue, Ticket, TicketLink
from .access import (
    SELF_RAISE,
    SELF_READ,
    SETTINGS_MANAGE,
    TICKET_MANAGE,
    TICKET_READ,
    TICKET_READ_ALL,
    TICKET_WORK,
    Actor,
    require,
)
from .errors import HelpdeskError, forbidden, from_domain
from .stats import get_open_by_priority

MODULE = "helpdesk"
PUBLIC, INTERNAL = "public", "internal"
PORTAL = "portal"


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


# ---------------------------------------------------------------- helpers


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; everything stored is UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | None) -> str | None:
    return None if value is None else as_utc(value).isoformat()


def _not_found(what: str) -> HelpdeskError:
    return HelpdeskError(404, "not_found", f"{what} not found")


def _conflict(code: str, message: str, field: str | None = None) -> HelpdeskError:
    return HelpdeskError(409, code, message, field=field)


def _invalid(code: str, message: str, field: str | None = None) -> HelpdeskError:
    return HelpdeskError(422, code, message, field=field)


def _domain(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except DomainRuleError as err:
        raise from_domain(err) from err


def _audit(
    db: Session,
    actor: Actor | None,
    organisation_id: str,
    action: str,
    entity: str,
    entity_id: str,
    reason: str | None = None,
) -> None:
    db.add(
        AuditEntry(
            organisation_id=organisation_id,
            actor=actor.user_id if actor else None,
            action=action,
            entity=entity,
            entity_id=entity_id,
            reason=reason,
            occurred_at=clock(),
        )
    )


def _publish(db: Session, actor: Actor | None, name: str, organisation_id: str, payload: dict) -> None:
    events.publish(
        db,
        f"{MODULE}.ticket.{name}",
        organisation_id,
        {"organisation_id": organisation_id, **payload},
        actor=actor.user_id if actor else None,
    )


def _check_attachments(ids: list[str] | None) -> list[str]:
    ids = list(ids or [])
    maximum = load_settings().max_attachments
    if len(ids) > maximum:
        raise _invalid("too_many_attachments", f"at most {maximum} attachments", field="attachment_document_ids")
    return ids


def _visible_queue_ids(db: Session, actor: Actor) -> set[str] | None:
    """None: every queue (helpdesk:ticket:read-all). Otherwise the queues the caller is a member of."""
    if actor.can(TICKET_READ_ALL):
        return None
    return repo.member_queue_ids(db, actor.user_id)


def _visible_ticket(db: Session, actor: Actor, ticket_id: str) -> Ticket:
    """A ticket in the caller's queues, or in any queue with read-all; 404 otherwise."""
    ticket = repo.get(db, Ticket, ticket_id)
    visible = _visible_queue_ids(db, actor)
    if ticket is None or (visible is not None and ticket.queue_id not in visible):
        raise _not_found("ticket")
    return ticket


def _own_ticket(db: Session, actor: Actor, ticket_id: str) -> Ticket:
    ticket = repo.get(db, Ticket, ticket_id)
    if ticket is None or ticket.requester_id != actor.user_id:
        raise _not_found("ticket")
    return ticket


def _commit(db: Session) -> None:
    db.commit()


# ---------------------------------------------------------------- serialisation (contract schemas)


def queue_dict(queue: Queue, open_count: int) -> dict:
    return {
        "id": queue.id,
        "organisation_id": queue.organisation_id,
        "name": queue.name,
        "description": queue.description,
        "member_ids": list(queue.member_ids or []),
        "active": queue.active,
        "open_count": open_count,
    }


def category_dict(category: Category) -> dict:
    return {
        "id": category.id,
        "organisation_id": category.organisation_id,
        "parent_id": category.parent_id,
        "name": category.name,
        "description": category.description,
        "default_queue_id": category.default_queue_id,
        "default_priority": category.default_priority,
        "active": category.active,
    }


def ticket_dict(t: Ticket) -> dict:
    return {
        "id": t.id,
        "organisation_id": t.organisation_id,
        "number": t.number,
        "requester_id": t.requester_id,
        "raised_by_id": t.raised_by_id,
        "channel": t.channel,
        "category_id": t.category_id,
        "queue_id": t.queue_id,
        "assignee_id": t.assignee_id,
        "priority": t.priority,
        "status": t.status,
        "hold_reason": t.hold_reason,
        "title": t.title,
        "description": t.description,
        "attachment_document_ids": list(t.attachment_document_ids or []),
        "resolution_note": t.resolution_note,
        "duplicate_of": t.duplicate_of,
        "reopen_count": t.reopen_count,
        "satisfaction_rating": t.satisfaction_rating,
        "feedback": t.feedback,
        "created_at": iso(t.created_at),
        "updated_at": iso(t.updated_at),
        "first_responded_at": iso(t.first_responded_at),
        "resolved_at": iso(t.resolved_at),
        "closed_at": iso(t.closed_at),
    }


def comment_dict(c: Comment) -> dict:
    return {
        "id": c.id,
        "ticket_id": c.ticket_id,
        "author_id": c.author_id,
        "author_is_requester": c.author_is_requester,
        "visibility": c.visibility,
        "body": c.body,
        "attachment_document_ids": list(c.attachment_document_ids or []),
        "created_at": iso(c.created_at),
    }


def link_dict(link: TicketLink) -> dict:
    return {
        "id": link.id,
        "ticket_id": link.ticket_id,
        "module": link.module,
        "entity": link.entity,
        "ref_id": link.ref_id,
        "note": link.note,
        "created_by": link.created_by,
        "created_at": iso(link.created_at),
    }


# ---------------------------------------------------------------- queues


def list_queues(db: Session, actor: Actor, active: bool | None) -> list[dict]:
    """GET /queues: "Support queues of the organisation", every queue, with open_count."""
    require(actor, TICKET_READ, SETTINGS_MANAGE)
    counts = repo.open_counts_by_queue(db)
    return [queue_dict(q, counts.get(q.id, 0)) for q in repo.queues(db, active)]


def create_queue(db: Session, actor: Actor, body: dict) -> dict:
    require(actor, SETTINGS_MANAGE)
    if repo.queue_by_name(db, body["name"]) is not None:
        raise _conflict("queue_name_taken", "a queue with this name already exists", field="name")
    queue = Queue(
        organisation_id=actor.organisation_id,
        name=body["name"],
        description=body.get("description"),
        member_ids=list(dict.fromkeys(body.get("member_ids") or [])),
        active=body.get("active", True),
    )
    db.add(queue)
    db.flush()
    _audit(db, actor, actor.organisation_id, "queue.created", "queue", queue.id)
    _commit(db)
    return queue_dict(queue, 0)


def update_queue(db: Session, actor: Actor, queue_id: str, body: dict) -> dict:
    """PATCH /queues/{id}. Only the fields sent are changed. "A queue with open tickets cannot be deactivated" (409).
    A rename to another queue's name is also a 409, as on POST /queues."""
    require(actor, SETTINGS_MANAGE)
    queue = repo.get(db, Queue, queue_id)
    if queue is None:
        raise _not_found("queue")
    if "name" in body and body["name"] != queue.name:
        other = repo.queue_by_name(db, body["name"])
        if other is not None and other.id != queue.id:
            raise _conflict("queue_name_taken", "a queue with this name already exists", field="name")
        queue.name = body["name"]
    if body.get("active") is False and queue.active and repo.open_counts_by_queue(db).get(queue.id, 0):
        raise _conflict("queue_has_open_tickets", "a queue with open tickets cannot be deactivated", field="active")
    if "description" in body:
        queue.description = body["description"]
    if "member_ids" in body:
        queue.member_ids = list(dict.fromkeys(body["member_ids"] or []))
    if "active" in body:
        queue.active = body["active"]
    _audit(db, actor, actor.organisation_id, "queue.updated", "queue", queue.id)
    _commit(db)
    return queue_dict(queue, repo.open_counts_by_queue(db).get(queue.id, 0))


# ---------------------------------------------------------------- categories


def list_categories(db: Session, actor: Actor, active: bool | None) -> list[dict]:
    require(actor, SELF_RAISE, TICKET_READ, SETTINGS_MANAGE)
    return [category_dict(c) for c in repo.categories(db, active)]


def _check_category_shape(db: Session, parent_id: str | None, default_queue_id: str, category_id: str | None) -> None:
    """Two levels only: the parent must be a top-level category, and a category with sub-categories cannot itself
    become one (409, "parent is itself a sub-category"). The parent and the default queue must exist in the
    organisation (422 otherwise; the contract names no answer for an unknown id)."""
    if parent_id is not None:
        parent = repo.get(db, Category, parent_id)
        if parent is None:
            raise _invalid("unknown_parent", "parent category not found", field="parent_id")
        if parent.parent_id is not None or parent.id == category_id:
            raise _conflict("too_deep", "only two levels: the parent is itself a sub-category", field="parent_id")
        if category_id is not None and repo.has_children(db, category_id):
            raise _conflict("too_deep", "a category with sub-categories cannot become one", field="parent_id")
    if repo.get(db, Queue, default_queue_id) is None:
        raise _invalid("unknown_queue", "default queue not found", field="default_queue_id")


def create_category(db: Session, actor: Actor, body: dict) -> dict:
    require(actor, SETTINGS_MANAGE)
    parent_id = body.get("parent_id")
    _check_category_shape(db, parent_id, body["default_queue_id"], None)
    if repo.category_by_name(db, parent_id, body["name"]) is not None:
        raise _conflict("category_name_taken", "the name already exists under this parent", field="name")
    category = Category(
        organisation_id=actor.organisation_id,
        parent_id=parent_id,
        name=body["name"],
        description=body.get("description"),
        default_queue_id=body["default_queue_id"],
        default_priority=body["default_priority"],
        active=body.get("active", True),
    )
    db.add(category)
    db.flush()
    _audit(db, actor, actor.organisation_id, "category.created", "category", category.id)
    _commit(db)
    return category_dict(category)


def update_category(db: Session, actor: Actor, category_id: str, body: dict) -> dict:
    """PATCH /categories/{id}: "Existing tickets keep their values". Only the fields sent are changed."""
    require(actor, SETTINGS_MANAGE)
    category = repo.get(db, Category, category_id)
    if category is None:
        raise _not_found("category")
    parent_id = body["parent_id"] if "parent_id" in body else category.parent_id
    default_queue_id = body.get("default_queue_id", category.default_queue_id)
    _check_category_shape(db, parent_id, default_queue_id, category.id)
    name = body.get("name", category.name)
    clash = repo.category_by_name(db, parent_id, name)
    if clash is not None and clash.id != category.id:
        raise _conflict("category_name_taken", "the name already exists under this parent", field="name")
    category.parent_id, category.name, category.default_queue_id = parent_id, name, default_queue_id
    for key in ("description", "default_priority", "active"):
        if key in body:
            setattr(category, key, body[key])
    _audit(db, actor, actor.organisation_id, "category.updated", "category", category.id)
    _commit(db)
    return category_dict(category)


# ---------------------------------------------------------------- raising tickets


def _active_category(db: Session, category_id: str) -> Category:
    category = repo.get(db, Category, category_id)
    if category is None or not category.active:
        raise _invalid("category_inactive", "the category is inactive or does not exist", field="category_id")
    return category


def _raise(db: Session, actor: Actor, body: dict, *, requester_id: str, channel: str, priority: str | None) -> Ticket:
    """The ticket gets the category's default queue and priority, status new and the next number. Whether the
    default queue is active is not checked: the contract names only an inactive category (422)."""
    category = _active_category(db, body["category_id"])
    attachments = _check_attachments(body.get("attachment_document_ids"))
    number = repo.next_ticket_number(db, actor.organisation_id)
    # Format from the PRD's example HD-000123: the prefix, a hyphen and the number padded to six digits.
    ticket = Ticket(
        organisation_id=actor.organisation_id,
        number=f"{load_settings().ticket_number_prefix}-{number:06d}",
        requester_id=requester_id,
        raised_by_id=actor.user_id,
        channel=channel,
        category_id=category.id,
        queue_id=category.default_queue_id,
        priority=priority or category.default_priority,
        status=rules.NEW,
        title=body["title"],
        description=body["description"],
        attachment_document_ids=attachments,
        reopen_count=0,
    )
    db.add(ticket)
    db.flush()
    _audit(db, actor, actor.organisation_id, "ticket.created", "ticket", ticket.id)
    _publish(
        db,
        actor,
        "created",
        actor.organisation_id,
        {
            "ticket_id": ticket.id,
            "number": ticket.number,
            "requester_id": ticket.requester_id,
            "raised_by_id": ticket.raised_by_id,
            "channel": ticket.channel,
            "category_id": ticket.category_id,
            "queue_id": ticket.queue_id,
            "priority": ticket.priority,
            "created_at": iso(ticket.created_at),
        },
    )
    return ticket


def raise_my_ticket(db: Session, actor: Actor, body: dict) -> dict:
    """POST /me/tickets (channel portal)."""
    require(actor, SELF_RAISE)
    ticket = _raise(db, actor, body, requester_id=actor.user_id, channel=PORTAL, priority=None)
    _commit(db)
    return ticket_dict(ticket)


def raise_ticket(db: Session, actor: Actor, body: dict) -> dict:
    """POST /tickets: on behalf of a requester. With assign_to_me the ticket is assigned to the caller and
    helpdesk.ticket.assigned is published after created ("A ticket was assigned to an agent"), so subscribers learn
    the assignee. As on /assign, "The assignee must be a member of the target queue": a caller outside the
    category's default queue is refused with 409 assignee_not_in_queue, so no ticket is assigned to someone who
    cannot open it."""
    require(actor, TICKET_WORK)
    if body.get("assign_to_me"):
        category = _active_category(db, body["category_id"])
        queue = repo.get(db, Queue, category.default_queue_id)
        if queue is None or actor.user_id not in (queue.member_ids or []):
            message = "you are not a member of the ticket's queue"
            raise _conflict("assignee_not_in_queue", message, field="assign_to_me")
    ticket = _raise(
        db, actor, body, requester_id=body["requester_id"], channel=body["channel"], priority=body.get("priority")
    )
    if body.get("assign_to_me"):
        ticket.assignee_id = actor.user_id
        _audit(db, actor, actor.organisation_id, "ticket.assigned", "ticket", ticket.id)
        _publish_assigned(db, actor, ticket, previous_queue_id=ticket.queue_id, previous_assignee_id=None)
    _commit(db)
    return ticket_dict(ticket)


# ---------------------------------------------------------------- reading tickets


def list_tickets(db: Session, actor: Actor, filters: dict, cursor: str | None, limit: int) -> dict:
    require(actor, TICKET_READ)
    query = repo.tickets_query(db, queue_ids=_visible_queue_ids(db, actor), me=actor.user_id, **filters)
    rows, next_cursor = repo.page(db, query, cursor, limit)
    return {"items": [ticket_dict(t) for t in rows], "next_cursor": next_cursor}


def get_ticket(db: Session, actor: Actor, ticket_id: str) -> dict:
    """GET /tickets/{id}: public replies and internal notes, oldest first, and links."""
    require(actor, TICKET_READ)
    ticket = _visible_ticket(db, actor, ticket_id)
    return {
        **ticket_dict(ticket),
        "comments": [comment_dict(c) for c in repo.comments(db, ticket.id, public_only=False)],
        "links": [link_dict(link) for link in repo.links(db, ticket.id)],
    }


def list_my_tickets(db: Session, actor: Actor, statuses: list[str] | None, cursor: str | None, limit: int) -> dict:
    require(actor, SELF_READ)
    rows, next_cursor = repo.page(db, repo.my_tickets_query(db, actor.user_id, statuses), cursor, limit)
    return {"items": [ticket_dict(t) for t in rows], "next_cursor": next_cursor}


def get_my_ticket(db: Session, actor: Actor, ticket_id: str) -> dict:
    """GET /me/tickets/{id}: public replies only; internal notes and links are never returned."""
    require(actor, SELF_READ)
    ticket = _own_ticket(db, actor, ticket_id)
    window = load_settings().reopen_window_days
    return {
        **ticket_dict(ticket),
        "comments": [comment_dict(c) for c in repo.comments(db, ticket.id, public_only=True)],
        "can_reopen": can_reopen(ticket.status, as_utc(ticket.resolved_at), clock(), window),
    }


# ---------------------------------------------------------------- changing a ticket


def update_ticket(db: Session, actor: Actor, ticket_id: str, body: dict) -> dict:
    """PATCH /tickets/{id}: "helpdesk:ticket:work for title and priority on tickets assigned to the caller,
    helpdesk:ticket:manage otherwise". A category or priority change needs a reason, kept in the audit record, and
    publishes helpdesk.ticket.reclassified with the previous values. The category must exist in the organisation."""
    require(actor, TICKET_WORK, TICKET_MANAGE)
    ticket = _visible_ticket(db, actor, ticket_id)
    _domain(rules.ensure_can_reclassify, ticket.status)
    category_changes = "category_id" in body and body["category_id"] != ticket.category_id
    priority_changes = "priority" in body and body["priority"] != ticket.priority
    own_work = ticket.assignee_id == actor.user_id and not category_changes
    if not (actor.can(TICKET_MANAGE) or (actor.can(TICKET_WORK) and own_work)):
        raise forbidden("needs helpdesk:ticket:manage, or helpdesk:ticket:work on a ticket assigned to you")
    if (category_changes or priority_changes) and not (body.get("reason") or "").strip():
        raise _invalid("reason_required", "a reason is required to change the category or priority", field="reason")
    if category_changes and repo.get(db, Category, body["category_id"]) is None:
        raise _invalid("unknown_category", "category not found", field="category_id")
    previous_category, previous_priority = ticket.category_id, ticket.priority
    if "title" in body:
        ticket.title = body["title"]
    if category_changes:
        ticket.category_id = body["category_id"]
    if priority_changes:
        ticket.priority = body["priority"]
    reclassified = category_changes or priority_changes
    action = "ticket.reclassified" if reclassified else "ticket.updated"
    _audit(db, actor, ticket.organisation_id, action, "ticket", ticket.id, body.get("reason") if reclassified else None)
    if reclassified:
        _publish(
            db,
            actor,
            "reclassified",
            ticket.organisation_id,
            {
                "ticket_id": ticket.id,
                "number": ticket.number,
                "category_id": ticket.category_id,
                "previous_category_id": previous_category,
                "priority": ticket.priority,
                "previous_priority": previous_priority,
                "changed_by": actor.user_id,
            },
        )
    _commit(db)
    return ticket_dict(ticket)


def _publish_assigned(
    db: Session, actor: Actor, ticket: Ticket, *, previous_queue_id: str, previous_assignee_id: str | None
) -> None:
    _publish(
        db,
        actor,
        "assigned",
        ticket.organisation_id,
        {
            "ticket_id": ticket.id,
            "number": ticket.number,
            "queue_id": ticket.queue_id,
            "previous_queue_id": previous_queue_id,
            "assignee_id": ticket.assignee_id,
            "previous_assignee_id": previous_assignee_id,
            "assigned_by": actor.user_id,
        },
    )


def assign_ticket(db: Session, actor: Actor, ticket_id: str, body: dict) -> dict:
    """POST /tickets/{id}/assign. Fields combine as AssignInput says; `body` holds only the fields sent, so an
    explicit assignee_id null (unassign) differs from an omitted one. "Never changes the status. The assignee must be
    a member of the target queue." helpdesk:ticket:work may assign an unassigned ticket in the caller's queue to
    themselves; anything else needs helpdesk:ticket:manage. 409 when the ticket is closed or cancelled."""
    require(actor, TICKET_WORK, TICKET_MANAGE)
    ticket = _visible_ticket(db, actor, ticket_id)
    if ticket.status in rules.FINAL_STATUSES:
        raise _conflict("ticket_final", f"a {ticket.status} ticket cannot be assigned", field="status")
    target_queue_id = body.get("queue_id") or ticket.queue_id
    if "assignee_id" in body:
        assignee = body["assignee_id"]
    elif "queue_id" in body:
        assignee = None  # "queue_id only: move to that queue, unassigned"
    else:
        assignee = actor.user_id  # "Both omitted: assign to the caller in the current queue"
    queue = repo.get(db, Queue, target_queue_id)
    if queue is None:
        raise _invalid("unknown_queue", "queue not found", field="queue_id")
    self_pick_up = (
        assignee == actor.user_id
        and target_queue_id == ticket.queue_id
        and ticket.assignee_id is None
        and actor.user_id in (queue.member_ids or [])
    )
    if not (actor.can(TICKET_MANAGE) or (actor.can(TICKET_WORK) and self_pick_up)):
        raise forbidden("needs helpdesk:ticket:manage, except picking up an unassigned ticket in your queue")
    if assignee is not None and assignee not in (queue.member_ids or []):
        raise _conflict("assignee_not_in_queue", "the assignee is not a member of the queue", field="assignee_id")
    previous_queue_id, previous_assignee_id = ticket.queue_id, ticket.assignee_id
    ticket.queue_id, ticket.assignee_id = target_queue_id, assignee
    _audit(db, actor, ticket.organisation_id, "ticket.assigned", "ticket", ticket.id)
    _publish_assigned(db, actor, ticket, previous_queue_id=previous_queue_id, previous_assignee_id=previous_assignee_id)
    _commit(db)
    return ticket_dict(ticket)


def _add_comment(
    db: Session, actor: Actor, ticket: Ticket, visibility: str, body: str, attachments: list[str] | None
) -> Comment:
    comment = Comment(
        organisation_id=ticket.organisation_id,
        ticket_id=ticket.id,
        author_id=actor.user_id,
        author_is_requester=actor.user_id == ticket.requester_id,
        visibility=visibility,
        body=body,
        attachment_document_ids=_check_attachments(attachments),
    )
    db.add(comment)
    db.flush()
    _audit(db, actor, ticket.organisation_id, f"comment.{visibility}", "ticket", ticket.id)
    return comment


def _agent_public_reply(db: Session, actor: Actor, ticket: Ticket) -> None:
    """The first public reply by an agent publishes helpdesk.ticket.responded once; a public reply on a new ticket
    moves it to in_progress."""
    now = clock()
    if ticket.first_responded_at is None:
        ticket.first_responded_at = now
        _publish(
            db,
            actor,
            "responded",
            ticket.organisation_id,
            {"ticket_id": ticket.id, "number": ticket.number, "responded_by": actor.user_id, "responded_at": iso(now)},
        )
    after = _domain(rules.status_after_agent_public_reply, ticket.status)
    if after != ticket.status:
        _move(db, actor, ticket, after, None)


def _move(db: Session, actor: Actor | None, ticket: Ticket, to: str, hold_reason: str | None) -> None:
    """A move between new, in_progress and on_hold: helpdesk.ticket.status-changed. The hold reason is kept only
    while on hold."""
    from_status = ticket.status
    ticket.status, ticket.hold_reason = to, hold_reason if to == rules.ON_HOLD else None
    _publish(
        db,
        actor,
        "status-changed",
        ticket.organisation_id,
        {
            "ticket_id": ticket.id,
            "number": ticket.number,
            "from_status": from_status,
            "to_status": to,
            "hold_reason": ticket.hold_reason,
            "changed_at": iso(clock()),
        },
    )


def add_comment(db: Session, actor: Actor, ticket_id: str, body: dict) -> dict:
    """POST /tickets/{id}/comments: a public reply or an internal note; 409 when closed or cancelled. A public
    reply by the ticket's own requester (an agent who raised it for themselves) is not "the first public reply by
    an agent" (events.yaml, helpdesk.ticket.responded): it neither stops the response clock nor starts work."""
    require(actor, TICKET_WORK)
    ticket = _visible_ticket(db, actor, ticket_id)
    _domain(rules.ensure_can_comment, ticket.status)
    comment = _add_comment(db, actor, ticket, body["visibility"], body["body"], body.get("attachment_document_ids"))
    if body["visibility"] == PUBLIC and actor.user_id != ticket.requester_id:
        _agent_public_reply(db, actor, ticket)
    _commit(db)
    return comment_dict(comment)


def change_status(db: Session, actor: Actor, ticket_id: str, body: dict) -> dict:
    """POST /tickets/{id}/status: start work (new or on_hold -> in_progress) or put on hold with a reason
    (in_progress -> on_hold). The optional note is saved as a public reply, so it counts as one (responded)."""
    require(actor, TICKET_WORK)
    ticket = _visible_ticket(db, actor, ticket_id)
    if body["status"] == rules.ON_HOLD:
        after = _domain(rules.put_on_hold, ticket.status, body.get("hold_reason"))
    else:
        after = _domain(rules.start_work, ticket.status)
    _move(db, actor, ticket, after, body.get("hold_reason"))
    if body.get("note"):
        _add_comment(db, actor, ticket, PUBLIC, body["note"], None)
        _agent_public_reply(db, actor, ticket)
    _audit(db, actor, ticket.organisation_id, f"ticket.{after}", "ticket", ticket.id)
    _commit(db)
    return ticket_dict(ticket)


def resolve_ticket(db: Session, actor: Actor, ticket_id: str, body: dict) -> dict:
    require(actor, TICKET_WORK)
    ticket = _visible_ticket(db, actor, ticket_id)
    ticket.status = _domain(rules.resolve, ticket.status)
    now = clock()
    ticket.hold_reason, ticket.resolution_note, ticket.resolved_at = None, body["resolution_note"], now
    _audit(db, actor, ticket.organisation_id, "ticket.resolved", "ticket", ticket.id)
    _publish(
        db,
        actor,
        "resolved",
        ticket.organisation_id,
        {
            "ticket_id": ticket.id,
            "number": ticket.number,
            "requester_id": ticket.requester_id,
            "resolved_by": actor.user_id,
            "resolved_at": iso(now),
        },
    )
    _commit(db)
    return ticket_dict(ticket)


def _cancel(db: Session, actor: Actor, ticket: Ticket, reason: str, duplicate_of: str | None, action: str) -> None:
    ticket.status = _domain(rules.cancel, ticket.status, ticket_id=ticket.id, duplicate_of=duplicate_of)
    ticket.hold_reason, ticket.duplicate_of = None, duplicate_of
    now = clock()
    _audit(db, actor, ticket.organisation_id, action, "ticket", ticket.id, reason)
    _publish(
        db,
        actor,
        "cancelled",
        ticket.organisation_id,
        {
            "ticket_id": ticket.id,
            "number": ticket.number,
            "cancelled_by": actor.user_id,
            "duplicate_of": duplicate_of,
            "cancelled_at": iso(now),
        },
    )


def cancel_ticket(db: Session, actor: Actor, ticket_id: str, body: dict) -> dict:
    """POST /tickets/{id}/cancel. duplicate_of is "Another open ticket" (CancelInput): one that is not found, or
    not open, is refused with 409 like the contract's "duplicate_of is this ticket"."""
    require(actor, TICKET_MANAGE)
    ticket = _visible_ticket(db, actor, ticket_id)
    duplicate_of = body.get("duplicate_of")
    if duplicate_of is not None and duplicate_of != ticket.id:
        original = repo.get(db, Ticket, duplicate_of)
        if original is None or original.status not in rules.OPEN_STATUSES:
            raise _conflict("invalid_duplicate", "duplicate_of must be another open ticket", field="duplicate_of")
    _cancel(db, actor, ticket, body["reason"], duplicate_of, "ticket.cancelled")
    _commit(db)
    return ticket_dict(ticket)


def add_link(db: Session, actor: Actor, ticket_id: str, body: dict) -> dict:
    require(actor, TICKET_WORK)
    ticket = _visible_ticket(db, actor, ticket_id)
    if repo.same_link(db, ticket.id, body["module"], body["entity"], body["ref_id"]) is not None:
        raise _conflict("link_exists", "the same link already exists")
    link = TicketLink(
        organisation_id=ticket.organisation_id,
        ticket_id=ticket.id,
        module=body["module"],
        entity=body["entity"],
        ref_id=body["ref_id"],
        note=body.get("note"),
        created_by=actor.user_id,
    )
    db.add(link)
    try:
        db.flush()
    except IntegrityError:  # the same link added at the same moment
        db.rollback()
        raise _conflict("link_exists", "the same link already exists") from None
    _audit(db, actor, ticket.organisation_id, "link.added", "ticket", ticket.id)
    _commit(db)
    return link_dict(link)


def remove_link(db: Session, actor: Actor, ticket_id: str, link_id: str) -> None:
    """DELETE /tickets/{id}/links/{link_id}: "Remove a link recorded by mistake. Audited." The only deletion."""
    require(actor, TICKET_WORK)
    ticket = _visible_ticket(db, actor, ticket_id)
    link = repo.get(db, TicketLink, link_id)
    if link is None or link.ticket_id != ticket.id:
        raise _not_found("link")
    db.delete(link)
    _audit(db, actor, ticket.organisation_id, "link.removed", "ticket", ticket.id)
    _commit(db)


# ---------------------------------------------------------------- the requester's own ticket


def reply_to_my_ticket(db: Session, actor: Actor, ticket_id: str, body: dict) -> dict:
    """POST /me/tickets/{id}/comments: a reply to a ticket on hold waiting on the requester moves it back to
    in_progress."""
    require(actor, SELF_RAISE)
    ticket = _own_ticket(db, actor, ticket_id)
    after = _domain(rules.status_after_requester_reply, ticket.status, ticket.hold_reason)
    comment = _add_comment(db, actor, ticket, PUBLIC, body["body"], body.get("attachment_document_ids"))
    if after != ticket.status:
        _move(db, actor, ticket, after, None)
    _commit(db)
    return comment_dict(comment)


def _close(db: Session, actor: Actor | None, ticket: Ticket, rating: int | None, now: datetime | None = None) -> None:
    ticket.status = _domain(rules.close, ticket.status)
    now = now or clock()
    ticket.closed_at = now
    _audit(db, actor, ticket.organisation_id, "ticket.closed", "ticket", ticket.id)
    _publish(
        db,
        actor,
        "closed",
        ticket.organisation_id,
        {
            "ticket_id": ticket.id,
            "number": ticket.number,
            "closed_by": actor.user_id if actor else None,
            "satisfaction_rating": rating,
            "closed_at": iso(now),
        },
    )


def confirm_my_ticket(db: Session, actor: Actor, ticket_id: str, body: dict) -> dict:
    require(actor, SELF_RAISE)
    ticket = _own_ticket(db, actor, ticket_id)
    ticket.satisfaction_rating, ticket.feedback = body.get("satisfaction_rating"), body.get("feedback")
    _close(db, actor, ticket, ticket.satisfaction_rating)
    _commit(db)
    return ticket_dict(ticket)


def reopen_my_ticket(db: Session, actor: Actor, ticket_id: str, body: dict) -> dict:
    """POST /me/tickets/{id}/reopen within HELPDESK_REOPEN_WINDOW_DAYS. The ticket keeps its assignee; resolved_at
    is cleared, since the ticket is no longer resolved, and set again on the next resolution."""
    require(actor, SELF_RAISE)
    ticket = _own_ticket(db, actor, ticket_id)
    window = load_settings().reopen_window_days
    ticket.status = _domain(reopen_within_window, ticket.status, as_utc(ticket.resolved_at), clock(), window)
    ticket.reopen_count += 1
    ticket.resolved_at = None
    now = clock()
    _audit(db, actor, ticket.organisation_id, "ticket.reopened", "ticket", ticket.id, body["reason"])
    _publish(
        db,
        actor,
        "reopened",
        ticket.organisation_id,
        {
            "ticket_id": ticket.id,
            "number": ticket.number,
            "requester_id": ticket.requester_id,
            "assignee_id": ticket.assignee_id,
            "reopen_count": ticket.reopen_count,
            "reopened_at": iso(now),
        },
    )
    _commit(db)
    return ticket_dict(ticket)


def withdraw_my_ticket(db: Session, actor: Actor, ticket_id: str, body: dict) -> dict:
    require(actor, SELF_RAISE)
    ticket = _own_ticket(db, actor, ticket_id)
    _domain(rules.withdraw, ticket.status)
    _cancel(db, actor, ticket, body["reason"], None, "ticket.withdrawn")
    _commit(db)
    return ticket_dict(ticket)


# ---------------------------------------------------------------- open-by-priority counts


def open_by_priority(db: Session, actor: Actor, scope: str | None, queue_id: str | None) -> dict:
    """GET /stats/open-by-priority: the use case in application/stats.py, reading open tickets through the
    repository."""

    def find_open_tickets(queue_ids: frozenset[str] | None, assignee_id: str | None) -> list[CountedTicket]:
        return [
            CountedTicket(t.status, t.priority, t.assignee_id, as_utc(t.created_at))
            for t in repo.open_tickets(db, queue_ids, assignee_id)
        ]

    result = get_open_by_priority(
        actor,
        scope=scope,
        queue_id=queue_id,
        caller_queue_ids=repo.member_queue_ids(db, actor.user_id),
        find_open_tickets=find_open_tickets,
    )
    return {
        "scope": result.scope,
        "total_open": result.total_open,
        "rows": [
            {
                "priority": r.priority,
                "open": r.open,
                "unassigned": r.unassigned,
                "assigned_to_me": r.assigned_to_me,
                "on_hold": r.on_hold,
                "oldest_created_at": iso(r.oldest_created_at),
            }
            for r in result.rows
        ],
    }
