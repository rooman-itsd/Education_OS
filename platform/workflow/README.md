# workflow

**Domain:** platform
**Kind:** platform
**Status:** in-progress (enabled in `apps/backend`, mounted at `/api/v1/workflow`, and `apps/frontend`)

Configurable workflow and approval engine (state machines, SLAs, delegation).

## Scope
- **Responsible for:** Configurable multi-step approval chains (`ApprovalChain`, `ApprovalStep`); submission and tracking of workflow requests (`WorkflowRequest`); step transitions, SLAs, deadlines, and overdue detection; approvals, rejections, and user delegations (`WorkflowAction`); outbox event publishing (`workflow.request.submitted`, `workflow.step.advanced`, `workflow.request.approved`, `workflow.request.rejected`, `workflow.request.delegated`); tenant isolation enforced by PostgreSQL RLS on all workflow tables; pending approvals queue and dashboard widget (`workflow.approvals-pending`).
- **Explicitly NOT:** Direct modification of business entity states (calling modules handle entity mutations upon receiving workflow events); generic task management or ticketing (`support/helpdesk`); document attachment storage (`platform/documents`); long-term event audit trail (`platform/audit`); arbitrary script execution or untyped user workflows.

## Calling workflow from a module
A feature module may not import workflow (module standard: itself and `packages/` only). It submits through
`eos_core.workflow.submit`, which `apps/backend` wires at startup to this service's `create_request`, the use case
`POST /requests` runs, with the same input checks (the route's `NewRequestInput`):

```python
from eos_core import workflow

req = workflow.submit(db, organisation_id, chain_code="examinations.results",
                      entity_type="examinations.result_set", entity_id=result_set.id,
                      title="Semester 1 results", requested_by=principal.user_id,
                      client_token=f"results:{result_set.id}")
# {"id": ..., "status": "pending", "current_step_order": 1, "created": True}
```

- **The chain must exist first.** Workflow seeds no chain: each organisation's admin (`workflow:chain:write`)
  creates it through `POST /api/v1/workflow/chains`, e.g. code `examinations.results` with its steps and approver
  roles. Until then `submit()` raises `WorkflowRefusedError` with `code == "unknown_chain"` (also for an inactive
  chain); a module should say so to its user rather than fail. Chain codes are looked up within the organisation.
- **Requester.** `requested_by` is the acting user's id. They are the request's requester: they cannot approve,
  reject or delegate it, and `client_token` is idempotent per requester (a replay returns the first request with
  `created: False`). Workflow does not check `workflow:request:create` here; the module checks its own permission
  for the action before calling.
- **Transaction.** The request (status `pending`, at the chain's lowest `step_order`, with that step's SLA
  deadline) and its `workflow.request.submitted` event are written in the caller's session and committed or rolled
  back with the caller's own change. A refusal writes nothing and leaves the caller's transaction usable.
- **Where it works.** Only the API process wires the hook; elsewhere (the event-bus relay, a script)
  `submit()` raises `WorkflowUnavailableError`.
- **The outcome** arrives as `workflow.request.approved` or `workflow.request.rejected`, carrying the same
  `entity_type` and `entity_id`; their payloads are in [contracts/events.yaml](contracts/events.yaml).

## Who sees and acts on a request
- **Read:** org and super admins read every request. Everyone else reads their own requests, those delegated to
  them, those they acted on, and, if they hold `workflow:approval:action`, those that reached a step whose
  `approver_role` they hold. Anything else is 404 (`service.can_view`, `_visible_condition`).
- **Act:** the current step's `approver_role`, the delegate, or an admin; never the requester. Approve, reject and
  delegate lock the request row, and an optional `step_order` makes a late decision on a finished step a 409.
- **Idempotency:** `client_token` is unique per requester (`organisation_id, requester_id, client_token`).
- **SLA:** each step's deadline is its `sla_hours`, else `WORKFLOW_DEFAULT_SLA_HOURS`. The scheduled job
  `workflow.sla-check` escalates a pending step past its deadline once: a `workflow_escalation` row and a
  `workflow.step.overdue` event (retried by the relay until delivered).

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
