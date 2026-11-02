# Changelog — reporting

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- MetricSnapshot ingestion through the event bus (#317 follow-up; sources agreed: admissions, academics,
  examinations, finance). `MetricSnapshot` had no writer, so every report and widget showed zeros.
  - `application/metrics.py`: versioned metric definitions (source events, unit, category, whitelisted
    dimensions, payload validation) for admissions (applications submitted / accepted / declined, offers),
    academics (course offerings, faculty contact hours by department) and finance (invoiced, collected net of
    voids, refunds, concessions, cancellations; category financial).
  - `application/ingest.py` on `eos.event_consumers`: one `reporting_metric_fact` per source event and metric
    (unique, so redelivery adds nothing), then the month's snapshot cell is recalculated; `recalculate()` and
    `POST /metrics/recalculate` (manage) rebuild a range. A malformed payload raises (retried, then dead-lettered).
    No person id, name or email reaches a fact.
  - Migration `reporting_0003` replaces `reporting_metric_snapshot` (never written anywhere) with the agreed fields
    (tenant, source_module, metric_key, period_start, period_end, dimensions JSONB, value, unit, calculated_at,
    schema_version) and adds `reporting_metric_fact`; both with RLS.
  - `GET /metrics`, `GET /metrics/definitions`: financial metrics need `reporting:report:execute`.
  - Reports and widgets read the new snapshots. examinations and timetable-attendance publish nothing yet (no
    code), so attendance and pass-rate reports say `available: false` with the reason, and widgets list them under
    `unavailable` instead of presenting zeros as data.
Contract 0.2.0: financial run summaries need `reporting:report:execute`; `client_token` is per requester.

### Fixed
- Financial report data is restricted to roles that may run and export reports. A run of a `financial`
  definition (e.g. `fee-collection-summary`) answers 404 on `GET /executions/{id}` without
  `reporting:report:execute`, and the department-reports widget lists financial runs only to those roles. Faculty
  (`reporting:report:read` only) keep academic and administrative summaries; export and download already needed
  execute.
- `client_token` idempotency is per requester (migration `reporting_0002`): replaying another user's token
  returned their run, result_summary included.
- The department-reports widget's recent runs carry the report's code and name, not the definition id.

### Added
- Implemented core domain models: `ReportDefinition`, `ReportExecution`, `MetricSnapshot`.
- Added database migration `reporting_0001` with PostgreSQL Row Level Security (`rls.POLICY`) and `ix_<table>_organisation_id` indexes on all 3 reporting tables.
- Implemented application service (`eos_reporting.application.service`) supporting standard report seeding, custom report management, report execution engine, CSV/JSON export via `platform/documents`, and outbox event publishing (`reporting.report.executed`, `reporting.report.exported`).
- Added FastAPI endpoints under `/api/v1/reporting` for report definitions, execution with idempotency, export generation, and widget data APIs guarded by `require(...)` permission dependencies.
- Defined OpenAPI 3.1 specification in `contracts/openapi.yaml`.
- Defined event catalogue in `contracts/events.yaml` (`reporting.report.executed`, `reporting.report.exported`).
- Defined permission catalogue in `contracts/permissions.yaml` granting roles `org-admin`, `management`, `department-admin`, `faculty`, and `super-admin`.
- Implemented frontend package `@eos/reporting` with typed API client, `reporting.department-reports` widget for Department Admin, and `reporting.attendance-and-results-by-department` widget for Management.
- Registered `reporting` platform service in `apps/backend/config/modules.enabled.yaml` and `apps/frontend/config/modules.enabled.yaml`.
- Added test suite: unit models, application service, API routes, Alembic migration round-trip, PostgreSQL RLS tenant isolation, and frontend Vitest widget tests.
