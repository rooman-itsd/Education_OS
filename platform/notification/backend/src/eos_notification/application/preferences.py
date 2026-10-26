"""Per-user channel preferences. Quiet hours are validated and stored but NOT enforced in this release: deferring a
message needs the scheduler (#82), so a non-transactional message sent inside quiet hours is still sent."""

from __future__ import annotations

import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from eos_core import events
from eos_core.db import scoped
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.errors import NotificationError
from ..domain.models import CATEGORIES, CHANNELS, Preference
from ..infrastructure.config import NotificationConfig
from ..infrastructure.templates import LOCALE_RE
from .common import canonical_uuid, organisation_of
from .recipients import user_in_organisation

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_OPT_IN_BY_DEFAULT = ("email", "in_app")


def default_channels(config: NotificationConfig) -> dict[str, list[str]]:
    enabled = list(config.channels_enabled)
    return {
        cat: list(enabled) if cat == "transactional" else [c for c in _OPT_IN_BY_DEFAULT if c in enabled]
        for cat in CATEGORIES
    }


def effective_channels(row: Preference | None, config: NotificationConfig) -> dict[str, list[str]]:
    channels = default_channels(config)
    if row is not None:
        for cat, lst in (row.channels or {}).items():
            if cat in CATEGORIES and cat != "transactional":
                channels[cat] = [c for c in lst if c in CHANNELS]
    return channels  # transactional is always the full enabled set


def get_row(db: Session, organisation_id: str, user_id: str) -> Preference | None:
    return db.scalars(
        scoped(db, select(Preference), Preference).where(
            Preference.organisation_id == organisation_id, Preference.user_id == user_id
        )
    ).first()


def _view(user_id: str, row: Preference | None, config: NotificationConfig) -> dict:
    return {
        "user_id": user_id,
        "locale": row.locale if row else None,
        "channels": effective_channels(row, config),
        "quiet_hours": row.quiet_hours if row else None,
    }


def _quiet_hours(value: dict | None) -> dict | None:
    if value is None:
        return None
    try:
        start, end, tz = value["start"], value["end"], value["timezone"]
        ZoneInfo(tz)
    except (KeyError, TypeError, ZoneInfoNotFoundError, ValueError):
        raise NotificationError(422, "quiet_hours needs start, end (HH:MM) and a valid timezone") from None
    if not (isinstance(start, str) and isinstance(end, str) and _HHMM.match(start) and _HHMM.match(end)):
        raise NotificationError(422, "quiet_hours start and end must be HH:MM")
    return {"start": start, "end": end, "timezone": tz}


def _require_user(db: Session, organisation_id: str, user_id: str) -> str:
    uid = canonical_uuid(user_id, "user_id")
    if user_in_organisation(db, organisation_id, uid) is None:
        raise NotificationError(404, "no such user in this organisation")
    return uid


def get_preferences(db: Session, user_id: str, config: NotificationConfig | None = None) -> dict:
    config = config or NotificationConfig.from_env()
    org = organisation_of(db)
    uid = _require_user(db, org, user_id)
    return _view(uid, get_row(db, org, uid), config)


def set_preferences(
    db: Session,
    user_id: str,
    *,
    channels: dict,
    locale: str | None = None,
    quiet_hours: dict | None = None,
    actor: str | None = None,
    config: NotificationConfig | None = None,
) -> dict:
    """Replace a user's preferences. A request to switch a transactional category off is accepted for the other
    categories and the transactional one stays on (the contract says so)."""
    config = config or NotificationConfig.from_env()
    org = organisation_of(db)
    uid = _require_user(db, org, user_id)
    if not isinstance(channels, dict):
        raise NotificationError(422, "channels must be an object")
    if locale is not None and not LOCALE_RE.match(locale):
        raise NotificationError(422, "locale is not valid")
    for cat, lst in channels.items():
        if cat not in CATEGORIES:
            raise NotificationError(422, "unknown category")
        if not isinstance(lst, list) or any(c not in CHANNELS for c in lst):
            raise NotificationError(422, "unknown channel")
    quiet = _quiet_hours(quiet_hours)

    row = get_row(db, org, uid)
    before = effective_channels(row, config)
    stored = {cat: [c for c in dict.fromkeys(lst)] for cat, lst in channels.items() if cat != "transactional"}
    if row is None:
        row = Preference(organisation_id=org, user_id=uid, locale=locale, channels=stored, quiet_hours=quiet)
        db.add(row)
    else:
        row.locale, row.channels, row.quiet_hours = locale, stored, quiet
    after = effective_channels(row, config)
    if after != before:
        events.publish(
            db,
            "notification.preferences.changed",
            org,
            {
                "user_id": uid,
                "categories_disabled": [c for c in CATEGORIES if c != "transactional" and not after[c]],
                "channels_disabled": [
                    ch
                    for ch in config.channels_enabled
                    if not any(ch in lst for cat, lst in after.items() if cat != "transactional")
                ],
            },
            actor=actor,
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise NotificationError(409, "preferences were changed at the same time; try again") from None
    return _view(uid, row, config)
