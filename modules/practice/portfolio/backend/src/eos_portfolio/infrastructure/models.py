"""SQLAlchemy models for portfolio. Every table carries organisation_id (TenantMixin).
Table names are prefixed with portfolio_; no foreign key leaves this module."""

from __future__ import annotations

from datetime import UTC, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "portfolio_"


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; everything stored is UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | None) -> str | None:
    value = as_utc(value)
    return value.isoformat() if value else None


class ItemType(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}item_type"
    __table_args__ = (UniqueConstraint("organisation_id", "name", name="uq_portfolio_item_type_org_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reviewer_person_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class Item(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}item"
    __table_args__ = (Index("ix_portfolio_item_owner", "organisation_id", "owner_person_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    type_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}item_type.id"), index=True, nullable=False)
    owner_person_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ItemMedia(Base, TenantMixin):
    __tablename__ = f"{PREFIX}item_media"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}item.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[str] = mapped_column(String(100), nullable=False)
    caption: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(36), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Review(Base, TenantMixin):
    __tablename__ = f"{PREFIX}review"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}item.id", ondelete="CASCADE"), index=True, nullable=False
    )
    reviewer_person_id: Mapped[str] = mapped_column(String(36), nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


TABLES = [m.__table__ for m in (ItemType, Item, ItemMedia, Review)]
