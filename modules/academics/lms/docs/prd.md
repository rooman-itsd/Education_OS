# lms: product requirements

**Owner:** Shivani (@shivanisinghrooman-09) · **Tier:** common · **Status:** contracts in review (issue #63)

## 1. Objective

lms is the online learning space of each course offering. Instructors publish material, set and
grade coursework, run quizzes and hold discussions; students read, submit, attempt and take part.
It answers four questions:

- What should a student read or do in this course? (course spaces, content units, materials)
- What work is set and who has submitted it? (assignments, submissions, quizzes, quiz attempts)
- How did each student do on that work? (coursework grades and feedback, gradebook)
- What are people discussing? (discussion threads and posts)

It serves two dashboard widgets: one on the Faculty dashboard and one on the Student dashboard. Each is
inherited by every academy layout that extends those roles.

lms is meant to be reusable in other products (ADR-0001), so it depends only on `packages/`, platform
services and other modules' published contracts.

## 2. Scope

lms owns exactly these resources:

| Resource | Meaning |
|---|---|
| **Course Space** | The learning space of one course offering, optionally visible to some of its sections only |
| **Content Unit** | An ordered grouping inside a course space (for example a week or a topic) |
| **Course Material** | A document, external link or page published to a course space |
| **Assignment** | A piece of coursework with instructions, due date, maximum points and submission rules |
| **Submission** | One student's response to an assignment, per attempt |
| **Quiz** | A set of questions with a time limit, attempts allowed and an open/close window |
| **Quiz Attempt** | One student's attempt at a quiz, with answers and scores |
| **Grade / Feedback** | One student's coursework grade and feedback for one assignment or quiz |
| **Discussion** | Threads and posts inside a course space |
| **Gradebook and reports** | Derived, read-only views: gradebook, grading queue, recent materials, department activity |

**Coursework grades are not examination results.** They are points an instructor gives for coursework
inside lms. Examination marks, assessment schemes, results and their publication belong to
`academics/examinations`. Coursework grades do not feed an examinations assessment component in Week 1 (owner decision C9, LQ2).

## 3. Out of scope

lms references these by ID only. It keeps no foreign key to another module's tables and imports no
code from another module.

| Not here | Owner |
|---|---|
| Academic period, course, course offering, section, instructor assignment | `academics/academic-management` |
| Who is enrolled in a course offering or section | `student-lifecycle/enrolment-registration` |
| Person and student identity, departments | `platform/identity`, `student-lifecycle/student-information` |
| Timetable, scheduled classes, attendance | `academics/timetable-attendance` |
| Exams, assessment schemes, marks, results, hall tickets | `academics/examinations` |
| Projects with milestones, teams and reviews (capstone and others) | `practice/projects` |
| Learner portfolios, including teaching portfolios | `practice/portfolio` |
| Practicum and skill assessments | `practice/skill-progress` |
| Library catalogue and digital library | `campus-life/library` (see LQ9) |
| File storage | `platform/documents`, through `packages/sdk` |
| Notifications and reminders | `platform/notification`, `platform/scheduler` (see LQ14) |
| Online live classes (meeting links) | `integrations/video-conferencing` (see LQ8) |
| Search hosting | `platform/search` (see LQ14) |
| Cross-module analytics | `platform/reporting` |
| Plagiarism checking | No module or integration exists; out of scope unless an owner confirms otherwise (LQ11) |

## 4. Actors and responsibilities

Profile role ids are from `platform/identity/config/profiles/*.yaml`.

| Actor (profile role) | Responsibilities here |
|---|---|
| LMS administrator (`org-admin`) | Creates and archives course spaces, can act in any course space, reads organisation-wide reports |
| Department Admin / HoD (`department-admin`) | Reads course spaces, gradebooks and coursework activity for the department |
| Instructor (`faculty`) | Prepares and activates the course spaces they teach; publishes units and materials; sets assignments and quizzes; grades, gives feedback and releases grades; moderates discussions |
| Student (`student`) | Reads the course spaces they belong to; submits assignments; attempts quizzes; sees their released grades; takes part in discussions |
| Viewer (for example governance or IQAC roles) | Read-only access to course spaces and organisation-wide reports |

Teacher-education roles inherit from these: `mentor-teacher` extends `faculty`, and
`teacher-trainee` extends `student`. There is no teaching-assistant role in Week 1 (owner decision C18, LQ5).

## 5. Core resources

### 5.1 Course Space
- Has `course_offering_id`, `title`, `description` and `visible_section_ids`. An empty list means every section of the offering.
- Belongs to the department of its course offering. The department is cached from academic-management (consumed events pending, section 12).
- **Members:**
  - students registered in the course offering, and in a visible section where sections are set (pending LQ4)
  - instructors assigned to the offering (pending LQ5)

**Decided (owner decision C17):** a course space is created manually by an administrator, one per course offering. When it is archived stays open (LQ3).

### 5.2 Content Unit
- Has `title`, `position` and `published`.
- Groups materials, assignments and quizzes for display.
- A unit that is not published hides its items from students.

### 5.3 Course Material
- `material_type` is one of:
  - `document`: `document_id` in `platform/documents`; lms never stores file bytes
  - `link`: `url`
  - `page`: `body` text
- Also has `title`, an optional `unit_id`, `visible_section_ids` and `status`.
- Optional `scheduled_class_id` (a timetable-attendance ID). It stays optional and lms consumes no scheduled-class events (owner decision C19, LQ12).

### 5.4 Assignment
- Has `title`, `instructions`, an optional `unit_id`, `due_at`, `max_points` and `target_section_ids`.
- `submission_type` is one of `file`, `text`, `file_and_text`, `none` (the work is handed in offline and graded here).
- Has `max_attempts` (default 1), `late_policy` (`accept_late`, optional `late_cutoff_at`) and `status`.

### 5.5 Submission
- Has `assignment_id`, `student_id` (an external ID; LQ6), `attempt`, `submitted_at` and `late`.
- Content: `document_ids` and/or `text`.
- `status` is `submitted`, `graded` or `superseded`. An earlier attempt is superseded by a later one.

### 5.6 Quiz
- Has `title`, an optional `unit_id`, `opens_at`, `closes_at`, `time_limit_minutes`, `attempts_allowed`, `attempt_scoring` (`highest` or `latest`), `auto_release` and `status`.
- Questions have a `question_type`:
  - `single_choice`, `multiple_choice`, `true_false` and `short_answer` (exact match) are scored automatically
  - `essay` is scored manually
- Each question also has `prompt`, `options` (for choice types) and `points`. The answer key is never returned to students.

### 5.7 Quiz Attempt
- Has `quiz_id`, `student_id`, `attempt_number`, `started_at`, `submitted_at`, `answers`, `auto_score` and `manual_score`.
- `manual_grading_state` is `none`, `pending` or `done`.
- `status` is `in_progress`, `submitted` or `graded`.

### 5.8 Grade / Feedback
- One per (assignment or quiz, student): `item_type` (`assignment` or `quiz`), `item_id`, `student_id`, `points`, `max_points`, `feedback`, `status` (`draft` or `released`) and `version`.
- **Coursework grade only, not an examination result.**

### 5.9 Discussion
- **Thread:** `course_space_id`, `title`, `body`, `created_by` and `state` (`open`, `locked` or `hidden`).
- **Post:** `thread_id`, `body`, `created_by` and `state` (`visible` or `hidden`).

## 6. Lifecycles

```
course space:   draft → active → archived
content unit:   unpublished ⇄ published
material:       draft → published ⇄ unpublished
assignment:     draft → published → closed
submission:     submitted → graded            (a later attempt marks earlier ones superseded)
quiz:           draft → published → closed
quiz attempt:   in_progress → submitted → graded
grade:          draft → released              (a change after release needs a reason and re-releases a new version)
thread:         open ⇄ locked; open|locked ⇄ hidden
post:           visible ⇄ hidden
```

| Lifecycle | Rules |
|---|---|
| Course space | Students see it only once `active`. `archived` is read-only for everyone. When it is archived (manually, or when the offering completes) is part of LQ3 |
| Content unit, material | Students see published items in published units, visible to their section. Unpublishing hides an item without deleting it |
| Assignment | Can be edited in `draft`. Once `published`, changes to `due_at`, `max_points`, `target_section_ids` or `late_policy` publish `assignment.updated`. `closed` accepts no submissions |
| Submission | Accepted while the assignment is `published`. It is `late` when after `due_at`, and refused after `late_cutoff_at` or when `accept_late` is false. A new attempt (up to `max_attempts`) supersedes the previous one and is the one graded |
| Quiz | Can be edited in `draft`. Questions are frozen once `published`. Attempts are possible between `opens_at` and `closes_at`. `closed` stops new attempts |
| Quiz attempt | Answers can be saved while `in_progress`. An attempt still running at its time limit or at `closes_at` is submitted by the system. Automatic questions are scored on submit. With essay questions `manual_grading_state` is `pending` until scored, then the attempt is `graded` |
| Grade | Created as `draft` when an instructor grades a submission, or when a quiz attempt is fully scored (using `attempt_scoring`). Students see only `released` grades. A quiz with `auto_release` releases on full scoring. Changing a released grade needs a reason, increments `version` and is released again |
| Thread, post | Members post while the space is `active` and the thread is `open`. Moderators lock threads and hide threads or posts. Hidden content is kept for audit |

## 7. Dashboard and widget requirements

The widget ids come from the role layouts in `platform/identity/config/dashboards/` and issue #103.
This PR does not change those layouts.

| Widget id | Dashboards (builder) | Data required | Endpoint | Permission |
|---|---|---|---|---|
| `lms.assignments-to-grade` | Faculty (Shivani); inherited by every layout that extends `faculty` (for example mentor-teacher, music-teacher, clinical-supervisor) | Per course space the caller teaches: assignments and quizzes with ungraded submissions or attempts, the count, the due date, and the oldest waiting submission | `GET /me/grading-queue` | `lms:grade:manage-assigned` |
| `lms.course-materials` | Student (Tejaswini); Management Student (Gokula Lakshmi, #17); Medical Student (Tejaswini, #18); inherited by every layout that extends `student` (for example teacher-trainee, dancer) | Recently published materials in the caller's course spaces: title, course, published date, type | `GET /me/course-materials` | `lms:course-space:read-own` |

Because both widgets appear in many academies, their labels come from the profile vocabulary (FR-22,
LQ15). Management Student and Medical Student list `lms.course-materials` although they already
inherit it from `student`, which may show the card twice (LQ16). This is not changed here.

## 8. Functional requirements

**FR-1 Course space creation.**
- An administrator creates a course space for a course offering, optionally limited to some sections.
- The course offering must exist in the local read model, which is filled by consumed events (pending, section 12).
- Creation is manual (owner decision C17). `course-space.created` is published on creation.

**FR-2 Course space settings and lifecycle.**
- Instructors of the space (or an administrator) edit its title, description and visible sections, activate it and archive it.
- Activation makes it visible to students; archiving makes it read-only.

**FR-3 Course space membership.**
- Students who belong to a course space: those registered in the course offering, and in a visible section where sections are set.
- Instructors who belong: those assigned to the offering.
- Both lists come from read models refreshed by consumed events (pending LQ4, LQ5). lms never writes enrolment or instructor assignment.

**FR-4 Content units.** Instructors create, rename, reorder, publish and unpublish units.

**FR-5 Course materials.**
- Instructors add documents (stored in `platform/documents`), links and pages; edit them; and publish or unpublish them.
- Publishing publishes `material.published`.
- An optional `scheduled_class_id` may be set (owner decision C19).

**FR-6 Assignments.**
- Instructors create assignments with the fields in 5.4, then publish and close them.
- Publishing publishes `assignment.published`.
- After publication, a change to `due_at`, `max_points`, `target_section_ids` or `late_policy` publishes `assignment.updated`.

**FR-7 Submissions.**
- A student in a target section submits while the assignment is published, within the late policy and `max_attempts`.
- File content is uploaded to `platform/documents` first; lms keeps the `document_id`.
- Each submission publishes `submission.submitted`.
- Students see their own submissions; instructors see the submissions of their spaces.

**FR-8 Quizzes.**
- Instructors create quizzes and their questions while in draft, then publish and close them.
- Publishing publishes `quiz.published`. Questions cannot change after publication.

**FR-9 Quiz attempts.**
- A student starts an attempt inside the open window and within `attempts_allowed`; saves answers; and submits.
- The system submits an attempt automatically at the time limit or at `closes_at`.
- Submitting publishes `quiz-attempt.submitted`.
- Students never receive the answer key.

**FR-10 Automatic and manual quiz scoring.**
- Automatic question types are scored on submit.
- Instructors score essay questions. The attempt is `graded` when every question is scored.

**FR-11 Grading and feedback.**
- Instructors enter points (0 to `max_points`) and feedback for each student on an assignment or quiz.
- Quiz grades are created from attempts according to `attempt_scoring`, and instructors may override them with a reason.
- Grades start as `draft`.

**FR-12 Grade release.**
- Instructors release grades per assignment or quiz, for all or listed students. A quiz with `auto_release` releases on full scoring.
- Each release publishes `grade.released`.
- Changing a released grade needs a reason, creates a new `version` and releases it again.
- These are coursework grades, not examination results (section 2).

**FR-13 Gradebook.**
- For a course space: every published assignment and quiz per student, with the status (`missing`, `submitted`, `graded` or `released`) and points.
- Totals are unweighted: released points over the maximum of released items. Weighting belongs to examinations (LQ2, owner decision C9).
- Instructors see drafts; students see only their own released grades.

**FR-14 Discussions.**
- Members start threads and post replies while the space is active and the thread is open.
- Starting a thread publishes `discussion-thread.created`.

**FR-15 Discussion moderation.**
- Instructors (or administrators) lock and unlock threads, and hide and unhide threads and posts.
- Hidden content stays stored for audit.

**FR-16 Grading queue.**
- For the caller: assignments and quizzes in the course spaces they teach that have ungraded submissions or attempts needing manual scoring.
- Shows the count, due date and oldest waiting submission, oldest first.
- Serves `lms.assignments-to-grade`.

**FR-17 Recent course materials.**
- For the caller: published materials in active course spaces they belong to, newest first, with title, course, published date and type.
- Serves `lms.course-materials`.

**FR-18 Department coursework activity.**
- For a department, and for the organisation with the wider key: per course space, the count of published materials, assignments and quizzes; submissions received; ungraded count; oldest ungraded; and last activity.
- Computed from this module's data only.

**FR-19 Tenant isolation.**
- Every table has `organisation_id` with row-level security on `app.organisation_id`.
- Every query is scoped, every event carries `organisation_id`, and document, search and cache keys are prefixed by organisation.
- The cross-tenant leak test from `packages/testing` runs in this module's suite.

**FR-20 Auditability.**
- Every state change writes an immutable record to `platform/audit` through `packages/sdk`. This covers course space, unit, material, assignment, submission, quiz, attempt, grade, release and moderation.
- Submissions, attempts and grades are never hard-deleted.

**FR-21 File handling.**
- Documents for materials and submissions are stored and served by `platform/documents`; lms stores only `document_id`.
- Size limits, scanning and access rules are **PENDING (LQ7)**.

**FR-22 Vocabulary.** This is a common module, so labels come from the profile vocabulary (ADR-0004).
The code and contracts use neutral terms. Profiles may override them. The keys and default labels are
proposed below; the actual overrides are **OPEN (LQ15)**.

| Key | Default label |
|---|---|
| `lms.course-space` | Course |
| `lms.assignment` | Assignment |
| `lms.quiz` | Quiz |
| `lms.material` | Material |

## 9. Data model (summary)

The module has its own schema, `lms`. Every table has `organisation_id` and an RLS policy on `app.organisation_id`.
Full detail follows in `data-model.md` with the first migration.

| Table | Key columns |
|---|---|
| `course_space` | id, organisation_id, course_offering_id, title, description, visible_section_ids, department_id, status |
| `content_unit` | id, organisation_id, course_space_id, title, position, published |
| `course_material` | id, organisation_id, course_space_id, unit_id?, material_type, title, document_id?, url?, body?, scheduled_class_id?, visible_section_ids, status, published_at |
| `assignment` | id, organisation_id, course_space_id, unit_id?, title, instructions, due_at, max_points, submission_type, max_attempts, accept_late, late_cutoff_at, target_section_ids, status, published_at |
| `submission` | id, organisation_id, assignment_id, student_id, attempt, document_ids, text, submitted_at, late, status |
| `quiz` | id, organisation_id, course_space_id, unit_id?, title, opens_at, closes_at, time_limit_minutes, attempts_allowed, attempt_scoring, auto_release, status |
| `quiz_question` | id, organisation_id, quiz_id, position, question_type, prompt, options, answer_key, points |
| `quiz_attempt` | id, organisation_id, quiz_id, student_id, attempt_number, started_at, submitted_at, answers, auto_score, manual_score, manual_grading_state, status |
| `grade` | id, organisation_id, item_type, item_id, course_space_id, student_id, points, max_points, feedback, status, version, released_at, change_reason |
| `discussion_thread` | id, organisation_id, course_space_id, title, body, created_by, state |
| `discussion_post` | id, organisation_id, thread_id, body, created_by, state |
| `offering_ref` (read model) | organisation_id, course_offering_id, academic_period_id, course_code, course_title, department_id, status |
| `instructor_ref` (read model) | organisation_id, course_offering_id, section_id?, instructor_id, role, status |
| `member_ref` (read model) | organisation_id, course_offering_id, section_id?, student_id, status |

Read-model tables are refreshed only from consumed events (section 12). They are local
copies, not foreign keys. `student_id`, `instructor_id`, `department_id`, `document_id` and `scheduled_class_id` are external IDs.

## 10. Cross-module integration

| Needs | From | How | Status |
|---|---|---|---|
| Course offering (code, title, department, status), sections, academic period | academic-management | Consumed events into `offering_ref` | PENDING CONFIRMATION FROM OWNER (Shivani; names become authoritative when PR #168 merges, owner decision C4) |
| Instructor assignments, including teaching assistants | academic-management | Consumed events into `instructor_ref` | PENDING CONFIRMATION FROM OWNER (Shivani; LQ5) |
| Students registered in each course offering and section | enrolment-registration | Consumed events into `member_ref` | PENDING CONFIRMATION FROM OWNER (Praveen; LQ4) |
| Canonical student identifier | student-information / identity | n/a | PENDING (Praveen, Faizan; LQ6) |
| Scheduled classes, only as an optional material link | timetable-attendance | ID only; no events consumed | Decided (owner decision C19) |
| Permission checks, current user, caller's department | platform/identity | `packages/sdk` | Available; department source pending LQ13 |
| Audit trail | platform/audit | `packages/sdk` | Available |
| Publishing events | platform/event-bus | `packages/sdk` | Available |
| Material and submission files | platform/documents | `packages/sdk` | Available; limits pending LQ7 |
| Search, reminders, notifications | platform/search, scheduler, notification | Not used in week 1 | LQ14 |

Other modules use lms only through `contracts/openapi.yaml` and `contracts/events.yaml`.

## 11. Published events

All events are **PROPOSED** for week 1. The payloads are in `contracts/events.yaml`. The envelope is
the one stored by `packages/core` (`eos_core.events.OutboxEvent`): `id`, `name`, `organisation_id`,
`actor`, `occurred_at`, `payload` (see examinations R-1 for the `version` question).

| Event | Proposed consumers |
|---|---|
| `lms.course-space.created` | none yet |
| `lms.material.published` | notification |
| `lms.assignment.published` | notification; possibly examinations (LQ1) |
| `lms.assignment.updated` | notification; possibly examinations (LQ1) |
| `lms.submission.submitted` | notification |
| `lms.grade.released` | notification; not examinations in Week 1 (owner decision C9) |
| `lms.quiz.published` | notification; possibly examinations (LQ1) |
| `lms.quiz-attempt.submitted` | none yet |
| `lms.discussion-thread.created` | notification |

## 12. Consumed events

None are declared in `module.yaml` until the owners confirm the names in their own `events.yaml`.
The names below describe what is needed. They are **not** event names.

| Needed fact | Publisher | Event name |
|---|---|---|
| Course offering created / updated / status changed, with course code, title, department | academic-management (Shivani) | PENDING CONFIRMATION FROM OWNER |
| Section created / updated | academic-management (Shivani) | PENDING CONFIRMATION FROM OWNER |
| Academic period changes (for archiving) | academic-management (Shivani) | PENDING CONFIRMATION FROM OWNER |
| Instructor assignment created / ended, with role (including teaching assistants) | academic-management (Shivani) | PENDING CONFIRMATION FROM OWNER |
| Student registered in / withdrawn from a course offering or section | enrolment-registration (Praveen) | PENDING CONFIRMATION FROM OWNER |

The academic-management (PR #168) and timetable-attendance (PR #179) drafts propose event names and
list lms as a consumer. Those names become authoritative only when the PRs merge.

## 13. Permissions

The keys are in `contracts/permissions.yaml`, in `lms:<resource>:<action>` form, over the resources
`course-space`, `material`, `assignment`, `submission`, `quiz`, `quiz-attempt`, `grade`, `discussion` and `report`.

Modules check permission keys, never roles (ARCHITECTURE.md, Security). Each scope is its own key, and a key
means the same scope whoever holds it:

| Scope | Meaning |
|---|---|
| `-own` | The caller's own records (submissions, attempts, released grades), and the course spaces the caller belongs to as student or instructor |
| `-assigned` | Course spaces the caller teaches (instructor assignment, pending LQ5) |
| `-department` | Course spaces of the caller's department (department source pending LQ13) |
| `-all` | Every course space in the organisation |

**How operations state their permission.** This follows the timetable-attendance and examinations contracts:
- **`x-permission`** names the single, narrowest key that grants the operation.
- **The operation's description** names the wider keys of the same action that widen its scope.
- **The widest key the caller holds** applies.
- **Roles** hold the narrowest key plus any wider ones.

Reading a course space and its published content (units, materials, assignments, quizzes, threads) uses
`course-space:read-own`, widened by `course-space:read-department` and `course-space:read-all`. Instructor
actions use `*:manage-assigned`, `grade:manage-assigned` and `discussion:moderate-assigned`, each widened by
the matching `-all` key.

| Default module role | For profile role |
|---|---|
| `lms-admin` | `org-admin` |
| `lms-department-head` | `department-admin` |
| `lms-instructor` | `faculty` |
| `lms-student` | `student` |
| `lms-viewer` | read-only roles such as governance |

There is no teaching-assistant role in Week 1 (owner decision C18). How instructor assignments feed the `-assigned` scope stays open (LQ5).

## 14. Open questions

| # | Question | Who decides |
|---|---|---|
| LQ1 | Examinations Q6: does `examinations.upcoming-assessments` include LMS quizzes and assignment due dates? If it does, examinations would consume `lms.assignment.*` and `lms.quiz.published`, or a separate LMS widget would be added to the Student layout | Tejaswini, Shivani |
| LQ2 | **Decided for Week 1 (owner decision C9, [owner decision record](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6099000605)):** coursework grades do not feed the examinations `continuous` component; revisited in a later phase | Shivani |
| LQ3 | **Creation and scope decided (owner decision C17, [owner decision record](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6099000605)):** manual, one per course offering. **Still open:** when a course space is archived | Shivani (academic-management and lms) |
| LQ4 | Which enrolment-registration events and payloads define student access (course offering and section registration, withdrawal)? | Praveen |
| LQ5 | **Teaching-assistant part decided (owner decision C18, [owner decision record](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6099000605)):** no teaching-assistant role in Week 1. **Still open:** how instructor assignments are represented for the `-assigned` scope (academic-management events, C4) | Shivani (academic-management) |
| LQ6 | What is the canonical `student_id` (student-information record id or identity user id)? Same as examinations Q2 and timetable-attendance Q3 | Praveen, Faizan |
| LQ7 | Which file size limits, scanning and access-control rules does `platform/documents` apply to materials and submissions? | Himanshu |
| LQ8 | Do live-class meeting links (`integrations/video-conferencing`) belong in lms or timetable-attendance? | Himanshu, Shivani |
| LQ9 | How should lms link library digital resources (reading lists): by URL, by a library item ID, or not at all? | Tejaswini |
| LQ10 | Boundary with `practice/projects` (capstone submissions and reviews), `practice/portfolio` (teaching portfolio) and `practice/skill-progress` (practicum assessment). Proposed: lms assignments are coursework only | Tejaswini, Praveen, Akshata |
| LQ11 | Plagiarism checking: no module or integration exists. Out of scope unless an owner confirms otherwise | Faizan, Himanshu |
| LQ12 | **Decided (owner decision C19, [owner decision record](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6099000605)):** `scheduled_class_id` stays optional; lms consumes no scheduled-class events, and timetable-attendance no longer lists lms as a consumer of them | Shivani |
| LQ13 | How is the caller's department determined (identity SDK)? Same as examinations Q13 and timetable-attendance Q9 | Faizan |
| LQ14 | Future integration with `platform/search` (indexing materials) and `platform/scheduler` / `platform/notification` (due-date reminders). Not in week 1 | Himanshu |
| LQ15 | Profile vocabulary keys for lms (for example "assignment" called "studio brief" in a design academy) | Faizan (profiles) |
| LQ16 | `management-student.yaml` and `medical-student.yaml` list `lms.course-materials` although they inherit it from `student`, so the card may appear twice | Faizan (layouts), Gokula Lakshmi (#17), Tejaswini (#18) |

## 15. Acceptance criteria (week 1)

- Contracts reviewed by Faizan. Consumers confirm the events in section 11, and owners confirm the names in section 12.
- Both widgets in section 7 have their endpoint in `contracts/openapi.yaml` and their permission in `contracts/permissions.yaml`.
- Every operation in `contracts/openapi.yaml` names a single existing `x-permission` key.
- Every event carries `organisation_id`.
- LQ1 to LQ16 are raised with their owners on the PR.
