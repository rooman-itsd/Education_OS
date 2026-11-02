# audit

**Domain:** platform
**Kind:** platform
**Status:** in-progress

Immutable, append-only audit log for every state-changing action.

## Scope
- **Responsible for:** Permanent, append-only recording of intentional state changes across all modules (`who, when, what entity, before/after values`); tenant-isolated queries via RLS; cross-org read tracking for super admins; legal redaction tombstones; compliance exports; retention window pruning.
- **Explicitly NOT:** Application/diagnostic logs (Sentry/structlog), event delivery buffers (`platform/event-bus`), analytics or reporting (`platform/reporting`), row-level CDC replication, live system of record for domain data, or binary document storage (`platform/documents`).

## How records arrive
- **From the outbox.** `application/consumers.py` is published on event-bus's `eos.event_consumers` entry point and
  records every event in its `AUDITED` list (tenancy lifecycle and super admin operations, identity users,
  billing subscription and invoice state, workflow decisions, documents, report runs and exports) as one record
  in the event's organisation: `module` and `action` from the event name, the event's actor and time, the
  payload as `after`. Idempotent on the event id. Keys that look like secrets are dropped and named in
  `context.dropped_keys`. Anything else that fails raises, so the relay retries and finally dead-letters.
- **Super admin operations** (`SUPER_ADMIN_ACTIONS`: approve, package change, suspend, archive, export, deletion
  request, restore, purge, impersonation) also get a platform-level record (`organisation_id` null,
  `context.organisation_id` set), which `audit.super-admin-actions` reads.
- **Directly**, in the caller's transaction, through `service.record()` or `POST /records` (role `service`).
- **Retention:** the scheduled platform job `audit.prune` (daily, 02:30 UTC) runs `service.prune()`.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dashboard Widgets
- `audit.recent-activity`: Displays recent organization-scoped audit records for administrators.
- `audit.super-admin-actions`: Displays platform-level audit records: super admin operations on organisations (from tenancy's events, see above) and audit's own `audit_trail.read` cross-organisation access trail.

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
