# Changelog — billing

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Plan limits (contract 0.4.0, additive): `plan_limits`, `user_limit` and `usage_vs_limits` in the application service,
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
- GST tax invoices (contract 0.3.0, additive; #155, batch #337). Each invoice written when a paid plan is activated
  now carries: a number `PREFIX/YY-YY/NNNNNN` (at most 16 characters, one series per financial year, 1 April to
  31 March read in Indian time, no gaps: the counter row is locked and written in the invoice's own transaction, so
  a failed activation gives the number back); the supplier's and the recipient's name, GSTIN, address and state;
  the SAC code (`BILLING_SAC_CODE`, default 998315); the place of supply (the recipient's state, or the supplier's
  when none is on record); and the tax as decimal strings: CGST + SGST (half the rate each) when the place of supply
  is the supplier's state, IGST otherwise, at `BILLING_GST_RATE` (default 18), rounded half up to the paisa per head.
  GSTINs are checked for format, state code and check character. `amount` is unchanged and now means the taxable
  value, so revenue reports exclude GST. New: `GET/PUT /billing-profile` (the recipient: legal name, optional GSTIN,
  address, state; B2C when there is no GSTIN) and migration `billing_0004` (invoice columns, `billing_profile` with
  RLS, `billing_invoice_counter`, platform-wide like plans). Invoices issued earlier keep null in the new fields and
  are not renumbered. With no `BILLING_SUPPLIER_GSTIN` set (development, pilots) an invoice is numbered but carries
  no tax (`tax_scheme: none`); a set but invalid supplier GSTIN, rate, SAC or prefix refuses the upgrade with 503
  rather than issue a non-compliant invoice. Not covered: UTGST for union territories without a legislature (shown
  as SGST), reverse charge, credit notes and the PDF in platform/documents (`document_id` stays null).
- Super admin report (contract 0.2.0, #346): `GET /admin/reports/subscriptions` on `platform:revenue:read`, the
  catalogue key no route used yet: subscriptions per plan and status, monthly recurring revenue, paid invoices of
  the last 30 days (both as decimal strings) and trials ending within 14 days with the organisation's name (from
  the `eos.organisation_directory` entry point). Three Super Admin widgets read it: `billing.trials-expiring`,
  `billing.revenue-by-plan`, `billing.subscriptions-by-plan`. Read-only; nothing about charging changes. Comped
  subscriptions count as `comped`, not as recurring revenue; an unknown status counts as `other`; trials past their
  end but not yet expired by the daily job are listed (negative `days_left`). A paid invoice on a deleted plan still counts
  (its own row); trial dates are read in UTC whatever the connection's zone; the three widgets share one request.
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
