# Changelog — regulatory-reports

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contracts proposed: organisation-defined obligations; filings per period with preparation, review, submission and
  acknowledgement; `GET /stats/due` and `GET /calendar` behind the widgets `regulatory-reports.due` and
  `regulatory-reports.compliance-calendar`; two metadata-only events; permissions and proposed roles.
- PRD (`docs/prd.md`).
- Backend (#343): domain rules (filing statuses and moves, periods, due soon and overdue); use cases for all 13
  operations, with preparers limited to their own filings, an audit entry per change and outbox events for submission
  and acknowledgement; API router for every path in the contract, with NUL characters refused before the database.
- Alembic chain `regulatory_reports_0001`: three `regulatory_reports_*` tables with `organisation_id`, RLS policy on
  Postgres.
- Tests: API tests per area, statistics and calendar, dashboard roles through their layouts, contract and event payload
  tests, cross-tenant leak test, migration test, settings test, NUL test, row-level security on Postgres (opt-in).
- Widgets `regulatory-reports.due` (GET /stats/due) and `regulatory-reports.compliance-calendar` (GET /calendar) with
  loading, empty and error states following the widget error convention; typed API client; vitest widget tests.
