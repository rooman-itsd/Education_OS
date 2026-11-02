# amc-vendor-support

**Domain:** support
**Kind:** feature
**Status:** in-progress (backend and widget built and tested; not yet listed in `modules.enabled.yaml`)

AMC contracts, vendor support engagements, renewals.

## Scope
Owner: Madhumita (@madhumitha-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** AMC contracts with vendors (period, coverage type, value, response terms, contacts) and the items they
cover; activation, renewal and early termination; expiring and expired contracts worked out when read; support calls
and service visits (engagements) under a contract; the coverage lookup for other modules' screens; the statistics
behind the Support Staff widget `amc-vendor-support.contracts-expiring`.

**Not in scope:** the vendor master, vendor approval and blacklisting, purchase orders, invoices and payments
(procurement); repairs (maintenance); the asset register and warranties (asset-management); SLA clocks
(sla-management); contract documents; renewal reminders.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

## Backend
Package `eos_amc_vendor_support` in `backend/src/`:

| Layer | Files | What |
|---|---|---|
| domain | `domain/contracts.py`, `engagements.py`, `expiring.py`, `errors.py` | Contract statuses (draft, active, terminated, renewed) and what may change in each; renewal and termination rules; engagement statuses and the moves between them; whether an engagement met the contract's response and resolution terms; the expiring-contracts list. Pure Python. |
| application | `application/service.py`, `access.py`, `errors.py` | The use case behind every contract operation; permission keys and checks; errors with their HTTP status. Every state change writes an audit entry, and activation, renewal and termination publish their event from `contracts/events.yaml` to the `eos_core` outbox in the same transaction. |
| infrastructure | `infrastructure/models.py`, `repository.py`, `config.py` | The tables of the PRD data model, queries scoped to the caller's organisation, per-organisation numbering, `AMC_VENDOR_SUPPORT_*` settings. |
| api | `api/router.py`, `schemas.py`, `deps.py` | All 16 operations of `contracts/openapi.yaml`, each with the permission the contract names. Error bodies are `{code, message[, field]}` in FastAPI's `detail`. |

Tables are prefixed `amc_vendor_support_` and created by the module's own Alembic chain in `db/` (revision
`amc_vendor_support_0001`, version table `amc_vendor_support_alembic_version`). Every table carries
`organisation_id`; on Postgres each gets the `eos_core.rls` row-level-security policy. As in helpdesk, a temporary
`amc_vendor_support_audit_entry` table holds one row per state change until the audit SDK and `platform/audit` exist;
`_audit` in `application/service.py` then calls the SDK instead.

Expiry is worked out when read, never stored: an active contract is expiring when its end date is within its
`renewal_notice_days`, and expired once the end date has passed. `GET /stats/contracts-expiring` lists active
contracts ending within `within_days` (default `AMC_VENDOR_SUPPORT_EXPIRY_WINDOW_DAYS`, 1 to 366) and those already
past their end date, soonest first. Details the contract leaves open are noted in `application/service.py` where they
are decided.

### Needs from the host repo
- `packages/core` (`eos_core`); for tests, `packages/testing` (`eos_testing`).
- `support/amc-vendor-support` in `apps/backend/config/modules.enabled.yaml`, added in a later pull request of #342.
  From that list the module loader mounts `eos_amc_vendor_support.api.router:router` at `/api/v1/amc-vendor-support`,
  the API image installs the package, the auto-deploy runs the Alembic chain and CI runs `backend/tests`. Until then
  the module's tests run only as shown below.
- Permissions come from the roles in the token. The `support-staff` profile role gets the grants of
  `amc-vendor-support-viewer` through its dashboard layout, so it can read contracts and the widget. No layout grants
  `amc-vendor-support-contract-manager` or `amc-vendor-support-coordinator` yet, so on a live site nobody can create
  contracts or raise engagements until a layout grants them.

## Frontend
`frontend/src/widgets/ContractsExpiringWidget.tsx` is the Support Staff widget `amc-vendor-support.contracts-expiring`
(`platform/identity/config/dashboards/support-staff.yaml` already lists it): active contracts ending soon and those
already expired, soonest first, each with "N days left", "Ends today" or "Expired N days ago" and whether a renewal is
drafted, from `GET /api/v1/amc-vendor-support/stats/contracts-expiring` (permission `amc-vendor-support:contract:read`).
It uses `@eos/ui-kit` (`List`, `ListRow`, `Badge`, `SkeletonLines`, `EmptyState`, `ErrorState`). While the API is not
mounted or unreachable (404, 502, 503, network failure) it says "AMC data is not available yet."; a 401 or 403 offers
no retry. `frontend/src/api/client.ts` is a small typed client matching the contract's `ContractsExpiring`, until the
repo has a generated client. Tests are in `frontend/tests/` (Vitest and Testing Library).

The dashboard shows the widget once `apps/frontend/config/modules.enabled.yaml` lists `support/amc-vendor-support`.

## Run the checks
```
cd modules/support/amc-vendor-support/backend
PYTHONPATH=src:../../../../packages/core/src:../../../../packages/testing/src python -m pytest -q tests
#   Python 3.12; dependencies plus the test extras (pytest, pyyaml, httpx, eos-testing, psycopg[binary])
cd modules/support/amc-vendor-support/db && alembic upgrade head                  # own tables only; EOS_DATABASE_URL
ruff check --config tools/config/ruff.toml modules/support/amc-vendor-support    # from the repo root
ruff format --config tools/config/ruff.toml --check modules/support/amc-vendor-support
pnpm --filter @eos/amc-vendor-support typecheck && pnpm --filter @eos/amc-vendor-support test   # widget
```
Instead of `PYTHONPATH`, the module can be installed with its test extras, from the repo root:
`pip install ./packages/core ./packages/testing "./modules/support/amc-vendor-support/backend[test]"`. It does not
depend on `packages/sdk`, which has no package yet. Tests use a throwaway SQLite file, never a real database.

Row-level security on a real PostgreSQL: `tests/test_rls_postgres.py` runs only when
`AMC_VENDOR_SUPPORT_TEST_POSTGRES_URL` is set to a superuser URL of a **throwaway** server (for example
`postgres:16-alpine`). It creates its own database and a temporary role that is neither a superuser nor allowed to
bypass RLS, checks the forced `tenant_isolation` policy on all 5 tables, checks on 3 of them
(`amc_vendor_support_contract`, `amc_vendor_support_number_sequence`, `amc_vendor_support_audit_entry`) that each
organisation sees and writes only its own rows, then drops both. It is a test setting, not module configuration, so
it is not in `config/env.example`.

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
