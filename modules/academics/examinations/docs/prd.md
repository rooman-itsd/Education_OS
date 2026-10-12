# examinations: product requirements

**Owner:** Shivani (@shivanisinghrooman-09) · **Tier:** common · **Status:** contracts in review (issue #63)

## 1. Objective

examinations runs the examination lifecycle of an organisation, from setting up an exam cycle
to publishing and revising results. It answers four questions:

- What is examined, when, and under which rules? (exam cycles, assessment and grading schemes, papers, sessions)
- Who may sit each paper? (candidates, eligibility, hall tickets)
- Who invigilates and evaluates? (exam duties)
- What did each student score, and is it final? (mark entry, moderation, results)

It serves six dashboard widgets across the Examination Staff, Faculty, Student and Department
Admin dashboards.

## 2. Scope

examinations owns exactly these resources:

| Resource | Meaning |
|---|---|
| **Exam Cycle** | One examination round within an academic period, for example the end-term exams of a semester |
| **Assessment Scheme** | For one course offering: the evaluation components, their weightage, maximum marks and pass requirements |
| **Grading Scheme** | Organisation-level grade bands: percentage range → grade, grade point, pass or fail |
| **Exam Paper** | One assessment component of one course offering, examined in one exam cycle |
| **Exam Session** | One scheduled sitting (date, time, venue label) in which one or more papers are written |
| **Candidate** | One student's candidacy for one exam paper, with eligibility status and reasons |
| **Hall Ticket** | The admission document for one student in one exam cycle: issued, withheld or revoked |
| **Exam Duty** | An invigilation, evaluation or moderation duty assigned to a staff member |
| **Mark Entry** | One candidate's marks for one exam paper, through entry, moderation and locking |
| **Result** | One student's result for one course offering in one exam cycle (marks, grade, pass or fail), plus the student's grade point average for the cycle |
| **Exam Reports** | Derived, read-only views: schedule, hall-ticket counts, results pipeline, results summary |

## 3. Out of scope

examinations references these by ID only. It keeps no foreign key to another module's tables and
imports no code from another module.

| Not here | Owner |
|---|---|
| Person and student identity, staff, org units (departments) | `platform/identity` |
| Student master record and status | `student-lifecycle/student-information` |
| Programme enrolment, course and semester registration (the source of truth for who is registered) | `student-lifecycle/enrolment-registration` |
| Academic period, programme, curriculum, course, course offering, section, instructor assignment | `academics/academic-management` |
| Timetable, scheduled classes, attendance capture, attendance percentages | `academics/timetable-attendance` |
| Coursework grading (LMS assignments, quizzes) | `academics/lms` |
| Sports and music skill assessments (for example a music academy's "Grade exam") | `practice/skill-progress` |
| Sports tournament results | `sports/tournament-events` |
| Examination fees, invoices, payments | `finance-operations/fees-accounts` |
| Exam halls and room booking | `facilities/facility-booking` (see Q3) |
| Storage of hall-ticket and other files | `platform/documents`, through `packages/sdk` |
| Sending records to NAD, DigiLocker and government portals | `integrations/nad`, `integrations/digilocker`, `integrations/government-portals` |
| Cross-module analytics (for example `reporting.attendance-and-results-by-department`) | `platform/reporting` |
| Seat allocation, question papers, revaluation requests, transcripts | Not in week 1; transcript ownership is open (Q7) |

## 4. Actors and responsibilities

Profile role ids are from `platform/identity/config/profiles/*.yaml`.

| Actor (profile role) | Responsibilities here |
|---|---|
| Examination staff / controller (`examination-staff`, `org-admin`) | Sets up exam cycles, grading schemes and papers; schedules sessions; runs eligibility; issues, withholds and revokes hall tickets; assigns duties; locks marks; computes, approves and publishes results; revises results |
| Department Admin / HoD (`department-admin`) | Sets assessment schemes for the department's course offerings; moderates and approves the department's results; reads department reports |
| Faculty / Instructor (`faculty`) | Sees their duties; enters marks for papers they evaluate; moderates papers they are assigned to moderate |
| Student (`student`) | Sees their upcoming exam sessions and hall-ticket status; sees their published results |
| Viewer (for example governance or IQAC roles) | Read-only access to exam setup and organisation-wide reports |

Teacher-education roles inherit from these: `mentor-teacher` extends `faculty`, and
`teacher-trainee` extends `student`.

## 5. Core resources

### 5.1 Exam Cycle
- Belongs to one `academic_period_id`.
- Has a `cycle_type`: `internal`, `mid_term`, `end_term` or `supplementary`. How supplementary candidates are registered is Q1.
- Carries the eligibility rules for the cycle:
  - `eligibility_cutoff_date`
  - `min_attendance_percent` (optional)
  - `check_dues` (whether dues are checked; see Q4)
- Uses one grading scheme.

### 5.2 Assessment Scheme
- One `active` scheme per `course_offering_id`; earlier versions are kept.
- Each component has `code`, `name`, `kind` (`written`, `practical`, `oral`, `project`, `continuous`), `weightage_percent`, `max_marks` and an optional `pass_marks`.
- The scheme has an overall `pass_percent`.
- Weightages add up to 100.

### 5.3 Grading Scheme
- Bands of `min_percent`, `max_percent`, `grade`, `grade_point` and `is_pass`.
- Bands cover 0 to 100 with no gaps or overlaps.
- One organisation default; a cycle may name another.

### 5.4 Exam Paper
- One assessment-scheme component of one course offering in one exam cycle.
- Has `max_marks` (taken from the component) and `duration_minutes`.
- Its status follows the marks pipeline: `draft → scheduled → marks_entry → moderation → locked`.

### 5.5 Exam Session
- Has `starts_at`, `ends_at`, the papers written in it, `venue_label` (free text, see Q3) and `invigilators_required`.
- Status: `scheduled`, `cancelled` or `completed`.

### 5.6 Candidate
- One per (exam paper, student).
- Carries `student_id`, `course_offering_id`, `exam_cycle_id`, `exam_paper_id`, `eligibility_status` (`pending`, `eligible` or `ineligible`) and `eligibility_reasons`.
- Each reason has a `code`:
  - `not_registered`
  - `student_status`
  - `attendance_shortage`
  - `dues_outstanding`
  - `exam_rule`
  - `manual_override`
- Each reason also has a detail.
- A manual override keeps who made it and why.

### 5.7 Hall Ticket
- One per (exam cycle, student). Lists the papers the student is eligible for.
- Status: `issued`, `withheld` or `revoked`.
- The issued file is stored in `platform/documents`; examinations keeps only its `document_id`.

### 5.8 Exam Duty
- Has `staff_id` (an identity user id), `duty_type` (`invigilation`, `evaluation` or `moderation`), and the session (invigilation) or paper (evaluation, moderation) it covers.
- Status: `assigned`, `cancelled` or `completed`.

### 5.9 Mark Entry
- One per candidate. Has `marks_obtained` or `absent`, `entered_by` and `entered_at`.
- An optional moderation adjustment, with reason and moderator.
- Status: `entered`, `moderated` or `locked`.

### 5.10 Result
- One per (exam cycle, student, course offering).
- Has component marks, `weighted_percent`, `grade`, `grade_point` and `passed`.
- The student's cycle summary has the `grade_point_average`, weighted by the course offering credits cached from academic-management (consumed events pending, section 12).
- Status: `computed → approved → published`. A published result can be revised, which creates a new `version` with a reason.

## 6. Examination lifecycle

```
exam cycle:  draft → scheduled → in_progress → evaluation → results_published → closed
paper:       draft → scheduled → marks_entry → moderation → locked
result:      computed → approved → published → (revised → published)
```

| Cycle status | Entered when | What happens |
|---|---|---|
| `draft` | Created | Papers, assessment schemes and grading scheme are prepared |
| `scheduled` | Controller schedules it | Sessions are published; eligibility is determined and hall tickets issued |
| `in_progress` | First session starts | Sessions are held; invigilation duties are carried out. When a session's end time passes, the system marks it `completed` and moves its papers to `marks_entry` |
| `evaluation` | Controller moves it after the last session | Marks are entered, moderated and locked |
| `results_published` | Results are published | Students see results; revisions are still possible |
| `closed` | Controller closes it | No further changes except result revision (FR-17) |

## 7. Dashboard and widget requirements

The widget ids come from the role layouts in `platform/identity/config/dashboards/` and issue #102.
This PR does not change those layouts.

| Widget id | Dashboard (builder) | Data required | Endpoint | Permission |
|---|---|---|---|---|
| `examinations.schedule` | Examination Staff (Akshata) | Upcoming sessions: date and time, papers (course code and title), venue, candidate count, invigilators assigned and required | `GET /sessions?date_from=` | `examinations:session:read` |
| `examinations.hall-tickets-issued` | Examination Staff (Akshata) | Per exam cycle: eligible, issued, withheld and revoked counts; withheld reasons | `GET /reports/hall-tickets?exam_cycle_id=` | `examinations:hall-ticket:read-all` |
| `examinations.results-pending` | Examination Staff (Akshata) | Papers by pipeline stage (marks entry, moderation, lock, approval, publication), with counts and the oldest pending | `GET /reports/results-pending?exam_cycle_id=` | `examinations:report:read-all` |
| `examinations.exam-duties` | Faculty (Shivani) | The caller's upcoming duties: type, session time or paper, venue, status | `GET /me/duties` | `examinations:duty:read-own` |
| `examinations.upcoming-assessments` | Student (Tejaswini) | The caller's upcoming exam sessions: paper, date and time, venue, eligibility, hall-ticket status. Exams only, pending Q6 | `GET /me/exam-schedule` | `examinations:session:read-own` |
| `examinations.results-summary` | Department Admin (Himanshu) | For a department and exam cycle: per course offering, the candidate count, pass rate and grade distribution, for published results | `GET /reports/results-summary?exam_cycle_id=&department_id=` | `examinations:report:read-department`; `examinations:report:read-all` widens it to the organisation |

The Examination Staff dashboard's fourth widget, `enrolment-registration.registered-candidates`,
belongs to enrolment-registration and is not served here.

## 8. Functional requirements

**FR-1 Exam cycle creation and configuration.**
- The controller creates an exam cycle for an academic period with code, name, `cycle_type`, dates, grading scheme and eligibility rules.
- Configuration can change while the cycle is `draft` or `scheduled`.
- Status changes follow section 6. Creating and closing a cycle publish events.

**FR-2 Assessment scheme configuration.**
- A department head (for the department's course offerings) or the controller (any) defines the scheme for a course offering.
- Weightages must add up to 100.
- Activating a scheme supersedes the previous active one. A scheme used by a paper that has locked marks cannot change; a new version is needed.

**FR-3 Grading scheme configuration.**
- The controller defines grading schemes. The bands must cover 0 to 100 without gaps or overlaps.
- One scheme is the organisation default.
- A scheme in use by a cycle with published results cannot change; a new scheme is needed.

**FR-4 Paper creation.**
- The controller creates papers for a cycle from the active assessment scheme of a course offering, one per examined component.
- The course offering must exist in the local read model, which is filled by consumed events (pending, section 12).

**FR-5 Session scheduling.**
- The controller schedules a session with start and end time, the papers written in it, a venue label and the number of invigilators required.
- A session must fall within the cycle dates.
- Two sessions may not share a paper.
- A student may not be a candidate in two overlapping sessions; this is reported as a conflict on scheduling.

**FR-6 Session rescheduling and cancellation.**
- A `scheduled` session can be rescheduled (time or venue) or cancelled with a reason.
- Cancelling a session returns its papers to `draft` so that they can be rescheduled.
- Every change publishes an event so that candidates and duty holders can be notified.

**FR-7 Candidate eligibility determination.**
- **Who becomes a candidate.** Running eligibility for a cycle (or some papers of it) creates one candidate per registered student per paper. Registration comes from enrolment-registration (Q1).
- **Inputs, in this order, each adding a reason when it fails:**
  1. Registration in the course offering (enrolment-registration, Q1)
  2. Student status (student-information, Q2)
  3. Attendance at least `min_attendance_percent` up to `eligibility_cutoff_date`, from timetable-attendance's bulk attendance read (owner decision C7); excused classes are excluded from the denominator. Where the minimum lives is still Q5
  4. Dues, when `check_dues` is set (fees-accounts, Q4)
  5. The cycle's own examination rules
- **Missing inputs.** An input whose source is not available yet (the integration is unconfirmed) leaves the candidate `pending` with no reason recorded for that input. It never silently counts as eligible.
- **Manual override.** The controller may override a candidate's status with a mandatory reason.
- **Event.** The result publishes `candidate.eligibility-determined` per student.

**FR-8 Hall-ticket issuance, withholding and revocation.**
- **Issuing.** The controller issues hall tickets for a cycle, in bulk or for named students. A ticket is issued to a student with at least one eligible paper and lists only the eligible papers. The file is stored through `platform/documents`.
- **Withholding.** A ticket can be withheld with a reason (for example pending dues) and issued again later.
- **Revoking.** A ticket can be revoked with a reason. This is final; issuing again creates a new ticket.
- Each change publishes an event.

**FR-9 Exam duty assignment.**
- The controller assigns staff (identity user ids) to duties:
  - `invigilation` for a session
  - `evaluation` or `moderation` for a paper
- A staff member cannot hold two invigilation duties in overlapping sessions.
- Duties can be cancelled with a reason. Assigning and cancelling publish events.

**FR-10 Mark entry.**
- An evaluator with an `evaluation` duty for a paper enters marks for its candidates while the paper is in `marks_entry`.
- Marks are between 0 and the paper's `max_marks`, or the candidate is marked `absent`.
- Only `eligible` candidates can have marks.
- Re-entry overwrites while the paper is still in `marks_entry`.

**FR-11 Moderation.**
- When marks entry is complete, the paper moves to `moderation`.
- A moderator applies an adjustment, either per candidate or uniformly to the paper, always with a reason. The moderator is a staff member with a `moderation` duty for the paper, or the department head for the department's papers.
- Moderated marks stay within 0 and `max_marks`. The original marks are kept.

**FR-12 Mark locking.**
- The controller locks a paper's marks after moderation. Locked marks cannot change except through result revision (FR-17).
- A paper with unmarked eligible candidates cannot be locked.

**FR-13 Result computation.**
- When all papers of a course offering in the cycle are locked, results are computed for each candidate:
  - weighted percentage from the assessment scheme
  - pass or fail against component and overall pass requirements
  - grade and grade point from the grading scheme
- The student's grade point average is weighted by course offering credits.
- Recomputing replaces `computed` results only.

**FR-14 Result approval.**
- A department head approves `computed` results for the department's course offerings; the controller can approve any.
- Approval is recorded with approver and time.
- Whether approval should use `platform/workflow` is Q10. Until then it is this module's own state change.

**FR-15 Result publication.**
- The controller publishes approved results for a cycle, all or by course offering.
- Published results become visible to students (`GET /me/results`).
- One `result.published` event is published per student, listing that student's newly published course results.
- When every course offering of the cycle is published, the cycle moves to `results_published`.

**FR-16 Reports.**
- Hall-ticket counts per cycle (`GET /reports/hall-tickets`)
- Results pipeline status (`GET /reports/results-pending`)
- Results summary per department and cycle (`GET /reports/results-summary`)

Reports are computed from this module's own data only.

**FR-17 Result revision.**
- The controller revises a published result with a mandatory reason, for example a moderation error or a later decision.
- Revising creates a new result `version`, keeps the previous one, recomputes the student's grade point average, and publishes `result.revised` with the previous and new values. It does not publish `result.published` again, so consumers handle each change once.
- Revaluation requests by students are not in week 1.

**FR-18 Tenant isolation.**
- Every table has `organisation_id` with row-level security on `app.organisation_id`.
- Every query is scoped, every event carries `organisation_id`, and document and cache keys are prefixed by organisation.
- The cross-tenant leak test from `packages/testing` runs in this module's suite.

**FR-19 Auditability.**
- Every state change writes an immutable record to `platform/audit` through `packages/sdk`, with actor, time, before and after. This covers cycle, scheme, paper, session, eligibility, override, hall ticket, duty, marks entry, moderation, lock, result computation, approval, publication and revision.
- Marks and results are never hard-deleted.

**FR-20 Vocabulary.** This is a common module, so labels come from the profile vocabulary (ADR-0004).
The code and contracts use neutral terms. Profiles may override:

| Key | Default label | Example override |
|---|---|---|
| `examinations.exam-cycle` | Exam cycle | "Examination series", "Assessment round" |
| `examinations.paper` | Paper | "Subject", "Jury" (design), "Recital" |
| `examinations.hall-ticket` | Hall ticket | "Admit card" |

## 9. Data model (summary)

The module has its own schema, `examinations`. Every table has `organisation_id` and an RLS policy on
`app.organisation_id`. Full detail follows in `data-model.md` with the first migration.

| Table | Key columns |
|---|---|
| `exam_cycle` | id, organisation_id, academic_period_id, code, name, cycle_type, starts_on, ends_on, grading_scheme_id, eligibility_cutoff_date, min_attendance_percent, check_dues, status |
| `assessment_scheme` | id, organisation_id, course_offering_id, version, pass_percent, status |
| `assessment_component` | id, organisation_id, assessment_scheme_id, code, name, kind, weightage_percent, max_marks, pass_marks |
| `grading_scheme` | id, organisation_id, name, is_default, status |
| `grading_band` | id, organisation_id, grading_scheme_id, min_percent, max_percent, grade, grade_point, is_pass |
| `exam_paper` | id, organisation_id, exam_cycle_id, course_offering_id, assessment_component_id, max_marks, duration_minutes, status |
| `exam_session` | id, organisation_id, exam_cycle_id, starts_at, ends_at, venue_label, invigilators_required, status, cancel_reason |
| `exam_session_paper` | organisation_id, exam_session_id, exam_paper_id (unique) |
| `candidate` | id, organisation_id, exam_cycle_id, exam_paper_id, course_offering_id, student_id, eligibility_status, reasons, override_by, override_reason, determined_at |
| `hall_ticket` | id, organisation_id, exam_cycle_id, student_id, status, document_id, reason, issued_at |
| `exam_duty` | id, organisation_id, exam_cycle_id, staff_id, duty_type, exam_session_id?, exam_paper_id?, status, cancel_reason |
| `mark_entry` | id, organisation_id, candidate_id, marks_obtained, absent, entered_by, entered_at, moderation_delta, moderation_reason, moderated_by, status |
| `result` | id, organisation_id, exam_cycle_id, student_id, course_offering_id, version, weighted_percent, grade, grade_point, passed, status, approved_by, published_at, revision_reason |
| `offering_ref` (read model) | organisation_id, course_offering_id, course_id, academic_period_id, course_code, course_title, credits, department_id. `course_id` is kept so that course changes from academic-management can be applied to every offering of that course (PR #168) |
| `registration_ref` (read model) | organisation_id, student_id, course_offering_id, status (pending Q1) |

Read-model tables are refreshed only from consumed events (section 12). They are local
copies, not foreign keys. `student_id`, `staff_id`, `department_id` and `document_id` are external IDs.

## 10. Cross-module integration

| Needs | From | How | Status |
|---|---|---|---|
| Academic period, course offering (course code, title, credits, department), instructor assignment (to suggest evaluators) | academic-management | Consumed events into `offering_ref` | PENDING CONFIRMATION FROM OWNER (Shivani; names become authoritative when PR #168 merges, owner decision C4) |
| Who is registered for each course offering; supplementary and backlog registration | enrolment-registration | Consumed events into `registration_ref` | PENDING CONFIRMATION FROM OWNER (Praveen; Q1) |
| Student status (active, suspended, discontinued) | student-information | Event or API | PENDING CONFIRMATION FROM OWNER (Praveen; Q2) |
| Attendance counts per student and course offering at the cut-off date | timetable-attendance | `POST /reports/attendance-eligibility` (timetable-attendance FR-18, PR #179), key `timetable-attendance:report:read-eligibility` | Decided by owner decision C7; proposed contract, not yet merged |
| Dues status for examination fees | fees-accounts | Event or API | PENDING CONFIRMATION FROM OWNER (Gokula Lakshmi; Q4) |
| Permission checks, current user, caller's department | platform/identity | `packages/sdk` | Available; department scope pending Q13 |
| Audit trail | platform/audit | `packages/sdk` | Available |
| Publishing events | platform/event-bus | `packages/sdk` | Available |
| Hall-ticket files | platform/documents | `packages/sdk` | Available |
| Result approval workflow | platform/workflow | Not used until Q10 is decided | Open |

Other modules use examinations only through `contracts/openapi.yaml` and `contracts/events.yaml`.

## 11. Published events

All events are **proposed** for week 1. The payloads are in `contracts/events.yaml`. The envelope is
the one stored by `packages/core` (`eos_core.events.OutboxEvent`): `id`, `name`, `organisation_id`,
`actor`, `occurred_at`, `payload`.

| Event | Proposed consumers |
|---|---|
| `examinations.exam-cycle.created` | reporting |
| `examinations.exam-cycle.closed` | reporting |
| `examinations.exam-session.scheduled` | notification; possibly timetable-attendance and facility-booking (Q3) |
| `examinations.exam-session.rescheduled` | notification; possibly timetable-attendance and facility-booking |
| `examinations.exam-session.cancelled` | notification; possibly timetable-attendance and facility-booking |
| `examinations.candidate.eligibility-determined` | notification, student-information |
| `examinations.hall-ticket.issued` | notification |
| `examinations.hall-ticket.withheld` | notification |
| `examinations.hall-ticket.revoked` | notification |
| `examinations.duty.assigned` | notification; possibly hr-payroll (Q11) |
| `examinations.duty.cancelled` | notification; possibly hr-payroll |
| `examinations.result.published` | enrolment-registration, student-information, reporting, regulatory-reports, nad, digilocker, notification (Q7, Q12) |
| `examinations.result.revised` | the same consumers as `result.published` |

## 12. Consumed events

None are declared in `module.yaml` until the owners confirm the names in their own `events.yaml`.
The names below describe what is needed. They are **not** event names.

| Needed fact | Publisher | Event name |
|---|---|---|
| Academic period created / became active | academic-management (Shivani) | PENDING CONFIRMATION FROM OWNER |
| Course offering created / updated / status changed, with course code, title, credits, department | academic-management (Shivani) | PENDING CONFIRMATION FROM OWNER |
| Instructor assignment created / ended | academic-management (Shivani) | PENDING CONFIRMATION FROM OWNER |
| Student registered for / withdrawn from a course offering; supplementary or backlog registration | enrolment-registration (Praveen) | PENDING CONFIRMATION FROM OWNER |
| Student status changed | student-information (Praveen) | PENDING CONFIRMATION FROM OWNER |
| Examination-fee dues settled or outstanding (only if Q4 chooses events) | fees-accounts (Gokula Lakshmi) | PENDING CONFIRMATION FROM OWNER |

academic-management (PR #168), timetable-attendance (PR #179) and fees-accounts (PR #170) have
draft contracts that propose event names. Those names become authoritative only when the PRs merge.

## 13. Permissions

The keys are in `contracts/permissions.yaml`, in `examinations:<resource>:<action>` form.

Modules check permission keys, never roles (ARCHITECTURE.md, Security). Each scope is its own key, and
a key means the same scope whoever holds it. Where two actors do the same thing at different scopes, the
wider one holds an extra key:

| Action | Department scope (HoD) | Organisation scope (controller) | Own scope |
|---|---|---|---|
| Configure assessment schemes | `assessment-scheme:write-department` | `assessment-scheme:write-all` | — |
| Read candidates | `candidate:read-department` | `candidate:read-all` | — |
| Read duties | `duty:read-department` | `duty:read-all` | `duty:read-own` (faculty) |
| Read marks | `marks:read-department` | `marks:read-all` | `marks:read-assigned` (evaluator, moderator) |
| Enter marks | — | `marks:enter-all` | `marks:enter-assigned` (evaluator) |
| Moderate | `marks:moderate-department` | — | `marks:moderate-assigned` (moderator) |
| Read results | `result:read-department` | `result:read-all` | `result:read-own` (student, published only) |
| Approve results | `result:approve-department` | `result:approve-all` | — |
| Read reports | `report:read-department` | `report:read-all` | — |

**How operations state their permission.** This follows the timetable-attendance contract:

- **`x-permission`** names the single, narrowest key that grants the operation, for example `marks:read-assigned`.
- **The operation's description** names the wider keys of the same action, for example `marks:read-department` and `marks:read-all`.
- **The widest key the caller holds** decides the scope.
- **Roles** therefore hold the narrowest key plus any wider ones. The controller holds `-assigned` and `-department` keys alongside its `-all` keys, and the department head holds the `-assigned` marks keys, which have the same scope (papers the caller holds a duty for) as faculty's.
- **No key is held by faculty and department heads with different meanings.**

Department scope needs the caller's department from `platform/identity`. How identity exposes it is not yet
confirmed (Q13); until then the department-scoped keys are defined but their scope rule is pending.

| Default module role | For profile role |
|---|---|
| `examinations-controller` | `examination-staff`, `org-admin` |
| `examinations-department-head` | `department-admin` |
| `examinations-faculty` | `faculty` |
| `examinations-student` | `student` |
| `examinations-viewer` | read-only roles such as governance |

## 14. Open questions

| # | Question | Who decides |
|---|---|---|
| Q1 | Is candidacy derived entirely from course or semester registration in enrolment-registration? Who registers students for `supplementary` cycles and backlog papers, and what events carry it? | Praveen |
| Q2 | Which identifier `student_id` is (student-information record id or identity user id); where student status and display name come from | Praveen, Faizan |
| Q3 | Exam venues: keep a free-text `venue_label`, or reference facility-booking resources and book them (or create blackouts) when a session is scheduled | Ashritha |
| Q4 | Whether examination-fee dues can withhold eligibility or hall tickets; which fees-accounts event or API reports dues; who raises the examination-fee invoice | Gokula Lakshmi |
| Q5 | **API part decided (owner decision C7):** examinations reads attendance through timetable-attendance's bulk read (FR-18 in PR #179), not events; excused classes are excluded from the denominator. **Still open:** whether the minimum is set per exam cycle here (proposed) or comes from timetable-attendance's shortage threshold | Shivani (timetable-attendance), with Akshata for the Exam Staff view |
| Q6 | Does `examinations.upcoming-assessments` include LMS quizzes and assignments, or exams only? Proposed: exams only | Tejaswini, Shivani (lms) |
| Q7 | Transcripts and certificates: examinations, student-information, or only the NAD and DigiLocker integrations from published results | Praveen, Himanshu, Faizan |
| Q8 | **Decided (owner decision C5, [owner decision record](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6099000605)):** academic-management uses `academic_period_id`, `course_offering_id` and `instructor_assignment_id`, aligned in PR #168 | Shivani |
| Q9 | **Decided for Week 1 (owner decision C9, [owner decision record](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6099000605)):** LMS coursework grades do not feed the `continuous` component; exam marks are entered here. Integration is revisited in a later phase | Shivani |
| Q10 | Should result approval use `platform/workflow` (no module uses it yet) or stay as this module's state machine? | Himanshu, Faizan |
| Q11 | Does duty remuneration involve hr-payroll, and does it consume `duty.*` events? | Gokula Lakshmi |
| Q12 | Which result fields do `platform/reporting` (`reporting.attendance-and-results-by-department`), regulatory-reports, nad and digilocker need in `result.published`? | Himanshu, Madhumita |
| Q13 | How the caller's department is known (identity SDK), and therefore how department-scoped keys are enforced (same as timetable-attendance Q9) | Faizan |

### Review items

| # | Item | Raised with |
|---|---|---|
| CR-1 | **Answered.** Akshata's recorded comment on PR #168 agrees that Assessment Scheme is owned by examinations, not academic-management. Academic-management's PRD wording (sections 3 and 8.3) was updated in PR #168 to match. This PR does not touch academic-management | PR #168 (Shivani) |
| R-1 | Event envelope. ARCHITECTURE.md requires only `organisation_id` in the envelope; the implemented outbox (`packages/core`, `eos_core.events.OutboxEvent`) stores `id`, `name`, `organisation_id`, `actor`, `occurred_at`, `payload`. The scaffold comment in every `contracts/events.yaml` ("id, occurred_at, actor, tenant, version, payload") also lists `version`, which neither the architecture docs nor the outbox define. This contract follows the outbox, and contract versioning stays with the file-level `version` and module semver (module-standard rule 7). The timetable-attendance draft (PR #179) still lists `version`. Should the scaffold comment be corrected, or should `version` be added to the outbox? | Faizan |

## 15. Acceptance criteria (week 1)

- Contracts reviewed by Faizan. Consumers confirm the events in section 11, and owners confirm the names in section 12.
- Every widget in section 7 has its endpoint in `contracts/openapi.yaml` and its permissions in `contracts/permissions.yaml`.
- Every operation in `contracts/openapi.yaml` names its `x-permission`, and every key named exists.
- Every event carries `organisation_id`.
- Q1 to Q13, CR-1 and R-1 are raised with their owners on the PR.
