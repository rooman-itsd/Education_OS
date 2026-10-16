"""Tables owned by notification. Every table carries organisation_id NOT NULL (stricter than TenantMixin, which
allows NULL: a NULL organisation would bypass every unique constraint below and is invisible to tenant
sessions) and gets the tenant_isolation row-level-security policy from eos_core.init_db or the Alembic chain."""

from __future__ import annotations

from datetime import datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, CheckConstraint, DateTime, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

CHANNELS = ("email", "sms", "whatsapp", "push", "in_app")
CATEGORIES = ("transactional", "operational", "reminder", "announcement")

QUEUED, SENDING, SENT, DELIVERED, FAILED, BOUNCED, SUPPRESSED = (
    "queued",
    "sending",
    "sent",
    "delivered",
    "failed",
    "bounced",
    "suppressed",
)
STATUSES = (QUEUED, SENDING, SENT, DELIVERED, FAILED, BOUNCED, SUPPRESSED)

# status -> statuses it may move to. Every change is one guarded UPDATE (see application/service.py), so a
# second worker that lost a race changes nothing.
TRANSITIONS: dict[str, frozenset[str]] = {
    QUEUED: frozenset({SENDING, SUPPRESSED, DELIVERED, FAILED}),  # DELIVERED: in_app; FAILED: secret lost
    SENDING: frozenset({QUEUED, SENT, FAILED, DELIVERED, BOUNCED}),
    SENT: frozenset({DELIVERED, BOUNCED, FAILED}),
    DELIVERED: frozenset({BOUNCED}),
    FAILED: frozenset({QUEUED}),
    BOUNCED: frozenset({QUEUED}),
    SUPPRESSED: frozenset(),
}

TABLE_NAMES = ("notification_message", "notification_template", "notification_preference")


class Message(Base, TenantMixin, TimestampMixin):
    """One row per message and recipient. Holds no secret: secret variables are rendered in memory and never
    stored, and a rendered email body is never stored (only an in_app body is, because the inbox shows it)."""

    __tablename__ = "notification_message"
    __table_args__ = (
        UniqueConstraint("organisation_id", "client_token", name="uq_notification_message_org_token"),
        UniqueConstraint(
            "organisation_id",
            "source_event_id",
            "template_key",
            "channel",
            "recipient_key",
            name="uq_notification_message_org_event",
        ),
        CheckConstraint("organisation_id <> ''", name="ck_notification_message_org_nonempty"),
        Index("ix_notification_message_inbox", "organisation_id", "recipient_id", "created_at"),
        Index("ix_notification_message_status", "organisation_id", "status", "created_at"),
        Index("ix_notification_message_dispatch", "status", "next_attempt_at"),
        Index("ix_notification_message_lease", "status", "lease_expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    template_key: Mapped[str] = mapped_column(String(120))
    channel: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(20), default="operational")
    status: Mapped[str] = mapped_column(String(20), default=QUEUED)
    recipient_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    recipient_key: Mapped[str] = mapped_column(String(254))
    recipient_address: Mapped[str | None] = mapped_column(String(254), nullable=True)
    locale: Mapped[str | None] = mapped_column(String(10), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(300), nullable=True)
    variables: Mapped[dict] = mapped_column(JSON, default=dict)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The template text (placeholders only, never values) chosen at acceptance. Sending renders from this, so a
    # template edited after acceptance does not change a message already accepted.
    body_template: Mapped[str] = mapped_column(Text)
    client_token: Mapped[str | None] = mapped_column(String(120), nullable=True)
    request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)  # provider calls only
    # Recovery bookkeeping, kept apart from delivery: how often recovery itself failed on this message, and the
    # exception class of the last such failure (never its text, which may carry values).
    recovery_failures: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    last_recovery_error: Mapped[str | None] = mapped_column(String(60), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TemplateOverride(Base, TenantMixin, TimestampMixin):
    """An organisation's wording for a platform template. The category, placeholders and secret handling always
    come from the trusted default in code, so they are not stored here."""

    __tablename__ = "notification_template"
    __table_args__ = (
        UniqueConstraint("organisation_id", "key", "channel", "locale", name="uq_notification_template_org_key"),
        CheckConstraint("organisation_id <> ''", name="ck_notification_template_org_nonempty"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    key: Mapped[str] = mapped_column(String(120))
    channel: Mapped[str] = mapped_column(String(20))
    locale: Mapped[str] = mapped_column(String(10))
    subject: Mapped[str | None] = mapped_column(String(300), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Preference(Base, TenantMixin, TimestampMixin):
    __tablename__ = "notification_preference"
    __table_args__ = (
        UniqueConstraint("organisation_id", "user_id", name="uq_notification_preference_org_user"),
        CheckConstraint("organisation_id <> ''", name="ck_notification_preference_org_nonempty"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36))
    locale: Mapped[str | None] = mapped_column(String(10), nullable=True)
    channels: Mapped[dict] = mapped_column(JSON, default=dict)
    quiet_hours: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
