"""The coach's device alerts (GET /alerts, backing the dashboard widget wearables.alerts): which athletes' links expired or
were revoked, whose sync keeps failing, or who sent no data for WEARABLES_STALE_AFTER_DAYS. Statuses and dates only, never a
reading, so it is safe for any coach. Nothing from Strava is shown beyond "linked": no recency of its data, no sync time."""

from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime, timedelta

from eos_core.db import scoped
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..infrastructure.config import Config
from ..infrastructure.models import LinkState, aware, iso

KINDS = ("link_expired", "link_revoked", "sync_failing", "no_recent_data", "not_linked")
SCAN_LIMIT = 20000  # links of one organisation read per request; no academy has more athletes than this


class InvalidCursorError(ValueError):
    pass


def _cursor(a: dict) -> str:
    return base64.urlsafe_b64encode(
        f"{a['since']}|{a['person_id']}|{a['kind']}|{a.get('provider') or ''}".encode()
    ).decode()


def decode_cursor(cursor: str) -> tuple[str, str, str, str]:
    try:
        if len(cursor) > 300:
            raise ValueError
        since, person, kind, provider = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 3)
        datetime.fromisoformat(since)
        if kind not in KINDS or len(person) != 36:
            raise ValueError
        return since, person, kind, provider
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise InvalidCursorError from None


def compute(db: Session, cfg: Config, now: datetime, person_ids: list[str] | None, kind: str | None) -> list[dict]:
    q = select(LinkState).where(LinkState.status != "pending")
    if person_ids is not None:
        q = q.where(LinkState.person_id.in_(person_ids))
    links = db.scalars(scoped(db, q, LinkState).limit(SCAN_LIMIT)).all()
    stale = timedelta(days=cfg.stale_after_days)
    alerts: list[dict] = []
    for lk in links:
        strava = lk.provider == "strava"
        synced = None if strava else iso(lk.last_synced_at)

        def add(k: str, since: datetime, lk=lk, synced=synced) -> None:
            alerts.append(
                {
                    "person_id": lk.person_id,
                    "provider": lk.provider,
                    "kind": k,
                    "since": iso(aware(since)),
                    "last_synced_at": synced,
                }
            )

        if lk.status == "expired":
            add("link_expired", lk.status_since)
        elif lk.status == "revoked":
            add("link_revoked", lk.status_since)
        elif lk.status in ("active", "error"):
            if lk.consecutive_failures >= cfg.sync_failure_threshold and lk.failing_since:
                add("sync_failing", lk.failing_since)
            elif not strava:  # how fresh Strava's data is would be Strava data
                last = aware(lk.last_data_at) or aware(lk.status_since) or aware(lk.created_at)
                if last is not None and now - last > stale:
                    add("no_recent_data", last + stale)
    if person_ids is not None:
        linked = {lk.person_id for lk in links}
        alerts += [
            {
                "person_id": p,
                "provider": None,
                "kind": "not_linked",
                "since": iso(now.astimezone(UTC)),
                "last_synced_at": None,
            }
            for p in person_ids
            if p not in linked
        ]
    if kind:
        alerts = [a for a in alerts if a["kind"] == kind]
    # Oldest problems first (they have waited longest); a stable order for the cursor.
    return sorted(alerts, key=lambda a: (a["since"], a["person_id"], a["kind"], a["provider"] or ""))


def page(alerts: list[dict], cursor: str | None, limit: int) -> tuple[list[dict], str | None]:
    if cursor:
        since, person, kind, provider = decode_cursor(cursor)
        alerts = [
            a
            for a in alerts
            if (a["since"], a["person_id"], a["kind"], a["provider"] or "") > (since, person, kind, provider)
        ]
    items = alerts[:limit]
    return items, (_cursor(items[-1]) if len(alerts) > limit else None)
