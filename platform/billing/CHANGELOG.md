# Changelog — billing

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Plan limits (contract 0.1.2): `plan_limits`, `user_limit` and `usage_vs_limits` in the application service,
  and `GET /usage` (permission `billing:subscription:read`) reporting usage against the plan's limits: users
  counted by identity (a declared dependency), students and storage `null` until a module counts them.
  apps/backend wires `user_limit` into identity's `hooks.user_limit`, so creating a user past the limit
  answers `409 plan_limit_reached`.
- Invoices (contract 0.1.1): `GET /invoices` lists one paid invoice per activated period, written when an
  upgrade is confirmed by the payment adapter or activated at once without one. Table `billing_invoice`
  (migration `billing_0002`, tenant-scoped, RLS). Additive fields `plan`, `period_start`, `period_end`,
  `payment_reference` on `Invoice`.
- Module scaffolded.
