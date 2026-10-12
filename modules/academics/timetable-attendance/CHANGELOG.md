# Changelog — timetable-attendance

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Bulk attendance read for exam eligibility, `POST /reports/attendance-eligibility` (FR-18,
  owner decision C7, PR #183): counts per student up to a cut-off, excused classes excluded from
  the denominator, no threshold. New key `report:read-eligibility` and role for examination-staff.
  Examinations no longer listed as a consumer of attendance events. Q6 and Q7 decided.
- PRD (`docs/prd.md`) and contracts for timetables, scheduled classes, attendance sessions,
  attendance records and attendance reports, with endpoints for the today-classes,
  attendance-to-mark, today, attendance-summary and department-attendance widgets. Published
  events proposed pending consumer confirmation; consumed events pending owner confirmation.
- Module scaffolded.
