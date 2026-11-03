# Changelog — workflow

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- SLA monitoring (#317 follow-up). Deadlines were only computed when read, a step without `sla_hours` had none, and
  `WORKFLOW_DEFAULT_SLA_HOURS` was read by nothing. A step now gets its `sla_hours`, else the default; the scheduled
  platform job `workflow.sla-check` (`*/15 * * * *`, entry point `eos.scheduler_jobs`) records each pending step
  past its deadline once (`workflow_escalation`, migration `workflow_0003`, unique per request step, RLS) and
  publishes `workflow.step.overdue`; it reports `workflow.job.finished`. `backend/pyproject.toml` gains its build
  system, package location, `test` extra and the two entry points.
Contract 0.2.0: request reads and delegation targets are narrower (security fixes below); `step_order` on
actions is new and optional.

### Fixed
- `client_token` idempotency is per requester (migration `workflow_0002`): replaying another user's token created
  nothing new and returned their request, context included. It now creates the caller's own request.
- Request reads follow who is involved: department admins and other approvers see requests that reached a step
  their role approves, are delegated to them, or that they acted on; org and super admins see all. Before, any
  holder of `workflow:approval:action` read every request in the organisation.
- Approve, reject and delegate lock the request row (`SELECT ... FOR UPDATE`), so two concurrent decisions can no
  longer both apply (an approve and a reject both recorded, or one step approved twice). Actions accept an optional
  `step_order` and answer 409 if the request has already moved past it.
- Delegation requires a target holding `workflow:approval:action` who is not the requester, so a delegated item
  can no longer sit in a queue whose owner is refused every action.
- Creating a chain whose code differs only by surrounding spaces, or racing a second create, answers 409, not 500.

### Added
- Implemented core domain models: `ApprovalChain`, `ApprovalStep`, `WorkflowRequest`, `WorkflowAction`.
- Added database migration `workflow_0001` with PostgreSQL Row Level Security (`rls.POLICY`) and `ix_<table>_organisation_id` indexes on all 4 workflow tables.
- Implemented application service (`eos_workflow.application.service`) supporting chain authoring, request submission, multi-step state transitions, SLA deadlines, delegation, and outbox event publishing via `eos_core.events.publish`.
- Added FastAPI endpoints under `/api/v1/workflow` for approval chains, request search, pending approvals queue, approve, reject, and delegate operations.
- Defined OpenAPI 3.1 specification in `contracts/openapi.yaml`.
- Defined event catalogue in `contracts/events.yaml` (`workflow.request.submitted`, `workflow.step.advanced`, `workflow.request.approved`, `workflow.request.rejected`, `workflow.request.delegated`).
- Defined permission catalogue in `contracts/permissions.yaml` granting roles `department-admin`, `org-admin`, `faculty`, `student`, and `super-admin`.
- Implemented frontend widget `workflow.approvals-pending` (`ApprovalsPending.tsx`) and exported it from `platform/workflow/frontend/src/widgets`.
- Registered `workflow` service in `apps/backend/config/modules.enabled.yaml` and `apps/frontend/config/modules.enabled.yaml`.
- Added test suite: unit models, application service, API routes, Alembic migration round-trip, PostgreSQL RLS tenant isolation, and frontend vitest widget tests.
