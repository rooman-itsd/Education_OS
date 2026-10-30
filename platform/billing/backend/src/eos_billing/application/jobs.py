"""Billing's scheduled jobs, declared for platform/scheduler (entry point `eos.scheduler_jobs`). Both are platform
jobs: one run per deployment covers every organisation's subscription. Both are idempotent: expiring a trial
only acts on trials past their end, and a repeated reminder carries the same reminder_key."""

JOBS = {
    "billing.expire-trials": {
        "scope": "platform",
        "default_cron": "15 0 * * *",
        "idempotent": True,
        "description": "Trials past their end go read-only or suspended per the plan policy.",
    },
    "billing.trial-reminders": {
        "scope": "platform",
        "default_cron": "0 6 * * *",
        "idempotent": True,
        "description": "billing.trial.expiring 7, 3 and 1 days before a trial ends; notification emails the admin.",
    },
}
