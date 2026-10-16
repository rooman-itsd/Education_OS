# Changelog — academic-management

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Contract 0.2.0, `GET /faculty-load` (owner decisions on PR #168): `faculty_name` required; the report carries
  `academic_period_code`, `academic_period_name`, `faculty_count` and `over_load_count`; items are ordered over-load
  first, then by contact hours; 404 `active_term_not_found` when no term is given or active; teaching-assistant
  hours are excluded. `RosterEntry.student_id` is now `person_id` (learner identifier confirmed on issue #100).
- Docs: user stories; PRD records the confirmed decisions and the decisions still pending (section 13).
- Identifiers aligned with the shared academics vocabulary (owner decision C5, PR #183):
  `term_id` -> `academic_period_id`, `offering_id` -> `course_offering_id`, faculty-assignment
  `assignment_id` -> `instructor_assignment_id`. Path parameters renamed to match; event names, resource paths, schema names and permission keys unchanged.
- PRD (`docs/prd.md`) and contracts for terms, programmes, curricula, courses, offerings,
  sections, faculty assignment, roster and faculty load. Events proposed, pending consumer
  confirmation.
- Module scaffolded.
