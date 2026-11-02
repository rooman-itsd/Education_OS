# Changelog — billing

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Super admin report (contract 0.2.0, #346): `GET /admin/reports/subscriptions` on `platform:revenue:read`, the
  catalogue key no route used yet: subscriptions per plan and status, monthly recurring revenue, paid invoices of
  the last 30 days (both as decimal strings) and trials ending within 14 days with the organisation's name (from
  the `eos.organisation_directory` entry point). Three Super Admin widgets read it: `billing.trials-expiring`,
  `billing.revenue-by-plan`, `billing.subscriptions-by-plan`. Read-only; nothing about charging changes.
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
