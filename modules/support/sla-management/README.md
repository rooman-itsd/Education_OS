# sla-management

**Domain:** support
**Kind:** feature
**Status:** in-progress (backend, consumers and widget built and tested; enabled in `apps/backend` and `apps/frontend`)

SLA definitions, timers, escalation and breach tracking.

## Scope
Owner: Madhumita (@madhumitha-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** business-hours calendars; SLA policies per helpdesk priority and category with response and
resolution targets, warning thresholds, pausing hold reasons and escalation levels; response and resolution
clocks per helpdesk ticket, driven by helpdesk's ticket events; warnings, breaches and escalation notices
through notification; the breach counts behind the Support Staff widget `sla-management.breaches`.

**Not in scope:** tickets and their status (helpdesk), SLAs of maintenance, incident-management and
amc-vendor-support, deadlines on approval steps (workflow), escalation by reassignment or approval.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

## Backend
Package `eos_sla_management` in `backend/src/`:

| Layer | Files | What |
|---|---|---|
| domain | `domain/business_time.py`, `policies.py`, `clocks.py`, `errors.py` | Business minutes in a calendar (time zone, working intervals per ISO weekday, holidays, always open; daylight saving followed); calendar checks; policy rules and which policy applies; clock states and moves; warning threshold and escalation recipients. Pure Python. |
| application | `application/service.py`, `engine.py`, `consumers.py`, `access.py`, `errors.py` | The use case behind every contract operation; the clock engine (start, pause, resume, reopen, recalculate, stop, cancel, and recording warnings, breaches and escalations); the helpdesk event consumers; permission keys and checks; errors with their HTTP status. Every change writes an audit entry; clock changes publish their event from `contracts/events.yaml` to the `eos_core` outbox in the same transaction. |
| infrastructure | `infrastructure/models.py`, `repository.py`, `config.py` | The tables of the PRD data model, queries scoped to the organisation, `SLA_MANAGEMENT_*` settings. |
| api | `api/router.py`, `schemas.py`, `deps.py` | All 12 operations of `contracts/openapi.yaml`, each with the permission the contract names. Error bodies are `{code, message[, field]}` in FastAPI's `detail`. |

Tables are prefixed `sla_management_` and created by the module's own Alembic chain in `db/` (revision
`sla_management_0001`, version table `sla_management_alembic_version`). Every table carries `organisation_id`; on
Postgres each gets the `eos_core.rls` row-level-security policy. As in helpdesk and amc-vendor-support, a temporary
`sla_management_audit_entry` table holds one row per change until the audit SDK and `platform/audit` exist.

Clocks are driven by helpdesk's events (`application/consumers.py`, entry point `eos.event_consumers` in
`backend/pyproject.toml`, the nine events in `module.yaml`). Each event is applied once by envelope id, one ticket
at a time (the ticket's `ticket_ref` row is locked), in the envelope's organisation; a malformed event is logged
without its content and ignored. Times come from helpdesk's payloads, never from when the event is processed.

Warnings, breaches and escalations: the API reports a running clock breached or at risk as soon as its due or warning
time passes. The `clock.warning-raised`, `clock.breached` and `clock.escalated` events and escalation records are
written when the clock is next checked: on the ticket's next helpdesk event, or by `service.check_due_clocks`, which
the scheduler job is to call once PRD open question 1 is settled. Recipients are notified through these events
until the notification SDK exists. Details the contract leaves open are noted in `application/service.py`,
`engine.py` and `consumers.py` where they are decided.

### Needs from the host repo
- `packages/core` (`eos_core`); for tests, `packages/testing` (`eos_testing`).
- IANA time zones resolve from the host's time-zone database (`zoneinfo`); `UTC` always works. On a host without one,
  any other time zone is refused with 422. `tzdata` is not on the approved stack.
- `support/sla-management` in `apps/backend/config/modules.enabled.yaml`, added in a later pull request of #342. From
  that list the module loader mounts `eos_sla_management.api.router:router` at `/api/v1/sla-management`, the API image
  installs the package (which registers the consumers), the auto-deploy runs the Alembic chain and CI runs
  `backend/tests`. Until then the module's tests run only as shown below.
- helpdesk publishing its ticket events, and a scheduler job calling `check_due_clocks` (PRD open question 1).
- Permissions come from the roles in the token. The `support-staff` profile role gets the grants of
  `sla-management-viewer` through its dashboard layout, so it can read clocks and the widget. No layout grants
  `sla-management-admin` yet, so on a live site nobody can set up calendars and policies until one does.

## Frontend
`frontend/src/widgets/BreachesWidget.tsx` is the Support Staff widget `sla-management.breaches`
(`platform/identity/config/dashboards/support-staff.yaml` already lists it): counts of breached and at-risk running
clocks and of breaches in the last 24 hours, and the most overdue clocks with ticket number, kind, priority, due
time and "N min over", from `GET /api/v1/sla-management/stats/breaches` (permission `sla-management:clock:read`).
"My tickets" (`scope=mine`) is the default; "All tickets" shows every clock. Rows do not link to the ticket yet:
helpdesk has no ticket route in the app shell. While the API is not mounted or unreachable (404, 502, 503, network
failure) it says "SLA data is not available yet."; a 401 or 403 offers no retry. `frontend/src/api/client.ts` is a
small typed client matching the contract's `BreachSummary`. Tests are in `frontend/tests/` (Vitest and Testing
Library).

## Run the checks
```
cd modules/support/sla-management/backend
PYTHONPATH=src:../../../../packages/core/src:../../../../packages/testing/src python -m pytest -q tests
#   Python 3.12; dependencies plus the test extras (pytest, pyyaml, httpx, eos-testing, psycopg[binary])
cd modules/support/sla-management/db && alembic upgrade head                  # own tables only; EOS_DATABASE_URL
ruff check --config tools/config/ruff.toml modules/support/sla-management    # from the repo root
ruff format --config tools/config/ruff.toml --check modules/support/sla-management
pnpm --filter @eos/sla-management typecheck && pnpm --filter @eos/sla-management test   # widget
```
Instead of `PYTHONPATH`, the module can be installed with its test extras, from the repo root:
`pip install ./packages/core ./packages/testing "./modules/support/sla-management/backend[test]"`. It does not
depend on `packages/sdk`, which has no package yet. Tests use a throwaway SQLite file, never a real database.

Row-level security on a real PostgreSQL: `tests/test_rls_postgres.py` runs only when
`SLA_MANAGEMENT_TEST_POSTGRES_URL` is set to a superuser URL of a **throwaway** server (for example
`postgres:16-alpine`). It creates its own database and a temporary role that is neither a superuser nor allowed to
bypass RLS, checks the forced `tenant_isolation` policy on all 7 tables, checks on 4 of them that each organisation
sees and writes only its own rows, checks that two concurrent first events of a ticket share one `ticket_ref` row
and that a duplicate event delivered twice at once is applied once, then drops both. It is a test setting, not
module configuration, so it is not in `config/env.example`.

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
Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
