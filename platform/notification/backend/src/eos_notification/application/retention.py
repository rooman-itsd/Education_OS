"""History retention: delete notification history older than NOTIFICATION_HISTORY_RETENTION_DAYS.

A message row holds the recipient's address, the subject, the variables it was rendered from and, for in_app, the
body. DPDP's storage limitation means that is not kept forever; the permanent record of what happened is
platform/audit, which does not hold bodies or addresses.

What is deleted: finished messages (sent, delivered, failed, bounced, suppressed) whose last change
(`updated_at`) is older than the cutoff. There is no separate delivery-attempt table: attempts are counters and
an error class on the message row, so deleting the row removes the whole history and there is no foreign key to
order around.

What is kept: `queued` and `sending` messages, whatever their age. They have not been sent yet or are held by a
worker, and the recovery sweep still has to deliver or fail them; deleting one would silently lose an email. Once
recovery finishes it, it ages out like any other row.

Consequence: a message's idempotency key (client_token, source_event_id) goes with its row. An event redelivered
more than the retention period after it was first handled would send again; the relay's redelivery window is days,
not months, so this is accepted and noted in the README.

Scoping: the organisations holding old rows are listed in platform scope (ids only), then each organisation is
purged in an organisation scope of its own, so row-level security and the explicit filter both apply. Idempotent:
a second run finds nothing older than the cutoff that the first did not remove. Deleted in batches so one run
never holds a huge transaction."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from eos_core.db import SessionLocal, scoped
from eos_core.tenant import organisation_scope, platform_scope
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from ..domain.models import BOUNCED, DELIVERED, FAILED, SENT, SUPPRESSED, Message
from ..infrastructure.config import NotificationConfig
from .common import utc_now

log = logging.getLogger("eos.notification")

FINISHED = (SENT, DELIVERED, FAILED, BOUNCED, SUPPRESSED)
BATCH = 1000


def prune_history(
    *,
    session_factory: sessionmaker | None = None,
    config: NotificationConfig | None = None,
    now: datetime | None = None,
    organisation_id: str | None = None,
) -> dict[str, int]:
    """Delete finished messages older than the retention period, per organisation. `organisation_id` limits the
    purge to one organisation. Returns {"organisations": n scanned, "deleted": n rows, "errors": n failed
    organisations}; one organisation's failure does not stop the others."""
    config = config or NotificationConfig.from_env()
    cutoff = (now or utc_now()) - timedelta(days=config.history_retention_days)
    factory = session_factory or SessionLocal
    stale = (Message.status.in_(FINISHED), Message.updated_at < cutoff)
    with platform_scope(), factory() as lister:  # only the ids are read across tenants
        query = select(Message.organisation_id).where(*stale).distinct()
        if organisation_id is not None:
            query = query.where(Message.organisation_id == organisation_id)
        organisations = sorted(lister.scalars(query).all())
    counts = {"organisations": len(organisations), "deleted": 0, "errors": 0}
    for org in organisations:
        try:
            counts["deleted"] += _prune_organisation(factory, org, stale)
        except Exception as e:  # noqa: BLE001  one organisation must not stop the rest; class only, no values
            log.warning("notification history purge failed for organisation %s: %s", org, type(e).__name__)
            counts["errors"] += 1
    return counts


def _prune_organisation(factory: sessionmaker, org: str, stale: tuple) -> int:
    deleted = 0
    while True:
        with organisation_scope(org), factory() as db:
            ids = db.scalars(scoped(db, select(Message.id).where(*stale).limit(BATCH), Message)).all()
            if not ids:
                return deleted
            result = db.execute(delete(Message).where(Message.organisation_id == org, Message.id.in_(ids)))
            db.commit()
            deleted += result.rowcount or 0
