# Changelog — timetable-attendance

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Automatic closing of open attendance sessions at their marking deadline (issue #325, FR-11): the scheduler job
  `timetable-attendance.close-expired-sessions` (`application/auto_close.py`), declared on the `eos.scheduler_jobs` entry
  point (organisation scope, idempotent) and run from `scheduler.job.due`, which the module now consumes for its own job
  only. For the organisation, it closes each open session past its deadline as `closed_by = null`: unmarked eligible
  students become absent, the class becomes completed, and `attendance-session.closed` (with the contract's null
  `closed_by`) and one audit entry with no actor are written in the same transaction as the close, each session in its
  own savepoint so one failure leaves nothing of that session and does not stop the others. It reports the run with the
  new `timetable-attendance.job.finished` event. Idempotent: a session that is not open is never selected, is re-checked
  under its row lock, and a repeated delivery is recorded in `processed_event`. **No default schedule:** the scheduler
  seeds one only for platform jobs and none is invented, so the job runs once an operator schedules it per organisation.
  `classes.close_session` is unchanged (it needs an actor and sets `closed_by` to them). No migration or enablement change;
  `module.yaml` lists `scheduler` and `scheduler.job.due`, and `contracts/events.yaml` adds `job.finished`.
- Publish and unpublish (issue #325): `POST /timetables/{id}/publish` and `/unpublish`, key `timetable:publish`. Publishing
  takes a draft or unpublished timetable to `published` and raises its version by one; it is refused with 409 when the
  timetable is already published, when a blocking conflict remains (the response lists them in `details.conflicts`,
  including conflicts with the other published timetables of the period), or when its academic period is not a known
  term (`unknown_term`, from the `term_ref` the `term.created` consumer fills). Unpublishing takes a published
  timetable to `unpublished`, keeps the version, and cancels the timetable's future scheduled classes that have no
  attendance session, each with its own audit entry and `scheduled-class.cancelled` event, and records the optional
  `reason`. Both publish `timetable.published` / `timetable.unpublished` and write an audit entry in the same
  transaction. **Limit, by decision:** publishing does not generate classes yet, so the contract's "generates
  scheduled classes" is not met and `scheduled_class_count` is 0; `POST /timetables/{id}/generate-classes` is not
  served either, because turning a slot's wall-clock times into instants needs the organisation's time zone and no
  source for it exists (`docs/reviewer-decisions.md`, section 10). The tests that unpublish classes seed them
  directly, and the slots use assignment rows written directly, because the faculty-assignment consumer is not built.
  No migration, contract or enablement change.
- Event consumers (issue #325, part 3), registered under `eos.event_consumers` and listed in `module.yaml`:
  academic-management `term.created` into the new `term_ref` (a term's dates), `offering.created` and
  `offering.status-changed` into `offering_ref`, `section.created` and `section.updated` into `section_ref`. Migration
  `tt_0002` adds `term_ref` and `processed_event` (both with `organisation_id` and the forced `tenant_isolation`
  policy), makes the creation-only columns and `status` of `offering_ref` and `section_ref` nullable and adds
  `status_as_of`, because an event can arrive before its creation. Idempotent on the envelope id; a status is replaced
  only by an event that occurred at or after the one that set it; an event is applied only in its own organisation; a
  malformed payload or an envelope version other than 1 is refused. Slot validation now treats an offering or section
  as known only once its creation event has arrived. Not consumed: `faculty-assignment.*` (the `faculty_id` against
  `instructor_id` mapping is unconfirmed), `enrolment-registration.*` (the `student_id` mapping is unconfirmed),
  `offering.updated` and `course.*` (their payloads carry no new values). `docs/reviewer-decisions.md` records the
  decisions confirmed in the PR #459 review, what stays open, and the consumers' unreviewed design choices.
- Scheduled classes, attendance and reports (issue #325): `api/classes_attendance.py` serves the 22 remaining operations
  except `generate-classes`: list, create (ad hoc), get, reschedule and cancel classes; get and open a class's attendance
  session; get and close a session; list and mark its records; correct a record and read its history; the student
  summary and history, department and exam-eligibility reports; and `/me/teaching-schedule`, `/me/attendance-to-mark`,
  `/me/schedule`, `/me/attendance-summary`, `/me/attendance-history` for the widgets. Each state change audits and
  publishes its event in one transaction. Contract 0.2.0, additive for clients that read it: session status
  `cancelled` (reviewer decision A3: cancelling a class with an open session cancels the session instead of closing
  it), nullable `percentage`, `overall_percentage` and `average_percentage` (reviewer decision A1), 404
  `active_term_not_found` on the summaries and the department report (as academic-management answers its term-scoped
  reads), 403 `department_unknown` described on the department report, and 422 on rescheduling to an unknown or
  mismatched instructor assignment. The domain gains `plan_cancel_session`. No migration: the tables existed. Not
  built: automatic closing at the deadline (FR-11, needs a scheduler job) and class generation (time zone). Choices
  are listed in `docs/reviewer-decisions.md` section D.
- Section membership from enrolment-registration (issue #325, answers PRD Q2 from its published contract): consumers of
  `course-registration.confirmed`, `course-registration.withdrawn` and `section-allocation.changed`, registered with the
  others and listed in `module.yaml`. Each event adds a fact to the new `registration_ref` (migration `tt_0003`, with
  `organisation_id` and the forced `tenant_isolation` policy, and `section_member.registration_id`), and the
  registration's `section_member` rows are rebuilt from those facts: in the confirmed section from the date of
  `confirmed_at`, moved the day before `effective_on`, ended on the date of `withdrawn_at`. Idempotent on the envelope
  id, order-independent, a repeated fact changes nothing, the latest name wins by `occurred_at`, and an event is applied
  only in its own organisation. `person_id` is stored as `student_id`. Opening an attendance session now snapshots
  real students.
- Dashboard widgets (issue #325), exported from `frontend/src/widgets/index.ts` and enabled in
  `apps/frontend/config/modules.enabled.yaml`: `today` ("Today's classes", student layouts, `GET /me/schedule`),
  `attendance-summary` ("My attendance", student layouts, `GET /me/attendance-summary`), `today-classes` ("Teaching
  today", faculty layouts, `GET /me/teaching-schedule`), `attendance-to-mark` ("Attendance to mark", faculty layouts,
  `GET /me/attendance-to-mark`) and `department-attendance` ("Department attendance", department-admin,
  `GET /reports/department-attendance`). Each has loading, empty, not-available, no-access and retry states and a
  vitest suite (`frontend/tests`). The day widgets pass the viewer's own date. No active term (404
  `active_term_not_found`) is the empty state, and `department_unknown` (PRD Q9) is explained in words. The dashboard
  journeys in `tests/e2e/dashboards` name each widget's title, probe, empty and unavailable text.
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
