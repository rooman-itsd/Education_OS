# Changelog — billing

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Plan limits (contract 0.1.2): `plan_limits`, `user_limit` and `usage_vs_limits` in the application service,
  and `GET /usage` (permission `billing:subscription:read`) reporting usage against the plan's limits: users
  counted by identity (a declared dependency), students and storage `null` until a module counts them.
  apps/backend wires `user_limit` into identity's `hooks.user_limit`, so creating a user past the limit
  answers `409 plan_limit_reached`.
- Second review of PR 363: plan limits are typed (`domain/limits.py`, `PlanLimits`: optional whole numbers
  >= 0 for `users`, `students`, `storage_gb`; absent, null or 0 is no limit, the one rule everywhere).
  `PUT /admin/plans/{id}` answers 422 for "unlimited", "50", -1 or an unknown key; config/plans.yaml is
  validated when seeded. A value stored before this that does not validate reads as no limit, with a
  warning in the log, instead of a 500 on `POST /users` and `GET /usage`. `users` means staff accounts:
  usage counts them with identity's `count_staff_users` (learners left out); `students` stays null until
  counted.
- Scheduled jobs for platform/scheduler (#316): `billing.expire-trials` (daily 00:15 UTC) and
  `billing.trial-reminders` (daily 06:00 UTC), declared on the `eos.scheduler_jobs` entry point and run from
  `scheduler.job.due` (consumer on `eos.event_consumers`); each reports `billing.job.finished`.
  `remind_trials()` raises `billing.trial.expiring` 7, 3 and 1 whole days before a trial ends; the payload adds
  `trial_ends_on` and a `reminder_key` (organisation, end date, days left) so a repeated run is sent once.
- Invoices (contract 0.1.1): `GET /invoices` lists one paid invoice per activated period, written when an
  upgrade is confirmed by the payment adapter or activated at once without one. Table `billing_invoice`
  (migration `billing_0002`, tenant-scoped, RLS). Additive fields `plan`, `period_start`, `period_end`,
  `payment_reference` on `Invoice`.
- Module scaffolded.
