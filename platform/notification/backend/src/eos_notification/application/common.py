from __future__ import annotations

import uuid
from datetime import UTC, datetime

from eos_core.tenant import resolve_organisation
from sqlalchemy.orm import Session

from ..domain.errors import NotificationError


def organisation_of(db: Session) -> str:
    """The organisation this session runs as. Fails closed: with none there is nothing to act on, and a
    platform-level (organisation-less) message is not supported in this release."""
    org = resolve_organisation(db)
    if not org:
        raise NotificationError(403, "this operation needs an organisation context")
    return org


def aware(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; every stored time is UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def utc_now() -> datetime:
    return datetime.now(UTC)


def canonical_uuid(value: str | None, what: str) -> str | None:
    """Store ids in one canonical form so an upper-case or braced variant cannot defeat deduplication."""
    if value is None:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        raise NotificationError(422, f"{what} is not a valid id") from None
