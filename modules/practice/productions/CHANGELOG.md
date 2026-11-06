# Changelog — productions

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contracts (#318): productions API (productions, cast and crew, preparation tasks and the four widget
  endpoints), 12 domain events, and a permission catalogue of 7 keys with the module roles
  `productions-member`, `productions-lead` and `productions-coordinator`. PRD and user stories.
- Contract: the 29 academy profile roles whose dashboards show this module's widgets are granted the keys of
  the module role their widget needs. The role-reach test in #369 found 34 placements on 29 layouts answering
  403 because this catalogue was empty; `apps/backend/tests/test_role_inheritance.py` no longer lists them as
  known-unbacked.
- Backend (#318): domain rules (the status a production may be acted on from, date and call-time checks, the
  preparation warning, who may answer a part); use cases for creating, editing, preparing, scheduling,
  completing and cancelling a production, offering and answering and withdrawing a part, adding and completing
  preparation tasks, and the four widget queries; an outbox event for every state change.
- Backend: `client_token` is unique per **caller**, and decisions take a row lock (`FOR NO KEY UPDATE`), so a
  retry cannot return another user's production and two simultaneous answers cannot both apply — the two bugs
  the audit of #317 found in workflow.
- Alembic chain `pr_0001`: `productions_production`, `productions_role` and `productions_task`, each with
  `organisation_id` and the `tenant_isolation` RLS policy on Postgres.
- Widgets (#318): `productions.calendar` (GET /calendar), `productions.upcoming` (GET /upcoming),
  `productions.my-roles` (GET /my-roles) and `productions.in-preparation` (GET /in-preparation), each with
  loading, empty and error states; typed API client in `frontend/src/api/client.ts`.
- Enabled in `apps/backend/config/modules.enabled.yaml` and `apps/frontend/config/modules.enabled.yaml`, so the
  routes are mounted and the dashboards render the widgets instead of a "not built yet" card.
- Tests: domain unit tests, API integration tests, cross-tenant leak tests, profile-role reach tests and a
  migration test (64 passing); vitest widget tests (37 passing).
