# Changelog — skill-progress

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Backend: domain rules (framework and assessment status transitions, proficiency scales, rubric criteria, criterion
  scores against the rubric, overall score and level against the skill's scale, no self-assessment, no future
  assessment times, the progression with level advances and highest-level milestones); use cases for every
  operation in the contract; learners see only their own records; events from `contracts/events.yaml` through the
  outbox; an interim audit table shaped like platform/audit's Record (no feedback, notes, descriptions or evidence).
- Alembic chain `sp_0001`: five `skill_progress_*` tables with `organisation_id`, RLS policy on Postgres.
- Contract: `x-permission` and a 403 response on every operation; `POST /assessments/{id}/verify`
  (`assessment:approve`) and `POST /assessments/{id}/void` (`assessment:delete`), so the `verified` and `voided`
  statuses can be reached; a 400 response on the framework and skill updates (non-breaking).
- Tests: domain, API, learner self-scope, query counts, cross-tenant leak, migration and contract-drift tests.
