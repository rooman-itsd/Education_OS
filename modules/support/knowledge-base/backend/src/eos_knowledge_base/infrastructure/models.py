"""Tables of knowledge-base (PRD "Data model"). Every table carries organisation_id, so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name and no foreign key leaves this
module: owner, author, reviewer and reader ids are identity person ids, and references point to records in other
modules, all by id only (PRD "Rules")."""

from __future__ import annotations

from datetime import date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "knowledge_base_"


class Category(Base, TenantMixin, TimestampMixin):
    """One node of the two-level category tree (contract Category). parent_id is null for a top-level category."""

    __tablename__ = f"{PREFIX}category"
    __table_args__ = (Index("ix_knowledge_base_category_parent", "organisation_id", "parent_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}category.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Article(Base, TenantMixin, TimestampMixin):
    """An article (contract Article). Content lives in revisions: published_revision_no is what readers see,
    open_revision_no the draft or revision in review, last_revision_no the highest number given so far. Counts are
    kept on the row so browse and sort never scan feedback or views."""

    __tablename__ = f"{PREFIX}article"
    __table_args__ = (
        UniqueConstraint("organisation_id", "slug", name="uq_knowledge_base_article_slug"),
        Index("ix_knowledge_base_article_status", "organisation_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(12))
    owner_id: Mapped[str] = mapped_column(String(36))
    review_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    published_revision_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    open_revision_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_revision_no: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    helpful_count: Mapped[int] = mapped_column(Integer, default=0)
    not_helpful_count: Mapped[int] = mapped_column(Integer, default=0)
    first_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Revision(Base, TenantMixin, TimestampMixin):
    """One numbered revision of an article's content (contract Revision). Never deleted: superseded or discarded."""

    __tablename__ = f"{PREFIX}revision"
    __table_args__ = (
        UniqueConstraint("article_id", "revision_no", name="uq_knowledge_base_revision_no"),
        Index("ix_knowledge_base_revision_category", "organisation_id", "category_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    article_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}article.id"))
    revision_no: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(12))
    type: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    category_id: Mapped[str] = mapped_column(String(36))
    tags: Mapped[list] = mapped_column(JSON, default=list)
    audience: Mapped[str] = mapped_column(String(10))
    related_article_ids: Mapped[list] = mapped_column(JSON, default=list)
    references: Mapped[list] = mapped_column("refs", JSON, default=list)  # "references" is an SQL keyword
    author_id: Mapped[str] = mapped_column(String(36))
    change_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Feedback(Base, TenantMixin):
    """One vote per person per article (contract Feedback); a new vote replaces the earlier one."""

    __tablename__ = f"{PREFIX}feedback"
    __table_args__ = (UniqueConstraint("article_id", "person_id", name="uq_knowledge_base_feedback_person"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    article_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}article.id"))
    person_id: Mapped[str] = mapped_column(String(36))
    helpful: Mapped[bool] = mapped_column(Boolean)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision_no: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ViewDay(Base, TenantMixin):
    """Views of an article on one day (PRD "stored as daily totals per article"). Behind the top-articles periods."""

    __tablename__ = f"{PREFIX}view_day"
    __table_args__ = (UniqueConstraint("article_id", "day", name="uq_knowledge_base_view_day"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    article_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}article.id"))
    day: Mapped[date] = mapped_column(Date)
    views: Mapped[int] = mapped_column(Integer, default=0)


class ViewSeen(Base, TenantMixin):
    """Who already counted a view of an article today, so a view counts at most once per reader per day (PRD rule).
    reader_key is a hash of the organisation, article, reader and day, so it cannot be joined to a person or across
    days; rows of earlier days are deleted whenever a view is counted, so no reading history is kept."""

    __tablename__ = f"{PREFIX}view_seen"
    __table_args__ = (UniqueConstraint("article_id", "day", "reader_key", name="uq_knowledge_base_view_seen"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    article_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}article.id"))
    day: Mapped[date] = mapped_column(Date)
    reader_key: Mapped[str] = mapped_column(String(64))


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change of categories, articles and revisions (PRD rule "Every state
    change writes an audit record"). Stands in for the audit SDK, which does not exist yet (packages/sdk is empty), as
    helpdesk's and amc-vendor-support's do; its rows are not in the platform audit trail. `reason` keeps the reason or
    comment a caller gives (archive, return). Titles, bodies and feedback are never copied here."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_knowledge_base_audit_entity", "organisation_id", "entity", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


MODELS = (Category, Article, Revision, Feedback, ViewDay, ViewSeen, AuditEntry)
TABLES = [m.__table__ for m in MODELS]
