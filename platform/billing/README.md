# billing

**Kind:** platform (core)
**Status:** planned

Plans, trials, subscriptions, upgrades and invoices. Decision: [ADR-0005](../../docs/architecture/adr/0005-multi-tenant-saas.md).

## Scope
- Plans as data ([config/plans.yaml](config/plans.yaml) seeds them; the super admin edits them in the admin screens of `apps/frontend`).
  A plan is a set of suites, modules, specialized-suite count, integrations and limits.
- Plan limits (`domain/limits.py`, `PlanLimits`), each a whole number >= 0, absent or 0 meaning no limit:
  - `users`: active **staff** accounts. Learners are not users: a person whose roles include `student` or
    `applicant`, or a role whose dashboard layout extends `student` (e.g. `law-student`, `musician`; see
    `platform/identity/config/dashboards/`), is never counted against `users` and never refused on it.
    Identity counts staff (`count_staff_users`) and refuses the staff account past the limit
    (`409 plan_limit_reached`), through a hook apps/backend wires to `user_limit`.
  - `students`: the learners. Nothing counts them yet: `GET /usage` reports `null` and nothing is refused.
  - `storage_gb`: stored files, likewise not counted yet.
  `PUT /admin/plans/{id}` refuses anything else with 422; a malformed value stored earlier reads as no
  limit and is logged.
- Every organisation has one subscription: trialing, active, past_due, cancelled or read_only.
- Trial: starts at registration, reminders at 7, 3 and 1 days, then read-only or suspended.
- Upgrade: self-service through the payment adapter; the entitlement widens the moment the
  payment webhook confirms. Downgrades apply at period end.
- Invoices as PDFs in `platform/documents`.
- Super admin: edit plans, set any organisation's plan, extend trials, comp, revenue reports.

Not in scope: deciding what an organisation may use (`platform/tenancy` computes the entitlement from the plan).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../docs/architecture/module-standard.md#portability-checklist).
