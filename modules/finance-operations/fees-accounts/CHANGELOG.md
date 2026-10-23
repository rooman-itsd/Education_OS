# Changelog — fees-accounts

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contracts: fee heads, fee structures with instalments and late fees, invoices (single and bulk), online
  payment through payment-sbiepay, offline payments, refunds, voids, receipts, concessions, ledger statement,
  self-service dues, collection targets and the reports behind the Finance Staff, Applicant, Student and
  Management widgets; events; permissions and roles.
- PRD (`docs/prd.md`).
- Contract 0.2.0 (agreed on #175 and #183):
  - `GET /dues` for other modules, with the new permission `fees-accounts:dues:read` (examination-staff, finance-staff);
  - `GET/PUT /settings` (`invoice_library_fines`, `invoice_staff_transport`);
  - fee structures gain `room_type` and `route_id`;
  - fee heads, structures, invoices, payments, receipts and concessions carry `organisation_id`;
  - module.yaml consumes the hostel, transport and library events.
- `docs/user-stories.md`.
- Backend (#107):
  - domain rules;
  - fee heads and structures;
  - invoices: single, bulk, and raised from hostel, transport, library and admissions events;
  - counter and online payments through payment-sbiepay, with receipts, voids and refunds;
  - concessions with a second approver;
  - statements, `/me/*` and `/dues`;
  - settings and collection targets;
  - the collections, outstanding and collection-vs-target reports;
  - the daily late-fee and overdue job.
- Alembic chain `fees_accounts_0001`: 12 tables, each with `organisation_id` and the `tenant_isolation` policy on Postgres.
- Tests: 72, including the cross-tenant leak test, the migration test, contract drift checks and regression tests from review.
- `config/env.example` lists every key with its default; `module.yaml` status is `in-progress`.
- Contract 0.2.1 (additive): `Invoice.credit`, what was paid above the amount due and should be refunded.
- Fixes from the review of #244:
  - refunds started at the payment adapter (`payment-sbiepay.payment.refunded` without a refund of ours) are recorded
    against the payment and completed, so the ledger follows the money;
  - a concession request above the invoice total is refused (`exceeds_total`), and an approved concession is capped at
    what is invoiced less earlier concessions;
  - `payment-sbiepay.payment.succeeded` in a currency other than INR is ignored; an overpayment shows as `credit`;
  - proportional allocation uses largest remainder, so no fee head share is ever negative;
  - malformed event payloads are ignored with the reason instead of raising out of `consumers.handle`;
  - the collections and collection-vs-target reports are net of refunds completed in the period;
  - ad hoc invoices refuse inactive fee heads.
