"""Data access for portfolio tables. All queries filter by organisation_id."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .models import Item, ItemMedia, ItemType, Review


def find_item_types(db: Session, organisation_id: str) -> list[ItemType]:
    stmt = select(ItemType).where(ItemType.organisation_id == organisation_id).order_by(ItemType.name.asc())
    return list(db.scalars(stmt).all())


def get_item_type(db: Session, organisation_id: str, type_id: str) -> ItemType | None:
    stmt = select(ItemType).where(
        ItemType.organisation_id == organisation_id,
        ItemType.id == type_id,
    )
    return db.scalars(stmt).first()


def get_item_type_by_name(db: Session, organisation_id: str, name: str) -> ItemType | None:
    stmt = select(ItemType).where(
        ItemType.organisation_id == organisation_id,
        ItemType.name == name,
    )
    return db.scalars(stmt).first()


def count_items_by_type(db: Session, organisation_id: str, type_id: str) -> int:
    stmt = select(func.count(Item.id)).where(Item.organisation_id == organisation_id, Item.type_id == type_id)
    return db.scalar(stmt) or 0


def create_item_type(db: Session, item_type: ItemType) -> ItemType:
    db.add(item_type)
    db.flush()
    return item_type


def delete_item_type(db: Session, item_type: ItemType) -> None:
    db.delete(item_type)
    db.flush()


def find_items(
    db: Session,
    organisation_id: str,
    owner_person_id: str | None = None,
    type_id: str | None = None,
    statuses: list[str] | None = None,
    q: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Item], int]:
    base_where = [Item.organisation_id == organisation_id]
    if owner_person_id:
        base_where.append(Item.owner_person_id == owner_person_id)
    if type_id:
        base_where.append(Item.type_id == type_id)
    if statuses:
        base_where.append(Item.status.in_(statuses))
    if q:
        term = f"%{q.lower()}%"
        base_where.append(
            or_(
                func.lower(Item.title).like(term),
                func.lower(Item.description).like(term),
            )
        )

    count_stmt = select(func.count(Item.id)).where(*base_where)
    total = db.scalar(count_stmt) or 0

    stmt = select(Item).where(*base_where).order_by(Item.updated_at.desc()).offset(offset).limit(limit)
    items = list(db.scalars(stmt).all())
    return items, total


def get_item(db: Session, organisation_id: str, item_id: str) -> Item | None:
    stmt = select(Item).where(
        Item.organisation_id == organisation_id,
        Item.id == item_id,
    )
    return db.scalars(stmt).first()


def create_item(db: Session, item: Item) -> Item:
    db.add(item)
    db.flush()
    return item


def delete_item(db: Session, item: Item) -> None:
    db.delete(item)
    db.flush()


def find_media_by_item(db: Session, organisation_id: str, item_id: str) -> list[ItemMedia]:
    stmt = (
        select(ItemMedia)
        .where(ItemMedia.organisation_id == organisation_id, ItemMedia.item_id == item_id)
        .order_by(ItemMedia.sort_order.asc(), ItemMedia.uploaded_at.asc())
    )
    return list(db.scalars(stmt).all())


def get_media(db: Session, organisation_id: str, media_id: str) -> ItemMedia | None:
    stmt = select(ItemMedia).where(
        ItemMedia.organisation_id == organisation_id,
        ItemMedia.id == media_id,
    )
    return db.scalars(stmt).first()


def create_media(db: Session, media: ItemMedia) -> ItemMedia:
    db.add(media)
    db.flush()
    return media


def delete_media(db: Session, media: ItemMedia) -> None:
    db.delete(media)
    db.flush()


def find_reviews_by_item(db: Session, organisation_id: str, item_id: str) -> list[Review]:
    stmt = (
        select(Review)
        .where(Review.organisation_id == organisation_id, Review.item_id == item_id)
        .order_by(Review.reviewed_at.desc())
    )
    return list(db.scalars(stmt).all())


def create_review(db: Session, review: Review) -> Review:
    db.add(review)
    db.flush()
    return review
