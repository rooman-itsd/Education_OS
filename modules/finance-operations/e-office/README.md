# e-office

**Domain:** finance-operations
**Kind:** feature
**Status:** planned

File movement, notings, approvals, digital correspondence.

## Scope
_Owner fills in: what this module is responsible for, and what it explicitly is not._

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

## Frontend

`frontend/src/widgets/index.ts` exports the dashboard widget. The HR Staff layout in
`platform/identity/config/dashboards/hr-staff.yaml` places it, and `apps/frontend/config/modules.enabled.yaml`
registers the module (a separate PR).

| Widget | Dashboard | Endpoint | Permission |
|---|---|---|---|
| `e-office.files-pending` | HR Staff | `GET /me/inbox?limit=5` | `e-office:file:use` |

- **Files pending with me:** how many open files the viewer holds, how many of them are urgent (priority urgent or
  immediate) and how many are overdue, the overdue ones highlighted with a danger badge ("2 files overdue"); a line
  when letters received are still to be attached to a file; and the five files waiting longest, each with its number,
  subject, the action asked for, and "Due <date>" (or "Received <date>" when it was sent without a due date), with an
  "Overdue" badge and an "Urgent" or "Immediate" badge where they apply. "Showing 5 of 12 files" when the inbox holds
  more. Dates are Indian ("5 Nov 2026"); the date received is the date in Asia/Kolkata, as the contract's business
  dates are. The contract's file summary has no sender, so the widget does not say whom a file came from.
- **Data:** the widget reads through `src/api/client.ts`, a hand-written typed client that the generated client will replace.
- **States:** loading; empty ("No files pending") when no file is held and no letter waits to be attached; and error
  with a retry when trying again can help. Until the backend is mounted, the error reads "File data is not available
  yet."; without the permission, "You do not have access to this."; with an expired session, "Sign in again to see
  this."; any other failure, "Could not load file data.".
- **Tests:** `cd modules/finance-operations/e-office/frontend && pnpm test` (vitest and Testing Library), or
  `corepack pnpm --filter @eos/e-office test` from the repo root.

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
