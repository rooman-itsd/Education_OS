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
- Tests: 62, including the cross-tenant leak test, the migration test and contract drift checks.
- `config/env.example` lists every key with its default; `module.yaml` status is `in-progress`.
