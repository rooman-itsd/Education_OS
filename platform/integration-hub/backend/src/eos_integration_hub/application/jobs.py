"""integration-hub's scheduled jobs, declared for platform/scheduler (entry point `eos.scheduler_jobs`). All are platform
jobs: one run covers every organisation, each row in its own organisation's scope. All are idempotent: each acts only
on rows that are due, and a delivery's attempt is claimed before it runs.

The sweep is how async port operations and acknowledged callbacks are worked off. platform/scheduler runs on arq, so
this is the hub's arq job; a dedicated per-delivery queue can replace the one-minute sweep without a contract change."""

SWEEP = "integration-hub.process-deliveries"
HEALTH = "integration-hub.health-checks"
REFRESH = "integration-hub.refresh-tokens"
PURGE = "integration-hub.purge"

JOBS = {
    SWEEP: {
        "scope": "platform",
        "default_cron": "* * * * *",
        "idempotent": True,
        "description": "Run due async port operations and retries, process acknowledged provider callbacks.",
    },
    HEALTH: {
        "scope": "platform",
        "default_cron": "*/15 * * * *",
        "idempotent": True,
        "description": "Healthcheck every enabled connection due by INTEGRATION_HUB_HEALTH_INTERVAL_MIN.",
    },
    REFRESH: {
        "scope": "platform",
        "default_cron": "*/5 * * * *",
        "idempotent": True,
        "description": "Refresh OAuth tokens expiring within INTEGRATION_HUB_TOKEN_REFRESH_LEAD_S.",
    },
    PURGE: {
        "scope": "platform",
        "default_cron": "40 2 * * *",
        "idempotent": True,
        "description": "Delete encrypted inputs and raw callbacks past retention, old log rows and spent OAuth states.",
    },
}
