"""Portfolio application services.
Enforces multi-tenancy, state transitions, reviewer assignment, and emits events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.orm import Session

from ..domain.models import (
    ConflictError,
    ItemStatus,
    NotFoundError,
    PortfolioError,
    ReviewDecision,
    RuleViolationError,
    allowed_actions,
)
from ..infrastructure import repository as repo
from ..infrastructure.models import Item, ItemMedia, ItemType, Review, iso

MODULE = "portfolio"

ITEM_TYPE_READ = f"{MODULE}:item-type:read"
ITEM_TYPE_MANAGE = f"{MODULE}:item-type:manage"
ITEM_READ = f"{MODULE}:item:read"
ITEM_READ_ALL = f"{MODULE}:item:read-all"
ITEM_WRITE = f"{MODULE}:item:write"
ITEM_MANAGE = f"{MODULE}:item:manage"
REVIEW_WRITE = f"{MODULE}:review:write"
REVIEW_MANAGE = f"{MODULE}:review:manage"


def clock() -> datetime:
    """Current time; tests can monkeypatch."""
    return utcnow()


@dataclass
class Actor:
    """Who is calling."""

    user_id: str
    organisation_id: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


def _publish(db: Session, actor: Actor | None, name: str, organisation_id: str, payload: dict) -> None:
    events.publish(
        db,
        f"{MODULE}.{name}",
        organisation_id,
        {"organisation_id": organisation_id, **payload},
        actor=actor.user_id if actor else None,
    )


# ---------------------------------------------------------------- DTO conversion


def item_type_dict(t: ItemType, item_count: int = 0) -> dict:
    return {
        "id": t.id,
        "organisation_id": t.organisation_id,
        "name": t.name,
        "description": t.description,
        "requires_review": t.requires_review,
        "reviewer_person_ids": list(t.reviewer_person_ids or []),
        "item_count": item_count,
        "created_at": iso(t.created_at),
    }


def media_dict(m: ItemMedia) -> dict:
    return {
        "id": m.id,
        "item_id": m.item_id,
        "document_id": m.document_id,
        "caption": m.caption,
        "sort_order": m.sort_order,
        "uploaded_by": m.uploaded_by,
        "uploaded_at": iso(m.uploaded_at),
    }


def review_dict(r: Review) -> dict:
    return {
        "id": r.id,
        "item_id": r.item_id,
        "organisation_id": r.organisation_id,
        "reviewer_person_id": r.reviewer_person_id,
        "decision": r.decision,
        "score": r.score,
        "comments": r.comments,
        "reviewed_at": iso(r.reviewed_at),
    }


def item_dict(
    item: Item,
    actor: Actor,
    media: list[ItemMedia] | None = None,
    reviews: list[Review] | None = None,
    is_reviewer: bool = False,
) -> dict:
    is_owner = item.owner_person_id == actor.user_id
    is_manager = actor.can(ITEM_MANAGE)
    can = allowed_actions(item.status, is_owner=is_owner, is_reviewer=is_reviewer, is_manager=is_manager)
    return {
        "id": item.id,
        "organisation_id": item.organisation_id,
        "type_id": item.type_id,
        "owner_person_id": item.owner_person_id,
        "title": item.title,
        "description": item.description,
        "tags": list(item.tags or []),
        "attributes": dict(item.attributes or {}),
        "status": item.status,
        "submitted_at": iso(item.submitted_at),
        "decided_at": iso(item.decided_at),
        "created_at": iso(item.created_at),
        "updated_at": iso(item.updated_at),
        "media": [media_dict(m) for m in (media or [])],
        "reviews": [review_dict(r) for r in (reviews or [])],
        "can": can,
    }


# ---------------------------------------------------------------- Service operations


def list_item_types(db: Session, actor: Actor) -> list[dict]:
    types = repo.find_item_types(db, actor.organisation_id)
    result = []
    for t in types:
        count = repo.count_items_by_type(db, actor.organisation_id, t.id)
        result.append(item_type_dict(t, item_count=count))
    return result


def create_item_type(db: Session, actor: Actor, data: dict) -> dict:
    name = (data.get("name") or "").strip()
    if not name:
        raise RuleViolationError("missing_name", "Item type name is required")
    existing = repo.get_item_type_by_name(db, actor.organisation_id, name)
    if existing:
        raise ConflictError("name_in_use", f"Item type name '{name}' is already in use")

    t = ItemType(
        organisation_id=actor.organisation_id,
        name=name,
        description=data.get("description"),
        requires_review=data.get("requires_review", True),
        reviewer_person_ids=list(data.get("reviewer_person_ids") or []),
    )
    repo.create_item_type(db, t)
    db.commit()
    return item_type_dict(t, item_count=0)


def update_item_type(db: Session, actor: Actor, type_id: str, data: dict) -> dict:
    t = repo.get_item_type(db, actor.organisation_id, type_id)
    if not t:
        raise NotFoundError("Item type")

    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            raise RuleViolationError("missing_name", "Item type name cannot be empty")
        existing = repo.get_item_type_by_name(db, actor.organisation_id, name)
        if existing and existing.id != t.id:
            raise ConflictError("name_in_use", f"Item type name '{name}' is already in use")
        t.name = name

    if "description" in data:
        t.description = data["description"]
    if "requires_review" in data:
        t.requires_review = bool(data["requires_review"])
    if "reviewer_person_ids" in data:
        t.reviewer_person_ids = list(data["reviewer_person_ids"] or [])

    db.commit()
    count = repo.count_items_by_type(db, actor.organisation_id, t.id)
    return item_type_dict(t, item_count=count)


def delete_item_type(db: Session, actor: Actor, type_id: str) -> None:
    t = repo.get_item_type(db, actor.organisation_id, type_id)
    if not t:
        raise NotFoundError("Item type")
    count = repo.count_items_by_type(db, actor.organisation_id, type_id)
    if count > 0:
        raise ConflictError("type_in_use", "Items still use this type")
    repo.delete_item_type(db, t)
    db.commit()


def _check_reviewer(item_type: ItemType, actor: Actor) -> bool:
    if actor.can(REVIEW_MANAGE):
        return True
    return actor.can(REVIEW_WRITE) and (actor.user_id in (item_type.reviewer_person_ids or []))


def list_items(
    db: Session,
    actor: Actor,
    scope: str = "mine",
    owner_person_id: str | None = None,
    type_id: str | None = None,
    statuses: list[str] | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    types_by_id = {t.id: t for t in repo.find_item_types(db, actor.organisation_id)}

    target_owner: str | None = None
    if scope == "mine":
        target_owner = actor.user_id
        if owner_person_id and owner_person_id != actor.user_id:
            if not actor.can(ITEM_READ_ALL):
                raise PortfolioError(403, "forbidden", "Filtering by another owner requires portfolio:item:read-all")
            target_owner = owner_person_id
    elif scope == "managed":
        if owner_person_id:
            if not actor.can(ITEM_READ_ALL) and owner_person_id != actor.user_id:
                raise PortfolioError(403, "forbidden", "Filtering by another owner requires portfolio:item:read-all")
            target_owner = owner_person_id

    page = max(1, page)
    page_size = max(1, min(200, page_size))
    offset = (page - 1) * page_size

    raw_items, total = repo.find_items(
        db,
        organisation_id=actor.organisation_id,
        owner_person_id=target_owner,
        type_id=type_id,
        statuses=statuses,
        q=q,
        offset=offset,
        limit=page_size,
    )

    items = []
    for item in raw_items:
        itype = types_by_id.get(item.type_id)
        is_reviewer = _check_reviewer(itype, actor) if itype else False

        # In managed scope, if caller does not have read-all, they must be owner or reviewer
        if scope == "managed" and not actor.can(ITEM_READ_ALL):
            if item.owner_person_id != actor.user_id and not is_reviewer:
                continue

        media = repo.find_media_by_item(db, actor.organisation_id, item.id)
        reviews = repo.find_reviews_by_item(db, actor.organisation_id, item.id)
        items.append(item_dict(item, actor, media=media, reviews=reviews, is_reviewer=is_reviewer))

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def create_item(db: Session, actor: Actor, data: dict) -> dict:
    type_id = data.get("type_id")
    if not type_id:
        raise RuleViolationError("missing_type", "type_id is required")
    itype = repo.get_item_type(db, actor.organisation_id, type_id)
    if not itype:
        raise NotFoundError("Item type")

    title = (data.get("title") or "").strip()
    if not title:
        raise RuleViolationError("missing_title", "title is required")

    owner_id = data.get("owner_person_id") or actor.user_id
    if owner_id != actor.user_id and not actor.can(ITEM_MANAGE):
        raise PortfolioError(403, "forbidden", "Setting owner_person_id requires portfolio:item:manage")

    item = Item(
        organisation_id=actor.organisation_id,
        type_id=type_id,
        owner_person_id=owner_id,
        title=title,
        description=data.get("description"),
        tags=list(data.get("tags") or []),
        attributes=dict(data.get("attributes") or {}),
        status=ItemStatus.DRAFT,
        created_at=clock(),
        updated_at=clock(),
    )
    repo.create_item(db, item)
    db.commit()
    is_reviewer = _check_reviewer(itype, actor)
    return item_dict(item, actor, is_reviewer=is_reviewer)


def get_item(db: Session, actor: Actor, item_id: str) -> dict:
    item = repo.get_item(db, actor.organisation_id, item_id)
    if not item:
        raise NotFoundError("Item")

    itype = repo.get_item_type(db, actor.organisation_id, item.type_id)
    is_reviewer = _check_reviewer(itype, actor) if itype else False
    is_owner = item.owner_person_id == actor.user_id

    if not is_owner and not actor.can(ITEM_READ_ALL) and not is_reviewer:
        raise NotFoundError("Item")

    media = repo.find_media_by_item(db, actor.organisation_id, item.id)
    reviews = repo.find_reviews_by_item(db, actor.organisation_id, item.id)
    return item_dict(item, actor, media=media, reviews=reviews, is_reviewer=is_reviewer)


def update_item(db: Session, actor: Actor, item_id: str, data: dict) -> dict:
    item = repo.get_item(db, actor.organisation_id, item_id)
    if not item:
        raise NotFoundError("Item")

    is_owner = item.owner_person_id == actor.user_id
    if not is_owner and not actor.can(ITEM_MANAGE):
        raise PortfolioError(403, "forbidden", "Editing requires ownership or portfolio:item:manage")

    if item.status not in (ItemStatus.DRAFT, ItemStatus.CHANGES_REQUESTED):
        raise ConflictError("not_editable", "Item is not editable in its current status")

    if "type_id" in data and data["type_id"]:
        itype = repo.get_item_type(db, actor.organisation_id, data["type_id"])
        if not itype:
            raise NotFoundError("Item type")
        item.type_id = data["type_id"]

    if "title" in data:
        title = (data["title"] or "").strip()
        if not title:
            raise RuleViolationError("missing_title", "title cannot be empty")
        item.title = title

    if "description" in data:
        item.description = data["description"]
    if "tags" in data:
        item.tags = list(data["tags"] or [])
    if "attributes" in data:
        item.attributes = dict(data["attributes"] or {})

    item.updated_at = clock()
    db.commit()

    itype = repo.get_item_type(db, actor.organisation_id, item.type_id)
    is_reviewer = _check_reviewer(itype, actor) if itype else False
    media = repo.find_media_by_item(db, actor.organisation_id, item.id)
    reviews = repo.find_reviews_by_item(db, actor.organisation_id, item.id)
    return item_dict(item, actor, media=media, reviews=reviews, is_reviewer=is_reviewer)


def delete_item(db: Session, actor: Actor, item_id: str) -> None:
    item = repo.get_item(db, actor.organisation_id, item_id)
    if not item:
        raise NotFoundError("Item")

    is_owner = item.owner_person_id == actor.user_id
    if not is_owner and not actor.can(ITEM_MANAGE):
        raise PortfolioError(403, "forbidden", "Deleting requires ownership or portfolio:item:manage")

    if item.status != ItemStatus.DRAFT:
        raise ConflictError("not_editable", "Only a draft item may be deleted")

    repo.delete_item(db, item)
    db.commit()


def submit_item(db: Session, actor: Actor, item_id: str) -> dict:
    item = repo.get_item(db, actor.organisation_id, item_id)
    if not item:
        raise NotFoundError("Item")

    is_owner = item.owner_person_id == actor.user_id
    if not is_owner and not actor.can(ITEM_MANAGE):
        raise PortfolioError(403, "forbidden", "Submitting requires ownership or portfolio:item:manage")

    if item.status not in (ItemStatus.DRAFT, ItemStatus.CHANGES_REQUESTED):
        raise ConflictError("not_submittable", "Item is not in a submittable status")

    itype = repo.get_item_type(db, actor.organisation_id, item.type_id)
    now = clock()
    item.submitted_at = now
    item.updated_at = now

    if itype and not itype.requires_review:
        item.status = ItemStatus.APPROVED
        item.decided_at = now
    else:
        item.status = ItemStatus.SUBMITTED

    _publish(
        db,
        actor,
        "item.submitted",
        actor.organisation_id,
        {
            "item_id": item.id,
            "type_id": item.type_id,
            "owner_person_id": item.owner_person_id,
        },
    )
    db.commit()

    media = repo.find_media_by_item(db, actor.organisation_id, item.id)
    reviews = repo.find_reviews_by_item(db, actor.organisation_id, item.id)
    is_reviewer = _check_reviewer(itype, actor) if itype else False
    return item_dict(item, actor, media=media, reviews=reviews, is_reviewer=is_reviewer)


def withdraw_item(db: Session, actor: Actor, item_id: str) -> dict:
    item = repo.get_item(db, actor.organisation_id, item_id)
    if not item:
        raise NotFoundError("Item")

    is_owner = item.owner_person_id == actor.user_id
    if not is_owner and not actor.can(ITEM_MANAGE):
        raise PortfolioError(403, "forbidden", "Withdrawing requires ownership or portfolio:item:manage")

    if item.status in (ItemStatus.APPROVED, ItemStatus.DRAFT):
        raise ConflictError("already_decided", "Item has already been decided")

    if item.status not in (ItemStatus.SUBMITTED, ItemStatus.UNDER_REVIEW):
        raise ConflictError("already_decided", "Item cannot be withdrawn in its current status")

    now = clock()
    item.status = ItemStatus.DRAFT
    item.updated_at = now

    _publish(
        db,
        actor,
        "item.withdrawn",
        actor.organisation_id,
        {
            "item_id": item.id,
        },
    )
    db.commit()

    itype = repo.get_item_type(db, actor.organisation_id, item.type_id)
    media = repo.find_media_by_item(db, actor.organisation_id, item.id)
    reviews = repo.find_reviews_by_item(db, actor.organisation_id, item.id)
    is_reviewer = _check_reviewer(itype, actor) if itype else False
    return item_dict(item, actor, media=media, reviews=reviews, is_reviewer=is_reviewer)


def list_media(db: Session, actor: Actor, item_id: str) -> list[dict]:
    get_item(db, actor, item_id)
    media = repo.find_media_by_item(db, actor.organisation_id, item_id)
    return [media_dict(m) for m in media]


def add_media(db: Session, actor: Actor, item_id: str, data: dict) -> dict:
    item = repo.get_item(db, actor.organisation_id, item_id)
    if not item:
        raise NotFoundError("Item")

    is_owner = item.owner_person_id == actor.user_id
    if not is_owner and not actor.can(ITEM_MANAGE):
        raise PortfolioError(403, "forbidden", "Adding media requires ownership or portfolio:item:manage")

    doc_id = (data.get("document_id") or "").strip()
    if not doc_id:
        raise RuleViolationError("missing_document", "document_id is required")

    media = ItemMedia(
        organisation_id=actor.organisation_id,
        item_id=item_id,
        document_id=doc_id,
        caption=data.get("caption"),
        sort_order=int(data.get("sort_order") or 0),
        uploaded_by=actor.user_id,
        uploaded_at=clock(),
    )
    repo.create_media(db, media)
    db.commit()
    return media_dict(media)


def delete_media(db: Session, actor: Actor, item_id: str, media_id: str) -> None:
    item = repo.get_item(db, actor.organisation_id, item_id)
    if not item:
        raise NotFoundError("Item")

    is_owner = item.owner_person_id == actor.user_id
    if not is_owner and not actor.can(ITEM_MANAGE):
        raise PortfolioError(403, "forbidden", "Deleting media requires ownership or portfolio:item:manage")

    media = repo.get_media(db, actor.organisation_id, media_id)
    if not media or media.item_id != item_id:
        raise NotFoundError("Media")

    repo.delete_media(db, media)
    db.commit()


def list_reviews(db: Session, actor: Actor, item_id: str) -> list[dict]:
    get_item(db, actor, item_id)
    reviews = repo.find_reviews_by_item(db, actor.organisation_id, item_id)
    return [review_dict(r) for r in reviews]


def add_review(db: Session, actor: Actor, item_id: str, data: dict) -> dict:
    item = repo.get_item(db, actor.organisation_id, item_id)
    if not item:
        raise NotFoundError("Item")

    if item.status not in (ItemStatus.SUBMITTED, ItemStatus.UNDER_REVIEW):
        raise ConflictError("not_under_review", "Item is not under review")

    itype = repo.get_item_type(db, actor.organisation_id, item.type_id)
    if not itype:
        raise NotFoundError("Item type")

    if not _check_reviewer(itype, actor):
        raise PortfolioError(403, "forbidden", "You are not a designated reviewer for this item type")

    decision = data.get("decision")
    if decision not in (ReviewDecision.APPROVED, ReviewDecision.CHANGES_REQUESTED):
        raise RuleViolationError("invalid_decision", "Decision must be approved or changes_requested")

    now = clock()
    rev = Review(
        organisation_id=actor.organisation_id,
        item_id=item_id,
        reviewer_person_id=actor.user_id,
        decision=decision,
        score=data.get("score"),
        comments=data.get("comments"),
        reviewed_at=now,
    )
    repo.create_review(db, rev)

    if decision == ReviewDecision.APPROVED:
        item.status = ItemStatus.APPROVED
        item.decided_at = now
    else:
        item.status = ItemStatus.CHANGES_REQUESTED
        item.decided_at = now

    item.updated_at = now

    _publish(
        db,
        actor,
        "item.reviewed",
        actor.organisation_id,
        {
            "item_id": item.id,
            "review_id": rev.id,
            "decision": decision,
            "reviewer_person_id": actor.user_id,
        },
    )
    db.commit()

    return review_dict(rev)
