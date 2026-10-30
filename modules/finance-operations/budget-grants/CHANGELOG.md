# Changelog — budget-grants

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contracts: budget heads, annual budgets with approval and reappropriation, availability check for procurement,
  commitments and actual spend, grants with investigators, lines and funds received, utilisation certificates,
  and the reports behind the budget-vs-spend and my-grants widgets; events; permissions and roles.
- PRD (`docs/prd.md`).
- Contract 0.2.0: budget heads, budgets, reappropriations, expenditure, grants, certificates and my-grants carry
  `organisation_id` (additive), as the shared cross-tenant leak test needs.
- `docs/user-stories.md`; the PRD records the consumed procurement and hr-payroll events as agreed (#172, #221).
- Backend (#128):
  - budget heads;
  - budgets with approval by someone other than the preparer;
  - reappropriation;
  - availability and open lines for procurement;
  - manual spend and its reversal;
  - grants with revision, funds received and closing;
  - utilisation certificates drafted from the records, certified and marked submitted;
  - `/me/grants` and the budget-vs-spend report;
  - commitments and spend from procurement and hr-payroll events;
  - threshold alerts and certificate reminders.
- Alembic chain `budget_grants_0001`: 11 tables, each with `organisation_id` and the `tenant_isolation` policy on Postgres.
- `config/env.example` lists every key with its default; `module.yaml` status is `in-progress`.
- Fixes from review:
  - certificate due dates are period ends, so a certified period covers its due date;
  - a line that any entry or reappropriation refers to is never deleted;
  - a grant line is never revised below what is used on it, and a revision re-checks the thresholds;
  - a head deactivated later doesn't block revising its existing line;
  - only a draft certificate is decided;
  - whoever edits or submits a budget becomes its preparer and can't approve it;
  - malformed event payloads are ignored with the reason;
  - text fields are never null;
  - manual spend and certificate periods stay inside the budget year or grant period;
  - code races answer 409;
  - the daily job starts on a fresh transaction.
- Tests: 47, including the cross-tenant leak test, the migration test, contract drift checks and regression tests from review.
- Audit trail: `budget_grants_audit_entry` records every state change in the same transaction (actor, action, entity, id),
  until the audit SDK exists, as in hostel and helpdesk.
- A grant with open commitments can't be closed (`open_commitments`), and amounts larger than the column holds are refused.
- Fixes from the second review:
  - a duplicate budget head or grant code that slips past the pre-check (two requests racing) is 409 `code_taken`,
    not 500: the write runs through `_unique`, which catches the database's refusal at flush as well as at commit;
  - a financial year is fully validated: a year and the next (`2026-27`), between 1900 and 9998, so `2026-28` and
    `9999-00` are 422 `invalid_financial_year`;
  - a purchase order delivered after one of its invoices was paid commits only what is not yet paid (nothing when
    paid in full), so an out-of-order delivery never counts the money twice.
- Widgets (#267): `budget-vs-spend` (Finance Staff; Research Office with `scope=grants`) and `my-grants` (Research
  Scholar), with loading, empty and error-with-retry states; 22 tests. Frontend test dependencies came in #266.
- Enabled in `apps/backend/config/modules.enabled.yaml` (mounted at `/api/v1/budget-grants`) and
  `apps/frontend/config/modules.enabled.yaml`; the README documents the widgets.
- Business dates follow Asia/Kolkata (IST), the same policy as procurement (#129): spend recorded from events, the
  default financial year, reminder windows and a certificate's default submission date use the date in India, so
  between 00:00 and 05:30 IST they no longer fall on the previous day. Timestamps stay UTC. Tests on both sides of
  IST midnight.
- Permissions: management gets `budget-grants:availability:read`. Management approves procurement indents, and
  procurement checks `GET /availability` with the approver's token before approving (#129). Additive; story M4.
