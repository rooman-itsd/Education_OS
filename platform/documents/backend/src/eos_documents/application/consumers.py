"""Event consumers for documents platform service."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from eos_core import events
from sqlalchemy.orm import Session

from ..infrastructure.config import load_settings
from ..infrastructure.storage import get_storage
from . import service
from .jobs import SWEEP_PENDING

log = logging.getLogger("eos.documents")


def valid_uuid(val: object) -> bool:
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def on_purged(db: Session, event) -> None:
    """tenancy.organisation.purged: delete the organisation's object storage prefix."""
    organisation_id = (event.payload or {}).get("organisation_id")
    if not valid_uuid(organisation_id):
        log.warning("documents: tenancy.organisation.purged without a usable organisation_id")
        return
    org_id = str(organisation_id)
    cfg = load_settings()
    storage = get_storage(cfg)
    deleted = storage.delete_prefix(cfg.minio_bucket, f"{org_id}/")
    events.publish(
        db,
        "documents.organisation.purged",
        None,
        {
            "organisation_id": org_id,
            "objects_deleted": deleted,
            "purged_at": datetime.now(UTC).isoformat(),
        },
    )


def on_job_due(db: Session, event) -> None:
    """scheduler.job.due for documents.sweep-pending-uploads: sweep stale unconfirmed uploads."""
    payload = event.payload or {}
    if payload.get("job") != SWEEP_PENDING:
        return
    cfg = load_settings()
    storage = get_storage(cfg)
    try:
        counts = service.sweep_pending_uploads(storage=storage)
        outcome = "failed" if counts["errors"] else "succeeded"
        detail = ", ".join(f"{k} {v}" for k, v in counts.items())
    except Exception as exc:  # noqa: BLE001
        log.exception("%s failed", SWEEP_PENDING)
        outcome, detail = "failed", type(exc).__name__
    events.publish(
        db,
        "documents.job.finished",
        event.organisation_id,
        {"run_id": payload.get("run_id"), "outcome": outcome, "detail": detail},
    )


CONSUMERS = {
    "tenancy.organisation.purged": on_purged,
    "scheduler.job.due": on_job_due,
}
