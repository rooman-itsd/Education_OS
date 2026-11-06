# Changelog — rti

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contracts proposed: request intake with applicant and fee metadata, assignment, custodian referrals, response,
  transfer, close and first appeals; `GET /stats/nearing-deadline` behind the Governance widget `rti.nearing-deadline`;
  two metadata-only events; permissions and proposed roles.
- PRD (`docs/prd.md`).
- Backend (#343): domain rules (statuses and moves, dates in India, calendar or working day counting, due dates, the
  deadline list); use cases for all 14 operations, with an audit entry per change and per read and outbox events for
  `rti.request.received` and `rti.request.closed`; API router for every path in the contract, with bounded inputs and
  NUL characters, NaN, Infinity and lone surrogates refused before the database. No statutory period is built in: the
  three timeline settings stay empty until the governance office sets them.
- Alembic chain `rti_0001`: six `rti_*` tables with `organisation_id`, RLS policy on Postgres.
- Tests: domain, settings, API per area, deadline list, dashboard roles, contract drift (routes, permissions, enums,
  error statuses, event payloads, response shapes), hostile input, atomicity of change, audit and event, cross-tenant
  leak test, migration test, row-level security on Postgres (opt-in).
- Widget `rti.nearing-deadline` (GET /stats/nearing-deadline) with loading, empty and error states following the widget
  error convention; typed API client; vitest widget tests. Test dev dependencies added to `frontend/package.json`.
