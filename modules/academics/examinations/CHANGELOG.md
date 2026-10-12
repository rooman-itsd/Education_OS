# Changelog — examinations

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- PRD: attendance for eligibility comes from timetable-attendance's bulk read (owner decision C7,
  PR #183); the attendance-event consumption row is removed. Where the minimum lives stays open (Q5).
- PRD (`docs/prd.md`) and contracts for exam cycles, assessment and grading schemes, papers,
  sessions, candidates and eligibility, hall tickets, exam duties, mark entry, moderation,
  results and examination reports, with endpoints for the schedule, hall-tickets-issued,
  results-pending, exam-duties, upcoming-assessments and results-summary widgets. Published
  events proposed pending consumer confirmation; consumed events pending owner confirmation.
- Module scaffolded.
