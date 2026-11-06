"""Tables of integration-hub (docs/data-model.md). One shared schema with the integration_hub_ prefix and its own
Alembic chain; every table carries organisation_id (TenantMixin) and gets the tenant_isolation row-level-security
policy on Postgres. No secret is ever stored here: credentials and tokens are references into the secret store, and the
sensitive blobs that must be kept for a while (an async delivery's input, a raw callback, a PKCE verifier) are
AES-GCM encrypted and purged on short retention.

The adapter registry is not a table: it is rebuilt from each adapter's describe() when the process starts
(infrastructure/registry.py)."""

from __future__ import annotations

from datetime import datetime

from eos_core.db import Base, TenantMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "integration_hub_"


def _ts(nullable: bool = True, **kw) -> Mapped:
    return mapped_column(DateTime(timezone=True), nullable=nullable, **kw)


class Connection(Base, TenantMixin):
    """One organisation's configuration of one adapter, provider and port. `connection_key_hash` is the SHA-256 of the
    random key in its inbound URLs; the key itself is in the secret store. `changed_at` moves on every change that
    can fix a failing delivery (credentials, settings, mode, authorisation), so a retry of a non-retryable failure is
    allowed once the connection changed."""

    __tablename__ = f"{PREFIX}connection"
    __table_args__ = (
        Index("ix_integration_hub_connection_port", "organisation_id", "port", "provider", "enabled"),
        Index("ix_integration_hub_connection_key", "connection_key_hash", unique=True),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    adapter: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(64))
    port: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(10))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    connection_key_hash: Mapped[str] = mapped_column(String(64))
    authorised: Mapped[bool] = mapped_column(Boolean, default=False)
    health_status: Mapped[str] = mapped_column(String(20), default="not_checked")
    health_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    health_checked_at: Mapped[datetime | None] = _ts()
    expires_at: Mapped[datetime | None] = _ts()
    health_window_start: Mapped[datetime | None] = _ts()
    health_window_runs: Mapped[int] = mapped_column(Integer, default=0)
    throttled_until: Mapped[datetime | None] = _ts()
    disabled_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = _ts(nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = _ts(nullable=False, default=utcnow)
    changed_at: Mapped[datetime] = _ts(nullable=False, default=utcnow)


class ConnectionCredential(Base, TenantMixin):
    """Which credential is set: a reference, a fingerprint, who and when. Never the value."""

    __tablename__ = f"{PREFIX}connection_credential"
    __table_args__ = (UniqueConstraint("connection_id", "name", name="uq_integration_hub_credential_name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    connection_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}connection.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    secret_ref: Mapped[str] = mapped_column(String(300))
    fingerprint: Mapped[str] = mapped_column(String(8))
    source: Mapped[str] = mapped_column(String(10))
    set_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    set_at: Mapped[datetime] = _ts(nullable=False)
    expires_at: Mapped[datetime | None] = _ts()


class AccountLink(Base, TenantMixin):
    """One person's authorisation at a person-scope provider. Tokens are in the secret store under `secret_ref`."""

    __tablename__ = f"{PREFIX}account_link"
    __table_args__ = (
        Index("ix_integration_hub_link_person", "organisation_id", "person_id", "status"),
        Index("ix_integration_hub_link_subject", "provider", "provider_subject"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    connection_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}connection.id"), index=True)
    person_id: Mapped[str] = mapped_column(String(36))
    port: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(64))
    provider_subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="pending")
    purpose: Mapped[str | None] = mapped_column(String(200), nullable=True)
    granted_scopes: Mapped[list] = mapped_column(JSON, default=list)
    secret_ref: Mapped[str | None] = mapped_column(String(300), nullable=True)
    linked_at: Mapped[datetime | None] = _ts()
    expires_at: Mapped[datetime | None] = _ts()
    last_synced_at: Mapped[datetime | None] = _ts()
    revoked_at: Mapped[datetime | None] = _ts()
    revoke_cause: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = _ts(nullable=False, default=utcnow)


class OAuthState(Base, TenantMixin):
    """A pending authorisation: single use, bound to the organisation, the connection or link, the person and the
    browser that started it, expiring after INTEGRATION_HUB_OAUTH_STATE_TTL_S. Only the state's hash is kept, and only
    the hash of the browser's binding nonce (the nonce itself is in an HttpOnly cookie); the PKCE verifier is
    encrypted."""

    __tablename__ = f"{PREFIX}oauth_state"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    state_hash: Mapped[str] = mapped_column(String(64), unique=True)
    adapter: Mapped[str] = mapped_column(String(64))
    connection_id: Mapped[str] = mapped_column(String(36))
    account_link_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    person_id: Mapped[str] = mapped_column(String(36))
    browser_binding_hash: Mapped[str] = mapped_column(String(64))
    code_verifier_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    return_url: Mapped[str] = mapped_column(String(2048))
    expires_at: Mapped[datetime] = _ts(nullable=False)
    used_at: Mapped[datetime | None] = _ts()
    created_at: Mapped[datetime] = _ts(nullable=False, default=utcnow)


class Delivery(Base, TenantMixin):
    """One row of the log per port operation (outbound) or provider callback (inbound). Never the payload in clear:
    `payload_encrypted` holds an async operation's input only so it can be retried, and is purged.

    `subject_key` is the caller's key for the port object (meeting_key, issuance_key, package_key, ...), `object_id` the
    id the adapter gave it (package_id, submission_id, exchange_id, ...), `person_id` the person it is about, and `refs`
    a few non-personal keys of the input (doc_kind, form_code, period, partner_id, format), so a later operation or
    callback can be matched to the module that asked and its event filled in. Never names, documents or readings."""

    __tablename__ = f"{PREFIX}delivery"
    __table_args__ = (
        Index("ix_integration_hub_delivery_listing", "organisation_id", "created_at"),
        Index("ix_integration_hub_delivery_due", "status", "next_attempt_at"),
        Index("ix_integration_hub_delivery_idempotency", "organisation_id", "caller_module", "idempotency_key"),
        Index("ix_integration_hub_delivery_subject", "organisation_id", "port", "subject_key"),
        Index("ix_integration_hub_delivery_object", "organisation_id", "port", "object_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    direction: Mapped[str] = mapped_column(String(10))
    connection_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    account_link_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    port: Mapped[str] = mapped_column(String(64))
    operation: Mapped[str] = mapped_column(String(80))
    sync: Mapped[bool] = mapped_column(Boolean, default=False)
    mode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    caller_module: Mapped[str | None] = mapped_column(String(64), nullable=True)
    caller_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    subject_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    person_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    refs: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = _ts()
    last_error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payload_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    inbound_receipt_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = _ts(nullable=False, default=utcnow)
    started_at: Mapped[datetime | None] = _ts()
    completed_at: Mapped[datetime | None] = _ts()


class DeliveryAttempt(Base, TenantMixin):
    __tablename__ = f"{PREFIX}delivery_attempt"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    delivery_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}delivery.id"), index=True)
    attempt: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = _ts(nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    outcome: Mapped[str] = mapped_column(String(10))
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider_code: Mapped[str | None] = mapped_column(String(40), nullable=True)


class InboundReceipt(Base, TenantMixin):
    """One provider callback as it arrived. Written by the hub's platform role before the tenant is known (an app-level
    callback); organisation_id is set once verify_inbound names the connection. The raw body and headers are encrypted
    and purged after INTEGRATION_HUB_INBOUND_RAW_RETENTION_DAYS.

    Requests that fail verification are not one row each: one `rejected` row per source (`connection:<id>`, or
    `ip:<hash>` on an app-level URL) and minute (`window_start`) counts them in `rejected_count`, and is purged after
    INTEGRATION_HUB_INBOUND_REJECTED_RETENTION_DAYS."""

    __tablename__ = f"{PREFIX}inbound_receipt"
    __table_args__ = (
        # Per connection: two organisations' connections at one provider may see the same event id.
        UniqueConstraint("connection_id", "dedupe_key", name="uq_integration_hub_inbound_dedupe"),
        UniqueConstraint("adapter", "source", "window_start", name="uq_integration_hub_inbound_rejected_window"),
        Index("ix_integration_hub_inbound_received", "received_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    adapter: Mapped[str] = mapped_column(String(64))
    connection_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(41), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    verdict: Mapped[str] = mapped_column(String(12))
    source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    window_start: Mapped[datetime | None] = _ts()
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    received_at: Mapped[datetime] = _ts(nullable=False, default=utcnow)
    processed_at: Mapped[datetime | None] = _ts()
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


TABLES = [
    m.__table__
    for m in (Connection, ConnectionCredential, AccountLink, OAuthState, Delivery, DeliveryAttempt, InboundReceipt)
]
