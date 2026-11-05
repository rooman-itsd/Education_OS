# Changelog — lms

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Backend (`eos_lms`): every operation of contract 0.1.0 in domain, application, infrastructure and api layers, each
  behind its `x-permission` and narrowed to the caller's course spaces; events to the outbox in the change's
  transaction; an audit entry for every state change; request bodies and query parameters bounded (400, never a 500).
- Consumers of academic-management offering and faculty-assignment events and enrolment-registration
  course-registration and section-allocation events, filling the offering, instructor and membership read models;
  declared in `module.yaml` and the `eos.event_consumers` entry point.
- Migration `lms_0001`: sixteen tables, each with `organisation_id` and the forced `tenant_isolation` policy, in
  `lms_alembic_version`.
- Job `submit_overdue_attempts` for platform/scheduler.
- Tests: contract drift (routes, permissions, bodies, error statuses, enums), event payloads, outbox and audit in one
  transaction, the cross-tenant leak test, consumers, hostile input on every field, migrations against the models,
  and the use cases of every area.
- Widgets `lms.assignments-to-grade` (Faculty) and `lms.course-materials` (Student), built on `@eos/ui-kit`, with
  tests.
- `docs/data-model.md`, `docs/integration-points.md`; README backend, frontend and "Assumptions to revisit".
- PRD (`docs/prd.md`) and contracts for course spaces, content units, materials, assignments,
  submissions, quizzes, quiz attempts, coursework grades and feedback, discussions, gradebook and
  reports, with endpoints for the assignments-to-grade and course-materials widgets. Published
  events proposed pending consumer confirmation; consumed events pending owner confirmation.
- Module scaffolded.
