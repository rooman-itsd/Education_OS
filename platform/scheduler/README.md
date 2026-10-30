# scheduler

**Domain:** platform
**Kind:** platform
**Status:** in progress — schedules, the tick, run history, operator API

Jobs, cron, reminders and alert dispatch.

## Scope
Work on a clock: nightly jobs, reminders, expiries. Scheduler owns *when*; the module that declared a job owns
*what*. It never imports that module: a due job is handed over as `scheduler.job.due` through event-bus, and
the module reports back with `<module>.job.finished`. It is not a queue for work offloaded from a request
(`arq` inside the module), and it does not send reminders itself (`platform/notification`). Design and open
questions: [docs/prd.md](docs/prd.md).

## Declaring a job

```toml
# <your module>/backend/pyproject.toml
[project.entry-points."eos.scheduler_jobs"]
billing = "eos_billing.application.jobs:JOBS"

[project.entry-points."eos.event_consumers"]
billing = "eos_billing.application.consumers:CONSUMERS"
```

```python
# eos_billing/application/jobs.py
JOBS = {
    "billing.expire-trials": {
        "scope": "platform",  # once per deployment; "organisation" runs per academy
        "default_cron": "15 0 * * *",  # a platform job with a default gets a UTC schedule automatically
        "idempotent": True,  # required: delivery is at-least-once
        "description": "Trials past their end go read-only or suspended.",
    },
}


# eos_billing/application/consumers.py
def on_job_due(db, event):
    if event.payload["job"] != "billing.expire-trials":
        return
    expired = expire_trials(db)
    publish(
        db,
        "billing.job.finished",
        event.organisation_id,
        {"run_id": event.payload["run_id"], "outcome": "succeeded", "detail": f"{expired} trials expired"},
    )


CONSUMERS = {"scheduler.job.due": on_job_due}
```

A handler that raises is retried by the relay; one that never reports is failed after
`SCHEDULER_RUN_TIMEOUT_S`. Only the module that owns a job can close its run.

## What this release provides

| Piece | State |
|---|---|
| Cron in an explicit timezone (`*`, numbers, ranges, lists, steps; day-of-month OR day-of-week; daylight-saving gaps and repeats) | built, 17 tests |
| The tick: fire due schedules (FOR UPDATE SKIP LOCKED on Postgres), catch-up once or never within a horizon, overlap refused and announced, unknown or non-idempotent jobs failed visibly | built, tested |
| Runs: started by the tick or "run now", closed by the owner's report or the timeout; `scheduler.run.succeeded|failed|skipped`; history pruned after `SCHEDULER_RUN_RETENTION_DAYS` | built, tested |
| Default UTC schedules for platform jobs that ship a `default_cron` | built, tested |
| Operator API: jobs, schedules, run now, runs; cross-tenant leak test | built, tested |
| `python -m eos_scheduler` (no Redis) and `arq eos_scheduler.worker.WorkerSettings` | the loop runs in tests; the arq worker is wired but has not run against Redis |
| The whole path through the host: tick → relay → owning module → report → relay → run closed | `apps/backend/tests/test_scheduled_job_chain.py`, also on PostgreSQL as `eos_app` |

## What this release does NOT do

1. **No module declares a job yet.** `billing.expire-trials` and the trial reminders need billing's declaration
   and handler (billing's code). Until then the scheduler has nothing to fire.
2. **Nothing runs the loop in a deployment yet.** `python -m eos_scheduler`, or the arq worker once Redis is in
   the stack, needs a service in `infra/`; so does the event-bus relay that carries the jobs.
3. **No audit record** of creating, changing or running a schedule: `platform/audit` is not built yet, so these
   are recorded on the `eos.scheduler.audit` log.
4. **`scheduler.run.skipped` is raised for overlap only.** Missed windows beyond the catch-up horizon, or with
   `catch_up: never`, are logged, not announced.
5. **No Super Admin widget** yet.

## Configuration

Every key is in [config/env.example](config/env.example), prefixed `SCHEDULER_`, each bounded.

## Tests

```
pytest platform/scheduler/backend/tests -q
```

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../docs/architecture/module-standard.md#portability-checklist).
