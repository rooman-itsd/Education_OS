# reporting

**Domain:** platform
**Kind:** platform
**Status:** in-progress

Dashboards, MIS reports, analytics, metric snapshots, and warehouse export integration.

## Scope
- **Responsible for:** Report definitions (`ReportDefinition`) supporting standard pre-seeded institutional reports and custom admin-defined reports; on-demand report execution (`ReportExecution`) with idempotency via `client_token`; metric snapshots (`MetricSnapshot`) for analytical caching; report export generator producing CSV and JSON exports stored in `platform/documents` via `direct_upload`; outbox event publishing (`reporting.report.executed`, `reporting.report.exported`); tenant isolation enforced by PostgreSQL RLS on all reporting tables (`reporting_definition`, `reporting_execution`, `reporting_metric_snapshot`); dashboard widgets `reporting.department-reports` for Department Admin and `reporting.attendance-and-results-by-department` for Management; frontend client and widgets package (`@eos/reporting`).
- **Explicitly NOT:** Live operational transaction mutations (modifications occur in respective feature modules); binary file storage management (delegated to `platform/documents`); immutable audit record logging (`platform/audit`); arbitrary user script execution.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

## Layout
| Path | Purpose |
|---|---|
| `docs/` | PRD, user stories, data model, screen list |
| `contracts/` | OpenAPI, event schemas, permission catalogue |
| `backend/` | Domain, application, infrastructure, API layers + unit tests |
| `frontend/` | Pages, components, API client + tests |
| `mobile/` | Mobile screens (optional) |
| `db/` | Migrations and seed data, own schema only |
| `config/` | `env.example`, feature flags |
| `tests/e2e` | End-to-end tests runnable in isolation |

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../docs/architecture/module-standard.md#portability-checklist).
