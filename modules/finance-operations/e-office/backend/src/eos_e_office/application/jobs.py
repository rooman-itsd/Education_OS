"""e-office's scheduled job, declared for platform/scheduler (entry point `eos.scheduler_jobs` in pyproject.toml).
A platform job: one run per deployment covers every organisation's open files. Idempotent, as the scheduler requires
(delivery is at-least-once): a holding already flagged is never flagged again. The default schedule is 18:45 UTC,
00:15 in Asia/Kolkata, just after the Indian date changes."""

JOBS = {
    "e-office.flag-overdue": {
        "scope": "platform",
        "default_cron": "45 18 * * *",
        "idempotent": True,
        "description": "Open files held past their due date are flagged once; e-office.file.overdue reminds the holder.",
    },
}
