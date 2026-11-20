"""Notification's scheduled job, declared for platform/scheduler (entry point `eos.scheduler_jobs`).

`notification.recover-stuck` runs `messages.recover_stuck()`: it re-sends queued messages whose retry is due
(a retryable provider failure, e.g. an SMTP 4xx or a dropped connection) and re-drives sending rows whose lease
expired. Without it a temporarily failed email stays queued forever, because the consumer that sent it returned
normally and the relay marked its event done. A platform job: one sweep covers every organisation. Idempotent:
each message's retry is guarded on the status and attempts the sweep saw, and attempts are bounded by
NOTIFICATION_MAX_ATTEMPTS / NOTIFICATION_RECOVERY_MAX_FAILURES with a doubling delay.

`notification.prune-history` runs `retention.prune_history()` (DPDP storage limitation): it deletes finished messages
(sent, delivered, failed, bounced, suppressed) older than NOTIFICATION_HISTORY_RETENTION_DAYS (default 90, minimum 1),
organisation by organisation, and keeps queued and sending ones. Platform job, idempotent: a second run finds
nothing older than the cutoff that the first did not already remove."""

RECOVER_STUCK = "notification.recover-stuck"
PRUNE_HISTORY = "notification.prune-history"

JOBS = {
    RECOVER_STUCK: {
        "scope": "platform",
        "default_cron": "*/5 * * * *",
        "idempotent": True,
        "description": "Retry queued emails whose retry is due and re-drive sends whose lease expired.",
    },
    PRUNE_HISTORY: {
        "scope": "platform",
        "default_cron": "45 2 * * *",
        "idempotent": True,
        "description": "Delete finished notification history (addresses, subjects, bodies) past the retention period.",
    },
}
