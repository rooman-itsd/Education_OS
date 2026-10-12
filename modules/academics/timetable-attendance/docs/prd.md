# timetable-attendance: product requirements

**Owner:** Shivani (@shivanisinghrooman-09) · **Tier:** common · **Status:** contracts in review (issue #63)

## 1. Objective

timetable-attendance turns the academic catalogue into a weekly timetable and actual class
occurrences, and records who attended each one. It answers three questions for every
organisation:

- When and where does each section meet, and who teaches it? (timetable, scheduled classes)
- Who was present at each class? (attendance sessions and records)
- How is attendance trending per student, course offering and department? (reports)

It serves five dashboard widgets across the Faculty, Student and Department Admin dashboards.

## 2. Scope

The module owns exactly these five resources:

| Resource | Meaning |
|---|---|
| **Timetable** | The planned recurring weekly schedule of classes for an academic period, made of slots (day, time, course offering, section, instructor assignment, location) |
| **Scheduled Class** | One actual class occurrence on a date, generated from a timetable slot or created ad hoc (extra class) |
| **Attendance Session** | The attendance-taking session for one scheduled class: opened, marked, closed |
| **Attendance Record** | One student's attendance status in one attendance session, with its correction history |
| **Attendance Reports** | Derived, read-only views over attendance records: per student, per course offering or section, per department |

## 3. Out of scope

timetable-attendance references these by ID only. It keeps no foreign key to another module's
tables and imports no code from another module.

| Not here | Owner |
|---|---|
| Academic period, programme, curriculum, course, course offering, section, instructor assignment | `academics/academic-management` |
| Person identity, users, org units (departments) | `platform/identity` |
| Student records | `student-lifecycle/student-information` |
| Student enrolment and student-section allocation | `student-lifecycle/enrolment-registration` |
| Examinations, results, exam eligibility decisions | `academics/examinations` |
| LMS content, assignments, course materials | `academics/lms` |
| Rooms and room booking | `facilities/facility-booking` (see open question Q4) |
| Notifications to students or guardians | `platform/notification`, through `packages/sdk` |

## 4. Actors and responsibilities

Profile role ids are from `platform/identity/config/profiles/*.yaml`.

| Actor (profile role) | Responsibilities here |
|---|---|
| Academic / timetable admin (`org-admin`) | Builds and publishes timetables for any department, generates scheduled classes, can open, close, mark and correct attendance for any class |
| Department Admin / HoD (`department-admin`) | Builds and publishes timetables for the department, reschedules or cancels classes, corrects attendance for department classes, reads department reports (department scope pending Q9) |
| Faculty / Instructor (`faculty`) | Sees their classes, opens and closes attendance sessions, marks and corrects attendance for classes they teach |
| Student (`student`) | Sees their own schedule and their own attendance summary and history |
| Viewer (for example governance or IQAC roles) | Read-only access to timetables, classes and organisation-wide reports |

Teacher-education roles inherit from these: `mentor-teacher` extends `faculty`, and
`teacher-trainee` extends `student`.

## 5. Core resources

### 5.1 Timetable
Belongs to one academic period and, optionally, one department. It has a `version` and a status:
`draft → published → unpublished`. An unpublished timetable can be edited and published again
as a new version. Its **slots** are part of the timetable, not a separate resource. Each slot has:
- `day_of_week`, `start_time`, `end_time`
- `course_offering_id`, `section_id`, `instructor_assignment_id`
- optional `location_label`
- optional `effective_from` / `effective_to` within the academic period

### 5.2 Scheduled Class
A dated occurrence:
- `class_date`, `starts_at`, `ends_at`, `location_label`
- status `scheduled | cancelled | completed`
- the slot it came from, or `null` for an ad-hoc class
- a copy of the academic-management IDs it references

A rescheduled class keeps its ID, and its old time is kept in the audit trail.

### 5.3 Attendance Session
At most one per scheduled class:
- status `open | closed`
- `opened_at` / `opened_by`
- `closed_at` / `closed_by`
- the marking deadline
- counts by status

### 5.4 Attendance Record
One per (attendance session, student):
- status `present | absent | late | excused`
- optional remark, `marked_by`, `marked_at`

Every correction keeps the previous value, who changed it, when, and a mandatory reason.

### 5.5 Attendance Reports
These are computed from attendance records, never entered by hand:
- **Student:** attendance percentage per course offering, and history
- **Department:** attendance percentage per course offering and section, plus the number of students below the shortage threshold

## 6. Dashboard requirements

The widget ids come from the role layouts in `platform/identity/config/dashboards/`; this PR does not change those layouts.
Each widget fetches through the endpoint named here and declares the permission it needs.

| Widget id | Dashboard (builder) | Shows | Endpoint | Permission |
|---|---|---|---|---|
| `timetable-attendance.today-classes` | Faculty (Shivani) | The caller's classes today, with attendance session state | `GET /me/teaching-schedule?date=` | `timetable-attendance:scheduled-class:read` |
| `timetable-attendance.attendance-to-mark` | Faculty (Shivani) | The caller's past or current classes whose attendance is not yet closed and still within the marking window | `GET /me/attendance-to-mark` | `timetable-attendance:attendance-record:mark` |
| `timetable-attendance.today` | Student (Tejaswini) | The caller's classes today | `GET /me/schedule?date=` | `timetable-attendance:scheduled-class:read-own` |
| `timetable-attendance.attendance-summary` | Student (Tejaswini) | The caller's attendance percentage per course offering, with shortage flags | `GET /me/attendance-summary` | `timetable-attendance:report:read-own` |
| `timetable-attendance.department-attendance` | Department Admin (Himanshu) | Department attendance per course offering and section; students below threshold | `GET /reports/department-attendance` | `timetable-attendance:report:read-department` |

The dancer layout (`dancer.yaml`) also uses `timetable-attendance.today`, so that widget must
not assume an academic field. Labels come from the vocabulary in section 7.17.

## 7. Functional requirements

**FR-1 Timetable creation.** An admin or HoD creates a draft timetable for an academic period,
optionally limited to one department, with zero or more slots.

**FR-2 Timetable update.** Slots of a `draft` or `unpublished` timetable can be added, changed
or removed. A `published` timetable cannot be edited; unpublish it first.

**FR-3 Timetable publication.** Publishing runs the conflict check (FR-4) and fails if there are
blocking conflicts. On success it sets status `published`, increments `version`, and generates
scheduled classes (FR-5). Unpublishing stops future generation and cancels future scheduled
classes that have no attendance session. Past classes and recorded attendance are never touched.

**FR-4 Timetable conflict detection.** Two slots conflict when their times overlap on the same
day within overlapping effective dates and they share:
- a `section_id` (a section cannot be in two classes at once);
- an instructor (the `instructor_id` held by their instructor assignments);
- a `location_label` (a warning only, until room ownership is settled; see Q4).

Conflicts are checked within the timetable and against every other published timetable in the
same academic period. `GET /timetables/{id}/conflicts` lists them without publishing.

**FR-5 Scheduled class generation.** For each slot, one scheduled class is generated for every
matching weekday between the slot's effective dates. Generation is idempotent (one class per
slot and date). Admins and HoDs can also create an ad-hoc class with no slot, and can reschedule
or cancel any class that has no closed attendance session.

**FR-6 Today's classes.**
- A faculty member sees the classes they teach on a date, defaulting to today in the organisation's time zone, with each class's attendance session state.
- A student sees the classes of the sections they are allocated to.

**FR-7 Attendance eligibility.**
- **Who can be marked.** The students allocated to the class's section on the class date, from the section-allocation read model (section 9). A student allocated after the class date is not eligible for it. This depends on the allocation events carrying an effective date (pending Q2).
- **When attendance can be marked.** The class is `scheduled` (not cancelled), and the current time is between `starts_at` minus `TIMETABLE_ATTENDANCE_MARKING_OPENS_BEFORE_MINUTES` and `ends_at` plus `TIMETABLE_ATTENDANCE_MARKING_WINDOW_HOURS`.
- **Who can mark.** The class's instructor, or a holder of `timetable-attendance:attendance-session:override`.

**FR-8 Opening an attendance session.** Opening creates the session for a scheduled class if the
FR-7 rules hold. It snapshots the eligible students as unmarked. Opening twice returns the
existing open session. Publishes `attendance-session.opened`.

**FR-9 Attendance capture.**
- The instructor submits statuses for some or all eligible students in one request; a "mark all present" default is a client concern.
- Only eligible students can be marked.
- A submission while the session is open creates or overwrites records, with no reason needed.
- One `attendance-record.marked` event is published per submission.

**FR-10 Attendance correction with auditability.**
- After a session is closed, a record changes only through a correction with a mandatory reason.
- The instructor may correct within `TIMETABLE_ATTENDANCE_CORRECTION_WINDOW_DAYS` of closing. Holders of `attendance-record:correct-department` (HoD) may correct any class in their department, also after the window. Holders of `attendance-session:override` (admin) may correct any class.
- Every correction keeps the old value in the record history, writes to `platform/audit`, and publishes `attendance-record.updated`.

**FR-11 Closing an attendance session.**
- The instructor or an override holder closes the session.
- Unmarked eligible students become `absent` on close.
- A session still open when the marking window ends is closed automatically, with `closed_by` null (the system acted).
- On close, the scheduled class becomes `completed`, and `attendance-session.closed` is published with the counts.

**FR-12 Faculty attendance-to-mark.** The list of the caller's scheduled classes that have
started, are not cancelled, have no closed session, and are still within the marking window,
ordered by oldest first.

**FR-13 Student attendance summary and history.**
- **Summary:** per course offering in an academic period, show classes held, attended (`present` + `late`), excused, percentage, and a shortage flag below `TIMETABLE_ATTENDANCE_SHORTAGE_THRESHOLD_PERCENT`.
- **History:** the dated list of records.
- **Excused classes:** excluded from the denominator (classes held). Decided by owner decision C7 (Q6).
- **Access:** students see only their own; HoDs see students in their department; admins and viewers see all. Faculty see attendance for the classes they teach through the session records endpoints, not through reports.

**FR-14 Department attendance reporting.** For a department and academic period (and an
optional date range), show attendance percentage per course offering and section, with the
count and list of students below the threshold. The department comes from the course offering
data cached from academic-management, assuming its offering events carry the department (pending Q1).

**FR-15 Tenant isolation.**
- Every table has `organisation_id` with row-level security on `app.organisation_id`.
- Every query is scoped, every event carries `organisation_id`, and cache keys are prefixed by organisation.
- The cross-tenant leak test from `packages/testing` runs in this module's suite.

**FR-16 Auditability.**
- Every state change writes an immutable record to `platform/audit` through `packages/sdk`, with actor, time, before and after. This covers timetable create, update, publish and unpublish; class create, reschedule and cancel; session open and close; record mark and correct.
- Attendance records are never hard-deleted.

**FR-17 Vocabulary.** This is a common module, so labels come from the profile vocabulary (ADR-0004).
The code and contracts use neutral terms. Profiles may override:

| Key | Default label | Example override |
|---|---|---|
| `timetable-attendance.timetable` | Timetable | "Practice schedule", "Rehearsal schedule" |
| `timetable-attendance.scheduled-class` | Class | "Session", "Lecture", "Rehearsal" |
| `timetable-attendance.attendance` | Attendance | "Roll call" |

**FR-18 Bulk attendance for exam eligibility** (owner decision C7).
- `POST /reports/attendance-eligibility` returns attendance counts for one course offering, up to an inclusive cut-off date, for the listed students or for every student allocated to its sections.
- **Denominator (`classes_counted`):** closed sessions of non-cancelled classes in the range for which the student was eligible (FR-7). Sessions where the student was excused are left out.
- **Numerator (`attended`):** present + late.
- **Boundaries:** open sessions are not counted (their number is reported); cancelled classes are never counted. Inside a closed session no record is missing, because unmarked students become absent at close (FR-11).
- **Edge cases:** a student with no counted class is flagged `no_eligible_classes`. A requested student never allocated to the offering's sections in the range is listed under `unknown_student_ids`, not treated as an error.
- **No percentage threshold is applied here.** Examinations compares the counts with its own rule. Where the minimum lives is open (Q5).
- **Expected consumer:** examinations, calling through the gateway with the caller's identity. Requires `timetable-attendance:report:read-eligibility`, granted by default to `examination-staff`.
- **Dependencies:** `student_id` is provisional on Q3. The student population depends on the section-allocation events (Q2).

## 8. Data model (summary)

The module has its own schema, `timetable_attendance`. Every table has `organisation_id` and an RLS
policy on `app.organisation_id`. Full detail follows in `data-model.md` with the first migration.

| Table | Key columns |
|---|---|
| `timetable` | id, organisation_id, academic_period_id, department_id?, name, version, status, published_at |
| `timetable_slot` | id, organisation_id, timetable_id, day_of_week, start_time, end_time, course_offering_id, section_id, instructor_assignment_id, location_label, effective_from, effective_to |
| `scheduled_class` | id, organisation_id, timetable_id?, slot_id?, academic_period_id, course_offering_id, section_id, instructor_assignment_id, instructor_id, class_date, starts_at, ends_at, location_label, status, cancel_reason |
| `attendance_session` | id, organisation_id, scheduled_class_id (unique), status, opened_at, opened_by, marking_deadline, closed_at, closed_by |
| `attendance_record` | id, organisation_id, attendance_session_id, student_id, status, remark, marked_by, marked_at; unique (attendance_session_id, student_id) |
| `attendance_record_change` | id, organisation_id, attendance_record_id, from_status, to_status, reason, changed_by, changed_at |
| `offering_ref` (read model) | organisation_id, course_offering_id, academic_period_id, course_code, course_title, department_id, status |
| `section_ref` (read model) | organisation_id, section_id, course_offering_id, code, status |
| `instructor_assignment_ref` (read model) | organisation_id, instructor_assignment_id, course_offering_id, section_id?, instructor_id, status |
| `section_member` (read model) | organisation_id, section_id, student_id, student_name, allocated_from, allocated_to |

Read-model tables are refreshed only from consumed events (section 11). They are local
copies, not foreign keys. `department_id`, `instructor_id` and `student_id` are external IDs.

## 9. Cross-module integration

| Needs | From | How | Status |
|---|---|---|---|
| Academic periods, course offerings (course code, title, department), sections, instructor assignments (instructor id) | academic-management | Consume its events into the read models in section 8; validate IDs on timetable create and update | Event names **PENDING CONFIRMATION FROM OWNER** |
| Which students are allocated to which section, and from when | enrolment-registration | Consume its events into `section_member` | Event names **PENDING CONFIRMATION FROM OWNER** |
| Student display name | student-information or enrolment-registration | Cached on `section_member` from the allocation event if it carries it | Pending; see Q3 |
| Permission checks, current user | platform/identity | `packages/sdk` | Available |
| Audit trail | platform/audit | `packages/sdk` | Available |
| Publishing events | platform/event-bus | `packages/sdk` | Available |
| Absence notifications | platform/notification | Not in week 1; a later consumer of `attendance-record.marked` | Later |

Other modules use timetable-attendance only through `contracts/openapi.yaml` and
`contracts/events.yaml`.

## 10. Published events

All events are **proposed** for week 1. The full payloads are in `contracts/events.yaml`. Each one
uses the platform event envelope: `id`, `occurred_at`, `actor`, `organisation_id`, `version`, `payload`.

| Event | Proposed consumers |
|---|---|
| `timetable-attendance.timetable.created` | none yet (audit/reporting) |
| `timetable-attendance.timetable.updated` | none yet (audit/reporting) |
| `timetable-attendance.timetable.published` | none in Week 1; lms and examinations do not consume it ([decision C on #179](https://github.com/rooman-itsd/Education_OS/pull/179#issuecomment-6099361776)) |
| `timetable-attendance.timetable.unpublished` | none in Week 1; lms and examinations do not consume it ([decision C on #179](https://github.com/rooman-itsd/Education_OS/pull/179#issuecomment-6099361776)) |
| `timetable-attendance.scheduled-class.created` | platform/notification (later); not lms (owner decision C19) |
| `timetable-attendance.scheduled-class.updated` | platform/notification (later); not lms (owner decision C19) |
| `timetable-attendance.scheduled-class.cancelled` | platform/notification (later); not lms (owner decision C19) |
| `timetable-attendance.attendance-session.opened` | none yet |
| `timetable-attendance.attendance-record.marked` | examinations (attendance eligibility), platform/notification (absence alerts, later) |
| `timetable-attendance.attendance-record.updated` | examinations, platform/notification (later) |
| `timetable-attendance.attendance-session.closed` | examinations, platform/reporting |

## 11. Consumed events

None are declared in `module.yaml` until the owners confirm the names in their own `events.yaml`.
The names below describe what is needed. They are **not** event names.

| Needed fact | Publisher | Event name |
|---|---|---|
| Academic period created / became active | academic-management | PENDING CONFIRMATION FROM OWNER |
| Course offering created / updated / status changed (with course code, title, department) | academic-management | PENDING CONFIRMATION FROM OWNER |
| Section created / updated / closed | academic-management | PENDING CONFIRMATION FROM OWNER |
| Instructor assignment created / ended (with instructor id, offering, optional section) | academic-management | PENDING CONFIRMATION FROM OWNER |
| Student allocated to a section / moved / withdrawn (with effective date) | enrolment-registration | PENDING CONFIRMATION FROM OWNER |

academic-management's draft contract (branch `contract/academic-management/prd-and-contracts`,
not merged) proposes names for its events. They become authoritative only when that PR merges.

## 12. Permissions model

The keys are in `contracts/permissions.yaml`, in `timetable-attendance:<resource>:<action>` form, over the
resources `timetable`, `scheduled-class`, `attendance-session`, `attendance-record` and `report`.

Modules check permission keys, never roles (ARCHITECTURE.md, Security), so a wider scope always comes from holding a further key:

- **Own-scope rule.** `attendance-session:open`, `attendance-session:close`, `attendance-record:mark` and
  `attendance-record:correct` apply only to classes where the caller is the instructor.
  `attendance-record:correct-department` widens correction to the caller's department, and
  `attendance-session:override` widens all four to the organisation.
- **Read-scope rule.** `attendance-session:read` and `attendance-record:read` return classes the caller teaches.
  `report:read-department` widens them to the department, and `report:read-all` to the organisation.
- **Department-scope rule (pending Q9).** The admin and the HoD hold the same timetable and scheduled-class write keys.
  Limiting the HoD to their own department needs the caller's department from `platform/identity`. How that is
  exposed is not yet confirmed.
- **Self-scope rule.** `*:read-own` permissions return only the caller's own data.

| Default module role | For profile role |
|---|---|
| `timetable-attendance-admin` | `org-admin` (academic / timetable admin) |
| `timetable-attendance-department-head` | `department-admin` |
| `timetable-attendance-faculty` | `faculty` |
| `timetable-attendance-student` | `student` |
| `timetable-attendance-viewer` | read-only roles such as governance |
| `timetable-attendance-exam-eligibility` | `examination-staff` (only `report:read-eligibility`, for FR-18) |

## 13. Open questions and decisions pending confirmation

| # | Question | Who decides |
|---|---|---|
| Q1 | Exact academic-management event names and payloads for academic period, course offering, section and instructor assignment | Shivani (academic-management PR) |
| Q2 | Exact enrolment-registration event names and payloads for student-section allocation, including the effective date | Praveen |
| Q3 | Which identifier `student_id` is: the student-information record id or the identity user id; and whether the allocation event carries the display name | Praveen, Faizan |
| Q4 | Rooms: keep a free-text `location_label`, or reference a `facility-booking` resource and book it on publish | Ashritha, Faizan |
| Q5 | Shortage threshold, marking window and correction window: organisation settings (where?) or env defaults only | Faizan |
| Q6 | **Decided (owner decision C7):** `excused` classes are excluded from the denominator | Shivani |
| Q7 | **Decided (owner decision C7):** examinations reads attendance through the bulk report in FR-18, not through `attendance-record.*` events | Shivani |
| Q8 | **Decided (owner decision C5, [owner decision record](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6099000605)):** academic-management uses `academic_period_id`, `course_offering_id` and `instructor_assignment_id`, aligned in PR #168 | Shivani |
| Q9 | How the caller's department is known (identity SDK), and whether that alone limits a HoD's timetable and scheduled-class writes, or a separate org-wide key is needed | Faizan (platform/identity) |

## 14. Acceptance for this PRD (week 1)

- Contracts reviewed by Faizan; consumers confirm the events in section 10 and the owners confirm the names in section 11.
- Every widget in section 6 has its endpoint in `contracts/openapi.yaml` and its permission in `contracts/permissions.yaml`.
