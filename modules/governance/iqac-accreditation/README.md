# iqac-accreditation

**Domain:** governance
**Kind:** feature
**Status:** in-progress (contracts proposed; backend, migrations, tests and the `iqac-accreditation.action-items`
widget built; not yet enabled in `apps/backend` and `apps/frontend`)

IQAC data collection, NAAC/NBA metrics, evidence repository.

## Scope
Owner: Madhumita (@madhumitha-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** the organisation's accreditation frameworks and their metrics; collection cycles; assigning metrics to
owners; responses (values or narratives) with evidence as links or references; review (accept or return); quality action
items; the counts behind the Governance widget `iqac-accreditation.action-items`. No accreditation content is built in.

**Not in scope:** evidence files, computing metric values from other modules, submitting to accrediting bodies' portals,
grades and peer team outcomes, statutory returns (regulatory-reports), reminders and timers.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)
- Dashboard widget: `iqac-accreditation.action-items` (Governance dashboard), exported from
  `frontend/src/widgets/index.ts`

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

What it needs from the host repo:
- `packages/core` (`eos_core`): database base and tenant scoping, row-level-security policy, token checks, permission
  catalogue, outbox for events. `packages/testing` for the cross-tenant leak test.
- `packages/ui-kit` for the widget.
- No platform service is called directly yet: identity is the token check in `api/deps.py`, audit is the module's own
  `iqac_accreditation_audit_entry` table, and owners are not notified (see "Assumptions to revisit"), because
  `packages/sdk` has none of them. Events go to the outbox.
- The API router is `eos_iqac_accreditation.api.router:router`. Mounting it under `/api/v1/iqac-accreditation` and
  registering the widget are done by adding `governance/iqac-accreditation` to `apps/backend/config/modules.enabled.yaml`
  and `apps/frontend/config/modules.enabled.yaml` in a separate pull request.
- Configuration: `IQAC_ACCREDITATION_DUE_SOON_DAYS` (default 14, 1 to 366) in `config/env.example`; a bad value is a
  deployment error.

## Run the checks
```
pip install -e modules/governance/iqac-accreditation/backend[test]       # into the repo .venv
cd modules/governance/iqac-accreditation/backend && python -m pytest -q  # throwaway SQLite, never a real database
IQAC_ACCREDITATION_TEST_POSTGRES_URL=postgresql://postgres@localhost/postgres python -m pytest -q tests/test_rls_postgres.py
pnpm --filter @eos/iqac-accreditation typecheck && pnpm --filter @eos/iqac-accreditation test
cd modules/governance/iqac-accreditation/db && alembic upgrade head      # own tables and iqac_accreditation_alembic_version only
```
The Postgres test is skipped unless that variable points at a throwaway PostgreSQL server (it creates and drops its own
database and role).

## Backend
`backend/src/eos_iqac_accreditation/`: `domain/` (statuses, moves and rules, no framework), `application/` (use cases,
access, errors), `infrastructure/` (tables, queries, settings), `api/` (router, request bodies, token guard).

- **Routes (23):** frameworks and their metrics, cycles with their status moves and assignments, responses with
  evidence and review, action items, and `GET /stats/action-items`, with exactly the paths and permissions of
  `contracts/openapi.yaml`.
- **Tables (7):** `iqac_accreditation_` framework, metric, cycle, response, evidence, action_item, audit_entry. Migration
  `iqac_accreditation_0001`, each table with `organisation_id` and the forced `tenant_isolation` policy.
- **Events (2):** `cycle.status-changed` on every cycle move and `response.accepted`, written to the outbox in the same
  transaction as the change and its audit entry. Payloads never carry values, narratives, evidence or comments.
- **Errors:** `{"detail": {"code", "message", "field"?}}`. 401 without a valid token, 403 without a permission the
  contract names, 404 for a record that is not in the caller's organisation or not visible to them, 409 for a refused
  move or a duplicate, 422 for a bad value. Every string, number, date (1900 to 2199), enum, uuid and cursor is bounded;
  NUL characters, `NaN` and `Infinity` are refused with a 422 and never reach the database.

## Frontend
`frontend/src/widgets/ActionItemsWidget.tsx` is `iqac-accreditation.action-items` (permission
`iqac-accreditation:stats:read`): the open, in-progress, overdue and due-soon counts and the soonest ten items, with
loading, empty and error-with-retry states, through the typed client in `frontend/src/api/client.ts`. No pages yet.

## Assumptions to revisit
Where the PRD or the contract leaves a detail open, the simplest reading was taken:

1. **Owners are not notified.** The contract promises notices on assignment and return, but `packages/sdk` has no
   notification service and the module holds no addresses. Assignments, returns and new or reassigned action items are
   audited and name the owner, and no event carries them (events.yaml has two), so a notice can be added later.
2. **"Open cycle"** (a framework used by one cannot be deactivated) means a cycle that is not `closed`.
3. **A cycle with no responses can be submitted**: "every response is accepted" holds for none.
4. **`PATCH /frameworks/{id}`** takes any of code, name, description and active (the contract's `FrameworkInput`
   requires code and name even on PATCH). A field sent as null keeps its value, as in regulatory-reports.
5. **A reference to a record that does not exist** in the request (framework of a cycle, metric of an assignment, cycle
   or metric of an action item) is a 422, not a 404: it is a value of the request, not its address.
6. **`PUT /responses/{id}`** sets the fields it is sent; one left out keeps its stored value and `null` clears it. A
   value on a qualitative metric is a 422. Saving and submitting need the cycle to be `collecting` or `under_review`
   (409 `cycle_not_collecting` otherwise), as the PRD says.
7. **Review:** a comment sent with an accept is kept; an accept without one clears an earlier return comment. A return
   comment is at least three characters without spaces.
8. **Action items** move `open → in_progress → done` in that order for everyone (a coordinator cannot skip), and
   either of the first two can be cancelled by a holder of `action-item:manage`. An owner with only `update-own` who
   sends another field or `cancelled` gets a 403. `note` is kept in the audit entry of a status change and ignored
   otherwise.
9. **Evidence:** a link needs `url` (http or https only, so a link never runs script in a reader's browser) and no
   reference; a reference needs `reference` and no url. There is no limit on evidence per response.
10. **Visibility:** with only `response:submit` (or `action-item:update-own`) a caller sees their own records; asking
    for another owner gives an empty page, not a 403, and another person's record is a 404.
11. **Counts:** `GET /stats/action-items` counts every action item of the organisation, not only the caller's. Due today
    is due soon, not overdue.
12. **Bounds** the contract leaves open: dates from 1900-01-01 to 2199-12-31, a metric value at most 1e15 in size and
    finite, a narrative at most 20 000 characters, other text at most 5 000 or 10 000, at most 200 assignments per call.
13. **Both events are kept public** (PRD open question 8); no consumer is assumed.

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
