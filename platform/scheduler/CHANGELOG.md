# Changelog — scheduler

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- The scheduler (#316, was #82). A module declares its jobs on the `eos.scheduler_jobs` entry point, consumes
  `scheduler.job.due` and reports with `<module>.job.finished` (run_id, outcome, detail); scheduler consumes that
  from every module with a job and closes the run only if that module owns it. A run nobody closes within
  `SCHEDULER_RUN_TIMEOUT_S` fails. Every outcome is an event (`scheduler.run.succeeded|failed|skipped`).
- Cron evaluated in each schedule's explicit timezone by a small standard-library evaluator (no cron library is
  on the approved stack): `*`, numbers, ranges, lists, steps; the classic day-of-month OR day-of-week rule; a time
  skipped by a spring-forward change fires at the first real minute after it, a repeated one fires once.
- The tick: due schedules claimed FOR UPDATE SKIP LOCKED on Postgres; missed windows run once with the count
  recorded (`catch_up: once`) or are skipped (`never`), never beyond `SCHEDULER_CATCH_UP_HORIZON_S`; overlap is
  refused and announced; a job no installed module declares as idempotent fails visibly instead of firing.
- A platform job that ships `default_cron` gets a UTC schedule the first time it is seen, so
  `billing.expire-trials` runs once billing declares it.
- Runners: `python -m eos_scheduler` (a plain loop, no Redis) and `arq eos_scheduler.worker.WorkerSettings`.
- Operator API from `contracts/openapi.yaml`: jobs, schedules (create, get, retime/enable, delete), run now
  (409 while a run is going), run history. Organisation callers work on their own organisation-scoped
  schedules; the super admin on platform jobs and every organisation's.
- `contracts/permissions.yaml`: blocks named with platform role ids (`org-admin`, `super-admin`); the
  `scheduler-admin` and `scheduler-viewer` blocks, which no profile assigns, are removed.
- Alembic chain `scheduler_0001`: `scheduler_schedule` and `scheduler_run` with `organisation_id` and RLS.
- Enabled in the host (`apps/backend/config/modules.enabled.yaml`).
- `contracts/openapi.yaml`: job definitions (read-only), schedules (cron or one-off), run now,
  and run history. A job is declared in code by the module that handles it; only its timing is
  editable, so a schedule cannot point at a job nothing handles.
- `contracts/events.yaml`: `scheduler.job.due` is the firing mechanism, not a notice — the
  owning module consumes it and does the work, because scheduler may not import module code.
  Plus `scheduler.run.succeeded|failed|skipped`; a skipped window is published rather than
  passed over in silence.
- `contracts/permissions.yaml`: job/schedule/run keys, with `scheduler:run:trigger` kept
  separate from `schedule:write`, and super-admin `platform:scheduler:admin` for
  platform-scoped jobs.
- Platform-scoped and organisation-scoped jobs are distinguished explicitly; conflating them
  would be a tenancy bug.
- Overlap is refused by default, cron requires an explicit timezone, and missed windows are
  caught up once rather than skipped.
- `docs/prd.md`: the clock/work boundary against workflow, notification and event-bus, and the
  first real job — `billing.expire_trials()`, which is documented as "run by the scheduler
  daily" and which nothing currently runs.
- Module scaffolded.
