# audit

**Domain:** platform
**Kind:** platform
**Status:** in-progress

Immutable, append-only audit log for every state-changing action.

## Scope
- **Responsible for:** Permanent, append-only recording of intentional state changes across all modules (`who, when, what entity, before/after values`); tenant-isolated queries via RLS; cross-org read tracking for super admins; legal redaction tombstones; compliance exports; retention window pruning.
- **Explicitly NOT:** Application/diagnostic logs (Sentry/structlog), event delivery buffers (`platform/event-bus`), analytics or reporting (`platform/reporting`), row-level CDC replication, live system of record for domain data, or binary document storage (`platform/documents`).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dashboard Widgets
- `audit.recent-activity`: Displays recent organization-scoped audit records for administrators.
- `audit.super-admin-actions`: Displays platform-level audit records. Note that this list contains audit's own `audit_trail.read` cross-organisation access trail records, until other platform services (such as tenancy organisation approve/suspend/impersonate) emit platform-level audit records.

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
