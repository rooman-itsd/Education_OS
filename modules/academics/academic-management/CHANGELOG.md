# Changelog — academic-management

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Faculty load rule: teaching-assistant assignments do not count; rows ordered over-load first; summary counts.
- Application layer: permission check, contract error mapping and the faculty-load report use case;
  `ACADEMIC_MANAGEMENT_MAX_WEEKLY_CONTACT_HOURS` read from the environment.
- Domain rules for terms, programmes, curricula, courses, offerings, faculty assignments and faculty load.
- Identifiers aligned with the shared academics vocabulary (owner decision C5, PR #183):
  `term_id` -> `academic_period_id`, `offering_id` -> `course_offering_id`, faculty-assignment
  `assignment_id` -> `instructor_assignment_id`. Path parameters renamed to match; event names, resource paths, schema names and permission keys unchanged.
- PRD (`docs/prd.md`) and contracts for terms, programmes, curricula, courses, offerings,
  sections, faculty assignment, roster and faculty load. Events proposed, pending consumer
  confirmation.
- Module scaffolded.
