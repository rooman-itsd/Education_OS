# billing

**Kind:** platform (core)
**Status:** planned

Plans, trials, subscriptions, upgrades and invoices. Decision: [ADR-0005](../../docs/architecture/adr/0005-multi-tenant-saas.md).

## Scope
- Plans as data ([config/plans.yaml](config/plans.yaml) seeds them; the super admin edits them in the admin screens of `apps/frontend`).
  A plan is a set of suites, modules, specialized-suite count, integrations and limits.
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

## Super admin report and dashboard widgets
`GET /admin/reports/subscriptions` (`platform:revenue:read`, super admin only; `application/reports.py`) reads every
organisation in platform scope and answers, per plan, the subscriptions in each status, the **monthly recurring
revenue** (active subscriptions × the plan's monthly price) and what was **paid in the last 30 days** (paid
invoices issued in that window), plus the **trials ending in the next 14 days**, soonest first. Money is computed
with `Decimal` and returned as two-decimal strings. Organisation names come from the `eos.organisation_directory`
entry point that tenancy publishes (`application/organisations.py`), so billing never imports tenancy; without it
a trial is listed without a name.

| Widget | Dashboard | Permission |
|---|---|---|
| `billing.plan-and-trial`, `billing.usage-vs-limits`, `billing.invoices` | Organisation Admin | `billing:subscription:read` |
| `billing.trials-expiring`, `billing.revenue-by-plan`, `billing.subscriptions-by-plan` | Super Admin | `platform:revenue:read` |

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../docs/architecture/module-standard.md#portability-checklist).
