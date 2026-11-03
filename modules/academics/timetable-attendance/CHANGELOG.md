# Changelog — timetable-attendance

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Timetable API (issue #325, part 2): `GET`/`POST /timetables`, `GET`/`PATCH /timetables/{id}`,
  `PUT /timetables/{id}/slots` and `GET /timetables/{id}/conflicts`, as the contract declares them. Request bodies are
  checked by the use cases, so a malformed body is the contract's 400 with a code and the offending field. Slots are
  replaced as a list (the contract has no per-slot routes); a slot identical to an existing one keeps its id. Slot
  ids must exist in the local read models, agree with each other and belong to the timetable's academic period, else
  422; until the consumers fill the read models (PRD Q1, Q2) only timetables without slots can be saved. Every change
  writes an audit entry and publishes `timetable.created` / `timetable.updated` in the same transaction, and a failure
  at any step rolls all of it back. Settings `TIMETABLE_ATTENDANCE_*` are read by `infrastructure/config.py`. Not
  here: publishing, class generation, scheduled classes, attendance, reports, widgets.
- Backend foundations (issue #325, part 1): domain rules for timetables and slots, conflict detection (section and
  instructor block publishing, a shared location is a warning), scheduled-class generation, rescheduling and
  cancelling, attendance sessions, marking, closing and correction, and attendance percentages (excused classes
  leave the denominator). Persistence: module-prefixed tables with `organisation_id` on every one, the
  read-model tables of PRD section 8 (`offering_ref`, `section_ref`, `assignment_ref`, `section_member`; not
  written until their events are wired, PRD Q1 and Q2) and `timetable_attendance_audit_entry`, an interim audit
  table shaped like platform/audit's `Record` until the audit SDK ships. Own Alembic chain (`tt_0001`, version
  table `timetable_attendance_alembic_version`) with the forced `tenant_isolation` policy on every table.
  `instructor_assignment_ref` is `assignment_ref` and `attendance_record_change` is `record_change`, so generated
  index names stay inside PostgreSQL's 63 characters. Dropped the phantom `eos-sdk` dependency, which does not
  exist, so a real install works. No API, application layer or widgets yet.
- Bulk attendance read for exam eligibility, `POST /reports/attendance-eligibility` (FR-18,
  owner decision C7, PR #183): counts per student up to a cut-off, excused classes excluded from
  the denominator, no threshold. New key `report:read-eligibility` and role for examination-staff.
  Examinations no longer listed as a consumer of attendance events. Q6 and Q7 decided.
- PRD (`docs/prd.md`) and contracts for timetables, scheduled classes, attendance sessions,
  attendance records and attendance reports, with endpoints for the today-classes,
  attendance-to-mark, today, attendance-summary and department-attendance widgets. Published
  events proposed pending consumer confirmation; consumed events pending owner confirmation.
- Module scaffolded.
