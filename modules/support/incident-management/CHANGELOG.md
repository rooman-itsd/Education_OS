# Changelog — incident-management

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contracts proposed: incidents with status, severity, timeline and references; problems with known errors;
  root-cause analysis; corrective actions; `GET /stats/open` behind the Support Staff widget
  `incident-management.open`; six events; permissions and roles.
- PRD (`docs/prd.md`).
- Backend (#342): domain rules (incident statuses and moves, resolution summary to resolve, note to cancel or reopen;
  problem statuses, workaround for a known error, published RCA to resolve; RCA draft and publish, read-only once
  published; corrective actions with overdue worked out when read); use cases for every contract operation with an
  audit entry per change and outbox events for the six events in `events.yaml`; per-organisation incident and
  problem numbers; references to other modules by id only; API router for all 20 operations.
- Alembic chain `incident_management_0001`: eight `incident_management_*` tables with `organisation_id`, RLS policy
  on Postgres.
- Tests: domain unit tests, API integration tests, edge-input tests, contract drift and event payload tests,
  cross-tenant leak test, migration test, settings test, row-level security and concurrency on Postgres (opt-in).
- Widget `incident-management.open` (GET /stats/open) with loading, empty and error states following the widget
  error convention; typed API client in `frontend/src/api/client.ts`; vitest widget tests.
- NUL characters never reach the database: Postgres cannot store them in text, so a NUL in a request body is a 422
  and in the URL a 404 (path ids) or 422 (query parameters), instead of a 500 (`api/deps.py` `no_nul`, `Strict`).
- Editing an incident or a problem refuses a blank description (422), as reporting and opening do: PATCH takes the
  same three-character minimum and `description_blank` for spaces. Adding a timeline update and adding a corrective
  action lock the incident or problem row first, as references and the status moves do, so neither can land on a
  record that a close or cancel is committing at the same moment (409).
