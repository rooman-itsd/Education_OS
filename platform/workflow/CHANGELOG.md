# Changelog — workflow

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
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
