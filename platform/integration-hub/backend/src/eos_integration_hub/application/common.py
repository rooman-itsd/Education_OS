"""Helpers every use case shares: the clock, audit and outbox in the caller's transaction, tenant-scoped lookups,
cursor pages, rendering, and building an adapter context with the connection's secrets resolved for one call."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from eos_audit.application import service as audit
from eos_core import events
from eos_core.db import scoped, utcnow
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.errors import HubError, not_found
from ..domain.vocabulary import MODULE
from ..infrastructure.config import HubConfig
from ..infrastructure.models import AccountLink, Connection, ConnectionCredential
from ..infrastructure.registry import AdapterContext, AdapterInfo, ProviderInfo, get_registry
from ..infrastructure.secrets import SecretStore, SecretStoreError, get_store

log = logging.getLogger("eos.integration_hub")


def clock() -> datetime:
    """Now, in UTC. Tests replace it."""
    return utcnow()


def aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def iso(value: datetime | None) -> str | None:
    value = aware(value)
    return value.astimezone(UTC).isoformat() if value else None


@dataclass
class Actor:
    """Who acts: a signed-in person (user_id, organisation_id, permissions) or the hub itself (user_id None)."""

    user_id: str | None
    organisation_id: str | None
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


def publish(db: Session, organisation_id: str | None, name: str, payload: dict, actor: str | None = None) -> None:
    """An integration-hub.* event in the caller's transaction. Payloads carry ids, keys and statuses only."""
    body = {"organisation_id": organisation_id, **payload} if organisation_id else dict(payload)
    events.publish(db, f"{MODULE}.{name}", organisation_id, body, actor=actor)


def record(
    db: Session,
    organisation_id: str | None,
    actor: str | None,
    action: str,
    entity_type: str,
    entity_id: str,
    after: dict | None = None,
    context: dict | None = None,
) -> None:
    """One audit record through platform/audit, in the same transaction as the change. Never a value: names,
    fingerprints, modes and statuses."""
    audit.record(
        db,
        organisation_id=organisation_id,
        actor=actor,
        module=MODULE,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        after=after,
        context=context,
    )


def adapter_or_409(name: str) -> AdapterInfo:
    info = get_registry().get(name)
    if info is None:
        raise HubError(409, "adapter_not_installed", f"adapter {name} is not installed")
    return info


def provider_of(connection: Connection) -> tuple[AdapterInfo | None, ProviderInfo | None]:
    info = get_registry().get(connection.adapter)
    return info, (info.provider(connection.provider) if info else None)


def get_connection(db: Session, connection_id: str, *, lock: bool = False) -> Connection:
    q = scoped(db, select(Connection), Connection).where(Connection.id == connection_id)
    if lock:
        q = q.with_for_update()
    row = db.scalar(q)
    if row is None:
        raise not_found("connection")
    return row


def get_link(db: Session, link_id: str) -> AccountLink:
    row = db.scalar(scoped(db, select(AccountLink), AccountLink).where(AccountLink.id == link_id))
    if row is None:
        raise not_found("account link")
    return row


def store_or_503(config: HubConfig | None = None) -> SecretStore:
    try:
        return get_store(config)
    except SecretStoreError as e:
        raise HubError(503, "secret_store_unavailable", str(e)) from e


def credentials_of(db: Session, connection: Connection) -> list[ConnectionCredential]:
    q = select(ConnectionCredential).where(
        ConnectionCredential.connection_id == connection.id,
        ConnectionCredential.organisation_id == connection.organisation_id,
    )
    return list(db.scalars(q.order_by(ConnectionCredential.name)))


def missing_credentials(db: Session, connection: Connection, provider: ProviderInfo) -> list[str]:
    have = {c.name for c in credentials_of(db, connection)}
    return [n for n in provider.credential_names if n not in have]


def resolve_secrets(db: Session, connection: Connection, store: SecretStore | None = None) -> dict[str, str]:
    """Every credential of the connection, read from the secret store into memory for one call. A missing value is
    left out (the adapter answers not_configured); an unreadable store is an error the caller records."""
    store = store or get_store()
    out: dict[str, str] = {}
    for cred in credentials_of(db, connection):
        value = store.get(cred.secret_ref)
        if value is not None:
            out[cred.name] = value
    return out


def link_secrets(link: AccountLink, store: SecretStore | None = None) -> dict[str, str]:
    if not link.secret_ref:
        return {}
    raw = (store or get_store()).get(link.secret_ref)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return (
        {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)} if isinstance(data, dict) else {}
    )


def context_for(
    connection: Connection,
    *,
    secrets: dict | None = None,
    link: AccountLink | None = None,
    delivery_id: str | None = None,
    attempt: int = 1,
    idempotency_key: str | None = None,
    timeout_s: int | None = None,
    port: str | None = None,
    operation: str | None = None,
    mode: str | None = None,
) -> AdapterContext:
    return AdapterContext(
        organisation_id=connection.organisation_id,
        connection_id=connection.id,
        provider=connection.provider,
        mode=mode or connection.mode,
        settings=dict(connection.settings or {}),
        secrets=dict(secrets or {}),
        account_link={"id": link.id, "person_id": link.person_id, "provider_subject": link.provider_subject}
        if link
        else None,
        delivery_id=delivery_id,
        attempt=attempt,
        idempotency_key=idempotency_key,
        deadline=clock() + timedelta(seconds=timeout_s) if timeout_s else None,
        port=port or connection.port,
        operation=operation,
    )


def offset_of(cursor: str | None) -> int:
    """The cursor is the offset this API returned as next_cursor; anything else is 400 invalid_cursor."""
    if cursor is None:
        return 0
    if not cursor.isdigit() or len(cursor) > 9:
        raise HubError(400, "invalid_cursor", "invalid cursor")
    return int(cursor)


def page(db: Session, q, cursor: str | None, limit: int, render) -> dict:
    offset = offset_of(cursor)
    rows = list(db.scalars(q.offset(offset).limit(limit + 1)))
    return {
        "items": [render(r) for r in rows[:limit]],
        "next_cursor": str(offset + limit) if len(rows) > limit else None,
    }
