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
- Paid only against a payment (security review N7, N8):
  - `POST /webhooks/payment` takes no token, so it is trusted only when signed: `X-Payment-Signature` is the hex
    HMAC-SHA256 of the raw body with `BILLING_PAYMENT_WEBHOOK_SECRET` (payment-sbiepay signs its
    PaymentNotification this way with the same value, `PAYMENT_SBIEPAY_NOTIFY_SECRET`). Only a succeeded payment
    for `billing` whose amount is the pending plan's total activates the upgrade; a redelivery changes nothing.
    No secret: 503. No adapter: 404.
  - With no adapter (`BILLING_PAYMENT_ADAPTER=none`) a paid plan is not self-service outside dev mode: the upgrade
    answers `409 payment_not_configured` and nothing is invoiced. A super admin activates the plan once payment
    has arrived offline (`PUT /admin/subscriptions/{organisation_id}`), which issues no invoice: a numbered GST
    invoice is written only for a payment the API confirmed. A free plan activates at once. In dev mode (local
    development and the test suites) a paid plan still activates without payment, as before.
- Invoices as PDFs in `platform/documents`.
- Super admin: edit plans, set any organisation's plan, extend trials, comp, revenue reports.

Not in scope: deciding what an organisation may use (`platform/tenancy` computes the entitlement from the plan).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Super admin report and dashboard widgets
`GET /admin/reports/subscriptions` (`platform:revenue:read`, super admin only; `application/reports.py`) reads every
organisation in platform scope and answers, per plan, the subscriptions in each status (a status outside the five
counts as `other`), the **monthly recurring revenue** (active subscriptions that pay × the plan's monthly price; one
comped through `admin_set`, `comped_until` in the future, counts in `active` and in `comped`, not in the revenue) and
what was **paid in the last 30 days** (paid invoices issued in that window, filtered in the database), plus the
**trials ending within 14 days**, soonest first, including any already past their end that the daily expiry job has
not made read-only yet (negative `days_left`, shown as "trial ended"). Money is computed
with `Decimal` and returned as two-decimal strings. Organisation names come from the `eos.organisation_directory`
entry point that tenancy publishes (`application/organisations.py`), so billing never imports tenancy; without it
a trial is listed without a name.

| Widget | Dashboard | Permission |
|---|---|---|
| `billing.plan-and-trial`, `billing.usage-vs-limits`, `billing.invoices` | Organisation Admin | `billing:subscription:read` |
| `billing.trials-expiring`, `billing.revenue-by-plan`, `billing.subscriptions-by-plan` | Super Admin | `platform:revenue:read` |

## GST invoices
An invoice is written when a paid plan is activated, as a snapshot (`application/service.py::_tax_fields`; the rules
are pure functions in `domain/gst.py`). The supplier is the platform: `BILLING_SUPPLIER_GSTIN`, `_NAME`, `_ADDRESS`
in `config/env.example`. The recipient is the organisation's billing profile (`GET/PUT /billing-profile`); its GSTIN
is optional. Tax is CGST + SGST when the place of supply equals the supplier's state, IGST otherwise; the taxable
value is the plan price times the months in the cycle (prices are exclusive of GST). Numbers are
`EOS/26-27/000001`: per financial year (1 April to 31 March, Indian time), gapless, within the 16 characters GST
allows. Invoices from before this are not tax invoices and keep empty GST fields.

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../docs/architecture/module-standard.md#portability-checklist).
