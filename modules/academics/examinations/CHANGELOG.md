# Changelog — examinations

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Exam duty APIs (issue #325): listExamDuties, assignExamDuty, cancelExamDuty and listMyDuties, with an audit entry per
  change and the two contracted events `examinations.duty.assigned` and `.cancelled`. Assigning needs a scheduled
  session or a paper, in a cycle up to `evaluation`; invigilation cannot overlap (back-to-back is fine, a cancelled session
  never counts); a live duplicate is a 409, backed by migration `ex_0003` (two partial unique indexes, assigned and
  completed duties only). `duty:read-all` lists the organisation's duties and `duty:read-department` alone gets none until
  the caller's department is known. `staff_id` is stored without an identity lookup. Recorded in
  `docs/reviewer-decisions.md` section 12.
- Paper and session APIs (issue #325): listExamPapers, createExamPapers, getExamPaper, updateExamPaper, listExamSessions,
  scheduleExamSession, getExamSession, rescheduleExamSession and cancelExamSession, with an audit entry per change and the
  three contracted events `examinations.exam-session.scheduled`, `.rescheduled` and `.cancelled` (papers publish none).
  Scheduling moves the papers to `scheduled`; cancelling returns them to `draft` and frees them, and is allowed while
  the cycle is draft, scheduled or in progress. Migration `ex_0002` adds the nullable `title` of a paper, which
  `updateExamPaper` stores and returns. Not enforced, and recorded in `docs/reviewer-decisions.md` section 11: the
  session-within-cycle rule (no organisation time zone) and candidate clashes.
- Enabled in `apps/backend/config/modules.enabled.yaml` (mounted at `/api/v1/examinations` behind the entitlement gate,
  next to its entry in `apps/frontend/config/modules.enabled.yaml`), so the 15 configuration and exam-cycle operations
  are served and the widgets stop answering 404 for them. Added `test_api_permissions.py`: every route is refused with 403
  for a caller without its key (checked against the roles' real grants) and 401 without a token.
- Configuration and exam-cycle APIs (issue #325): the 15 operations for grading schemes (list, create, get, replace,
  set default), assessment schemes (list, create, get, replace a draft, activate) and exam cycles (list, create, get,
  update, change status), with the router, the use cases, organisation-scoped queries, an audit entry per change and the
  two contracted events (`examinations.exam-cycle.created`, `.closed`); grading- and assessment-scheme changes publish
  none. Fixed `ExaminationsError` failing when a domain error carried a `status` detail (cycle_not_configurable). No
  migration: the foundation schema is unchanged. Contract gaps and deferrals: `docs/reviewer-decisions.md` section 10.
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
