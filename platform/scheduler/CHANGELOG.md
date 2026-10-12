# Changelog — scheduler

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
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
