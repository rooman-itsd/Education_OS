"""Who a message goes to. Addresses are resolved from identity at send time, never cached here: identity has no
change-email flow today, so a copy would go stale with nothing to refresh it."""

from __future__ import annotations

import re
from dataclasses import dataclass

from eos_identity.application.service import get_user
from sqlalchemy.orm import Session

from ..domain.errors import NotificationError
from .common import canonical_uuid

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_NO_ADDRESS = "no address for the channel"


@dataclass(frozen=True)
class Recipient:
    user_id: str | None
    address: str | None
    key: str
    locale: str | None


def user_in_organisation(db: Session, organisation_id: str, user_id: str):
    """The identity user, only if it belongs to this organisation and is active. Never reveals another tenant's."""
    user = get_user(db, user_id)
    if user is None or user.organisation_id != organisation_id or user.status != "active":
        return None
    return user


def resolve(db: Session, organisation_id: str, recipient: dict, channel: str) -> Recipient:
    locale = ((recipient.get("locale") or "").strip() or None) if isinstance(recipient, dict) else None
    user_id = canonical_uuid(recipient.get("user_id"), "recipient.user_id") if recipient.get("user_id") else None
    address = (recipient.get("address") or "").strip() or None

    if channel == "in_app":
        if not user_id:
            raise NotificationError(422, _NO_ADDRESS)
        if user_in_organisation(db, organisation_id, user_id) is None:
            raise NotificationError(422, _NO_ADDRESS)
        return Recipient(user_id, None, user_id, locale)

    if user_id:
        user = user_in_organisation(db, organisation_id, user_id)
        if user is None:
            raise NotificationError(422, _NO_ADDRESS)
        if channel != "email":
            raise NotificationError(422, _NO_ADDRESS)  # identity holds no phone number or device yet
        # identity is authoritative: a caller cannot redirect a user's mail to another address
        return Recipient(user_id, user.email, user_id, locale)

    if channel == "email" and address and _EMAIL.match(address) and len(address) <= 254:
        return Recipient(None, address, address.lower(), locale)
    raise NotificationError(422, _NO_ADDRESS)
