"""Audit's scheduled job, declared for platform/scheduler (entry point `eos.scheduler_jobs`).

`audit.prune` runs `service.prune()`: it deletes the window of records older than AUDIT_RETENTION_DAYS (a floor
of seven years by default; off unless AUDIT_RETENTION_ENABLED). A platform job, idempotent: a second run the same
day finds nothing older than the cutoff that the first did not already remove."""

PRUNE = "audit.prune"

JOBS = {
    PRUNE: {
        "scope": "platform",
        "default_cron": "30 2 * * *",
        "idempotent": True,
        "description": "Delete audit records older than the retention period (when retention is enabled).",
    },
}
