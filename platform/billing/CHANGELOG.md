# Changelog — billing

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- A trial reminder missed on its day is sent on the next run (#316 follow-up). Reminders fired only when exactly
  7, 3 or 1 days were left, so a day the scheduler missed lost that reminder. Chain `billing_0003` adds
  `billing_trial_reminder` (one row per organisation, trial end and threshold; unique; RLS); each run raises the
  most urgent due threshold with no row yet, so a missed reminder goes out with the real days left, a superseded
  one is not sent late, and no run raises one twice. `billing.trial.expiring` gains `threshold` (additive);
  `reminder_key` keeps its format. Trial end dates are counted in UTC whatever offset the database returns.
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
