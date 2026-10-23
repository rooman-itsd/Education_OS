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
- Alembic chain `budget_grants_0001`: 10 tables, each with `organisation_id` and the `tenant_isolation` policy on Postgres.
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
- Tests: 44, including the cross-tenant leak test, the migration test, contract drift checks and regression tests from review.
- Audit trail: `budget_grants_audit_entry` records every state change in the same transaction (actor, action, entity, id),
  until the audit SDK exists, as in hostel and helpdesk.
- A grant with open commitments can't be closed (`open_commitments`), and amounts larger than the column holds are refused.
