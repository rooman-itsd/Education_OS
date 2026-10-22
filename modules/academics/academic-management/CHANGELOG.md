# Changelog — academic-management

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Contract 0.2.1: every permission-checked operation in `contracts/openapi.yaml` now declares the shared
  `403` (`components.responses.Forbidden`, body `ErrorResponse`); 32 operations had left it out.
- Faculty load rule: teaching-assistant assignments do not count; rows ordered over-load first; summary counts.
- Application layer: permission check, contract error mapping and the faculty-load report use case;
  `ACADEMIC_MANAGEMENT_MAX_WEEKLY_CONTACT_HOURS` read from the environment.
- Faculty-load report: invalid stored rows, settings or faculty names are server faults, not a 400 the contract
  does not declare for `GET /faculty-load`; a bad `ACADEMIC_MANAGEMENT_MAX_WEEKLY_CONTACT_HOURS` is a configuration
  error. Tests check the report's value types and error bodies against `contracts/openapi.yaml`.
- Domain rules for terms, programmes, curricula, courses, offerings, faculty assignments and faculty load.
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
