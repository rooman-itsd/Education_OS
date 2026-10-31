# hr-payroll

**Domain:** finance-operations
**Kind:** feature
**Status:** planned

Employee master, leave, payroll, appraisals, service records.

## Scope
_Owner fills in: what this module is responsible for, and what it explicitly is not._

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

## Frontend

`frontend/src/widgets/index.ts` exports the dashboard widgets. The HR Staff layout in
`platform/identity/config/dashboards/` places them; `apps/frontend/config/modules.enabled.yaml` registers the module
(a separate PR).

| Widget | Title | Dashboard | Endpoint | Permission |
|---|---|---|---|---|
| `hr-payroll.leave-requests` | Leave requests pending | HR Staff | `GET /leave-requests?status=pending` | `hr-payroll:leave:approve` |
| `hr-payroll.payroll-run-status` | Payroll this month | HR Staff | `GET /payroll-runs/current` | `hr-payroll:payroll:read` |
| `hr-payroll.joinings-and-exits` | Joinings and exits | HR Staff | `GET /reports/joinings-and-exits` | `hr-payroll:report:read` |

- **Leave requests pending:** how many requests wait for a decision, and the first five in the contract's order
  (soonest start first) with employee, leave type, dates (with the half for half a day), days and an "Unpaid" badge for
  loss of pay. Empty: "No leave requests pending".
- **Payroll this month:** the run for this month, or the latest one with a line saying so; its month, status badge,
  a "Late" badge when the contract flags it, employees paid, net pay in rupees, who acts next (HR submits, finance or
  management approves, finance marks it paid), the due date until it is approved, the approver's note when it was
  returned, and the number of exceptions. The contract's 404 `not_found` (no run yet) is the empty state "No payroll
  run this month"; a 404 without that code means the module is not mounted and is an error.
- **Joinings and exits:** the report's default range (the first of this month to today): joined, exited and headcount,
  then up to five recent joinings, recent exits and people serving notice, each with designation, department and date.
  Empty: "No joinings or exits this month".
- **Data:** the widgets read through `src/api/client.ts`, a hand-written typed client that the generated client will
  replace. Amounts are the contract's decimal strings, shown exactly in rupees (`₹57,37,654.50`).
- **States:** loading, empty, and error with a retry when trying again can help. Until the backend is mounted, the
  error reads "HR data is not available yet."; without the permission, "You do not have access to this." (no retry);
  with an expired session, "Sign in again to see this." (no retry); any other failure, "Could not load HR data.".
- **Tests:** `cd modules/finance-operations/hr-payroll/frontend && pnpm test` (vitest and Testing Library).

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
