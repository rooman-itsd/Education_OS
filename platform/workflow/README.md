# workflow

**Domain:** platform
**Kind:** platform
**Status:** in-progress

Configurable workflow and approval engine (state machines, SLAs, delegation).

## Scope
- **Responsible for:** Configurable multi-step approval chains (`ApprovalChain`, `ApprovalStep`); submission and tracking of workflow requests (`WorkflowRequest`); step transitions, SLAs, deadlines, and overdue detection; approvals, rejections, and user delegations (`WorkflowAction`); outbox event publishing (`workflow.request.submitted`, `workflow.step.advanced`, `workflow.request.approved`, `workflow.request.rejected`, `workflow.request.delegated`); tenant isolation enforced by PostgreSQL RLS on all workflow tables; pending approvals queue and dashboard widget (`workflow.approvals-pending`).
- **Explicitly NOT:** Direct modification of business entity states (calling modules handle entity mutations upon receiving workflow events); generic task management or ticketing (`support/helpdesk`); document attachment storage (`platform/documents`); long-term event audit trail (`platform/audit`); arbitrary script execution or untyped user workflows.

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
