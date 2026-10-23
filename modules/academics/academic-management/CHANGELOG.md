# Changelog — academic-management

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- `GET /me/offerings` needs a term: 404 `active_term_not_found` when none is given or active, 404 for an unknown
  one, and `academic_period_id` must be a uuid (contract 0.2.3 declares the 404; the widget shows "no courses").
- Roster consumer: a withdrawal that arrives before its confirmation is recorded only against a section of the
  offering it names, with that section's offering id; a payload missing an agreed field is rejected once
  (`rejected:malformed_payload`) and recorded, never redelivered forever.
- Concurrent creates of a programme's curriculum: the version constraint answers 409 `concurrent_version`.
- `programme_ids` of an offering must be programmes of the organisation: 422 `unknown_programme` naming the item.
- `x-permission-any` on `getRoster` and `listMyOfferings` lists the roster keys the guard accepts; a test compares
  every route's guard with its operation.
- Contract 0.2.2: `GET /faculty-load` declares its 503 `faculty_directory_unavailable` (ErrorResponse), returned
  while no identity lookup of faculty names is available to modules.
- Concurrent creates of one code: the database's code constraint answers 409 `duplicate_code`, like the pre-check;
  other integrity errors are not turned into conflicts.
- Section capacity under concurrent registrations: the roster consumer locks the section row (SELECT ... FOR UPDATE)
  before counting and re-counts after writing in the same transaction, so a section never exceeds its capacity.
- Persistence: tables `academic_management_*` on TenantMixin with the shared RLS policy, own Alembic chain
  (`am_0001`), organisation-scoped repository; migration and cross-tenant leak tests.
- API: every operation of `contracts/openapi.yaml`, guarded by its permission key; events of
  `contracts/events.yaml` published through `eos_core.events.publish` in the same transaction.
- Roster read model from enrolment-registration's agreed events, upserted by `registration_id`, applied once per
  envelope id; withdrawals kept as withdrawn; closed or full sections and offerings that are not open take no
  new registrations.
- Contracts: permission role blocks are the platform role ids; event payloads no longer repeat `organisation_id`,
  each event declares `version: 1`, and the curriculum payload's `version` is now `curriculum_version`.
- Frontend: `academic-management.course-roster` widget with tests; the module is enabled in `apps/frontend`.
- Docs: data model; PRD and user stories record what is built and the shared work still outstanding.
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
