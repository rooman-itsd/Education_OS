# Changelog — grievance

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contracts proposed: committees; complaint intake on three tracks; acknowledgement, inquiry, proceedings, updates,
  decision, transfer, withdrawal and SGRC appeals; committee-scoped access to case content; `GET /stats/open-by-committee`
  and `GET /stats/open` behind the Governance and Management widgets; two metadata-only events; permissions and
  proposed roles.
- PRD (`docs/prd.md`).
- Backend: every operation of `contracts/openapi.yaml` (committees; filing, own cases, updates, withdrawal and appeal;
  committee-side list, read, status moves, updates, proceedings, decision, transfer and appeal decision; the two count
  endpoints), with committee-membership checks on every case operation, audit entries on changes and on reads of case
  content, and `grievance.case.filed` and `grievance.case.closed` written to the outbox in the same transaction.
- Own schema: Alembic chain `grievance_0001` with its own version table; every table has `organisation_id` and the
  `tenant_isolation` policy.
- Dashboard widgets `grievance.open-by-committee` and `grievance.open`.
- Tests: contract drift (routes, permissions, error statuses, enums, bodies, events), access, tenancy, transactions,
  migrations, settings, edge inputs and widgets.
- Docs: README backend and frontend sections with the assumptions to revisit, data model, integration points.
