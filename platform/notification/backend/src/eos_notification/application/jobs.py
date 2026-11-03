"""Notification's scheduled job, declared for platform/scheduler (entry point `eos.scheduler_jobs`).

`notification.recover-stuck` runs `messages.recover_stuck()`: it re-sends queued messages whose retry is due
(a retryable provider failure, e.g. an SMTP 4xx or a dropped connection) and re-drives sending rows whose lease
expired. Without it a temporarily failed email stays queued forever, because the consumer that sent it returned
normally and the relay marked its event done. A platform job: one sweep covers every organisation. Idempotent:
each message's retry is guarded on the status and attempts the sweep saw, and attempts are bounded by
NOTIFICATION_MAX_ATTEMPTS / NOTIFICATION_RECOVERY_MAX_FAILURES with a doubling delay."""

RECOVER_STUCK = "notification.recover-stuck"

JOBS = {
    RECOVER_STUCK: {
        "scope": "platform",
        "default_cron": "*/5 * * * *",
        "idempotent": True,
        "description": "Retry queued emails whose retry is due and re-drive sends whose lease expired.",
    },
}
