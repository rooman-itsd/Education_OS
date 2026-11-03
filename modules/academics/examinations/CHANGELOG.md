# Changelog — examinations

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Backend foundation (issue #325): domain rules for exam cycles (the lifecycle of PRD section 6), grading and assessment
  schemes (weightages add up to 100 on activation, activating supersedes the previous active scheme), papers (one per
  component and cycle, marks pipeline), sessions (within the cycle's dates, a paper in one session, reschedule and cancel)
  and duties (a session or a paper, no overlapping invigilation). Persistence: 11 `examinations_` tables with
  `organisation_id` on every one, `ex_0001` with the forced `tenant_isolation` policy, organisation-scoped repository,
  the 43 permission keys and token authentication guard. The database holds one default grading scheme per organisation,
  one active assessment scheme per offering, one paper per component and cycle, a paper in one session, and the duty
  target rule. No routes, candidates, hall tickets, marks, results or consumers yet; they wait on the decisions in
  `docs/reviewer-decisions.md`. Dropped the phantom `eos-sdk` dependency so a real install works.
- Examination Staff dashboard widgets (frontend): examinations.schedule, examinations.hall-tickets-issued, examinations.results-pending.
- PRD: attendance for eligibility comes from timetable-attendance's bulk read (owner decision C7,
  PR #183); the attendance-event consumption row is removed. Where the minimum lives stays open (Q5).
- PRD (`docs/prd.md`) and contracts for exam cycles, assessment and grading schemes, papers,
  sessions, candidates and eligibility, hall tickets, exam duties, mark entry, moderation,
  results and examination reports, with endpoints for the schedule, hall-tickets-issued,
  results-pending, exam-duties, upcoming-assessments and results-summary widgets. Published
  events proposed pending consumer confirmation; consumed events pending owner confirmation.
- Module scaffolded.
