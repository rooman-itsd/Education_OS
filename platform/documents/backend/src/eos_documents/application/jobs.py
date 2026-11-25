"""Scheduled jobs owned by platform/documents (entry point `eos.scheduler_jobs`)."""

from __future__ import annotations

SWEEP_PENDING = "documents.sweep-pending-uploads"

JOBS: dict[str, dict[str, object]] = {
    SWEEP_PENDING: {
        "schedule": "15 * * * *",  # hourly at :15
        "description": "Delete expired unconfirmed pending_upload intents and their staged objects.",
        "scope": "platform",
        "idempotent": True,
    }
}
