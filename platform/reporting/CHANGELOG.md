# Changelog — reporting

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
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
