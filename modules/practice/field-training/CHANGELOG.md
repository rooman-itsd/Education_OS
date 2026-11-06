# Changelog — field-training

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contracts proposed (generic pattern): sites, openings, placements by assignment or application, logbook with
  supervisor verification, assessments, completion and withdrawal, and the endpoints behind the widgets
  `field-training.my-placement`, `hours-logged`, `trainees-to-assess`, `placements-open` and
  `active-placements`; events; permissions and generic roles.
- PRD (`docs/prd.md`).
- User stories (`docs/user-stories.md`): sites, openings, placements, logbook, assessments and completion,
  self-service, widgets and the daily job, with the role table from `permissions.yaml`.
- Backend (`eos_field_training`): all 30 operations of contract 0.1.0 in domain, application, infrastructure and api
  layers; events to the outbox in the same transaction; an audit entry for every state change; row locks on the
  opening (seats) and on every placement and log entry that changes status; business dates in Asia/Kolkata; the daily
  job that starts assigned placements on their start date. Ids must be uuids, strings and numbers are bounded, dates
  fall in 1900 to 9998 and NUL characters are refused (422, or 404 in the path), forged cursors start from the top, a
  duplicate written past the check is a 409.
- Migration `field_training_0001`: eight tables, each with `organisation_id` and the forced `tenant_isolation`
  row-level-security policy.
- Tests: domain rules, every user-story area, a 403 for every operation and role without its key, real academy-role
  tokens, the keys each role holds through `permissions_for`, the cross-tenant leak test, refused inputs, the daily
  job, and the migration against the models.
- Widgets `field-training.my-placement`, `hours-logged`, `trainees-to-assess`, `placements-open` and
  `active-placements` on `@eos/ui-kit`, each with one permission and tests for loading, empty, data and every error
  state.
- Review fix (#504): nobody assigns, decides, starts, changes or completes their own placement (403 `own_placement`), so a
  user holding the coordinator and the trainee role cannot approve their own application; such a user cannot withdraw
  their own active placement either (403 `placement_active`, as for any trainee).
- Review fix (#504): an explicit `null` in a request body is a 422 for every field except `AssessmentInput.score`, the only
  one the contract types as nullable. A PATCH with `supervisor_ids: null` used to wipe the supervisors of a site or
  opening; leaving the field out keeps them, and `[]` clears them on purpose.
- Review fix (#504, found by Madhumita): ids are one id whatever their case. The UUID pattern accepted capitals and ids were
  stored and compared as sent, so a coordinator who is also a trainee could assign and start their own placement by
  sending their own id in capitals (201, then 200), and `supervisor_ids` `[x, X]` passed the uniqueness check. Ids in bodies,
  paths and filters, and the token's `sub` and `org`, are now lowercased before use; the guard and every lookup compare
  lowercase ids.
- Enabled in `apps/backend/config/modules.enabled.yaml` (mounted at `/api/v1/field-training`) and
  `apps/frontend/config/modules.enabled.yaml` (its five widgets on the trainee, supervisor and coordinator dashboards)
  (#339).
