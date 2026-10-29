"""SQLAlchemy models for web-portal-cms. Every table is prefixed web_portal_cms_ and carries organisation_id; the
migration puts the tenant_isolation row-level-security policy on each. to_dict() returns the contract's field
names."""

from __future__ import annotations

from datetime import UTC, datetime

from eos_core.db import Base, TenantMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "web_portal_cms_"


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; every stored datetime is UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | None) -> str | None:
    return as_utc(value).isoformat() if value is not None else None


class Page(Base, TenantMixin):
    __tablename__ = f"{PREFIX}page"
    __table_args__ = (
        Index(f"ix_{PREFIX}page_organisation_id", "organisation_id"),
        Index(f"uq_{PREFIX}page_slug", "organisation_id", "slug", unique=True),
        Index(f"ix_{PREFIX}page_listing", "organisation_id", "published", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    seo_description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "organisation_id": self.organisation_id,
            "slug": self.slug,
            "title": self.title,
            "type": self.type,
            "body": self.body,
            "seo_description": self.seo_description,
            "published": self.published,
            "published_at": iso(self.published_at),
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }


class Announcement(Base, TenantMixin):
    __tablename__ = f"{PREFIX}announcement"
    __table_args__ = (
        Index(f"ix_{PREFIX}announcement_organisation_id", "organisation_id"),
        Index(f"ix_{PREFIX}announcement_listing", "organisation_id", "published", "published_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        """Contract Announcement without `visible`, which depends on the time of the request."""
        return {
            "id": self.id,
            "organisation_id": self.organisation_id,
            "title": self.title,
            "body": self.body,
            "starts_at": iso(self.starts_at),
            "ends_at": iso(self.ends_at),
            "published": self.published,
            "published_at": iso(self.published_at),
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }


class AuditEntry(Base, TenantMixin):
    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (
        Index(f"ix_{PREFIX}audit_entry_organisation_id", "organisation_id"),
        Index(f"ix_{PREFIX}audit_entry_entity", "entity", "entity_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    entity: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


MODELS = (Page, Announcement, AuditEntry)
TABLES = [m.__table__ for m in MODELS]
