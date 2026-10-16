# academic-management: product requirements

**Owner:** Shivani (@shivanisinghrooman-09) · **Tier:** common · **Status:** contracts merged (#168, contract 0.2.0 in progress); implementation in progress (issue #100). User stories: [user-stories.md](user-stories.md)

## 1. Purpose

academic-management is the academic catalogue of an organisation: what is taught, in which
programme, in which term, by whom. Every other academics module (timetable-attendance, lms,
examinations) and several dashboards read from it. It is the source of truth for:

- academic terms (the calendar periods teaching happens in);
- programmes and their curriculum (which courses, in which term of the programme, how many credits);
- the course catalogue;
- course offerings: a course taught in a specific term, split into sections;
- faculty assignments: which faculty member teaches which offering or section, and their load.

## 2. Scope

**In scope**

- Create and maintain terms, programmes, curricula, courses, offerings and sections.
- Publish a curriculum version; offerings reference courses from the published curriculum.
- Assign faculty to offerings and sections; compute faculty teaching load per term.
- Serve a read-only course roster per offering, from enrolment data received as events.
- Publish an event for every state change so dependent modules can keep a cached copy.

**Out of scope** (and who owns it)

| Not here | Owner |
|---|---|
| Student programme enrolment, semester registration, allocating students to sections | `student-lifecycle/enrolment-registration` (Praveen) |
| Student master records | `student-lifecycle/student-information` (Praveen) |
| Departments and other org units, users, roles | `platform/identity` |
| Class schedule, rooms, attendance | `academics/timetable-attendance` |
| Course content, assignments, grading of coursework | `academics/lms` |
| Exams, evaluation, results, transcripts | `academics/examinations` |

academic-management references students, faculty and departments by ID only. It keeps no
foreign key to another module's tables (module-standard, hard rule 2).

## 3. Users and roles

Profile role ids are from `platform/identity/config/profiles/*.yaml`.

| Role | What they do here |
|---|---|
| `org-admin` | Sets up terms, programmes, the course catalogue; publishes curricula |
| `department-admin` (HoD) | Creates offerings and sections for the department; assigns faculty; watches faculty load |
| `faculty` | Sees their assigned offerings and rosters |
| `student` | Reads programme structure, curriculum and course details |
| `examination-staff` | Reads offerings and courses (code, title, credits, department) to plan exams; assessment schemes are owned by `academics/examinations` |

Teacher-education roles inherit from these: `mentor-teacher` extends `faculty`; `teacher-trainee`
extends `student`.

## 4. Vocabulary (common tier)

This is a common module, so labels come from the profile vocabulary (ADR-0004). The code and the
contract use these neutral terms. A profile may rename them with the keys below:

| Key | Default label | Example override |
|---|---|---|
| `academic-management.programme` | Programme | "Course" (B.Ed.), "Training programme" (sports) |
| `academic-management.term` | Term | "Semester", "Trimester", "Season" |
| `academic-management.course` | Course | "Paper", "Subject", "Module" |
| `academic-management.section` | Section | "Batch", "Division", "Group" |
| `academic-management.offering` | Offering | "Class" |

`course_type` is a fixed generic set: `theory`, `practical`, `practicum`, `project`, `studio`.
A teacher-education college uses `practicum` for school-internship-linked courses; the internship
itself lives in `practice/field-training`.

## 5. Functional requirements

### 5.1 Terms
- FR-1 An org-admin creates terms with code, name, start and end date. Term dates in one organisation do not overlap.
- FR-2 Exactly one term per organisation is `active` at a time. Activating a term closes the previous one and publishes `term.activated`.

### 5.2 Programmes and curriculum
- FR-3 A programme has code, name, level (`certificate`, `diploma`, `undergraduate`, `postgraduate`, `doctoral`, `other`), owning department, duration in terms, and total credits required.
- FR-4 A curriculum is a versioned list of (course, programme term number, category `core|elective`, credits) for a programme. A curriculum is `draft` until published. Published versions are immutable; a change means a new version.
- FR-5 Publishing a curriculum checks that its credits add up to the programme's credits required. Then it publishes `curriculum.published`.

### 5.3 Courses
- FR-6 A course has code (unique per organisation), title, credits, contact hours per week (lecture/practical), `course_type` and owning department.
- FR-7 Courses are archived, never deleted, once any offering references them.

### 5.4 Offerings and sections
- FR-8 A department-admin creates an offering: one course in one term, optionally limited to programmes. An offering has at least one section, with a capacity.
- FR-9 Offerings move `planned → open → in_progress → completed`, or to `cancelled`. Each transition publishes an event.
- FR-10 Sections can be added while an offering is `planned` or `open`. A section with enrolled students cannot be deleted, only closed.

### 5.5 Faculty assignment and load
- FR-11 A department-admin assigns a faculty member (identity user id) to an offering, optionally to one section, with role `primary | co_instructor | teaching_assistant` and contact hours per week.
- FR-12 Each offering in `open` or later state has exactly one `primary` faculty.
- FR-13 Faculty load for a term = the sum of assigned contact hours. It is compared to the organisation's configured maximum (`ACADEMIC_MANAGEMENT_MAX_WEEKLY_CONTACT_HOURS`). Assignments over the maximum are allowed, but flagged.
  Owner decisions on [PR #168](https://github.com/rooman-itsd/Education_OS/pull/168#issuecomment-6186246300) (v1):
  - only active `primary` and `co_instructor` assignments count; `teaching_assistant` hours do not;
  - a faculty member with no counted assignment is not listed;
  - the report lists over-load first, then contact hours descending, and carries `faculty_count` and `over_load_count`, which do not change with `over_load_only`;
  - the report names its term (`academic_period_code`, `academic_period_name`) and each faculty member (`faculty_name`, resolved server-side);
  - with no term given and no active term, `GET /faculty-load` answers 404 `active_term_not_found`.

### 5.6 Roster
- FR-14 The roster for an offering lists the students enrolled in it, by section. It is a read model built from enrolment events (section 8). academic-management never writes enrolment itself.
- FR-15 A faculty member may read the rosters of offerings they are assigned to. Department-admins may read every roster in their department.

### 5.7 Audit
- FR-16 Every create, update, state change and assignment is written to `platform/audit` through `packages/sdk`. How the module integrates with audit until the SDK supports it is pending (issue #100, question to Himanshu).

## 6. Dashboard widgets served

Each widget's endpoint is in `contracts/openapi.yaml` before any widget is built.

| Widget id | Dashboard (builder) | Endpoint | Permission |
|---|---|---|---|
| `academic-management.course-roster` | Faculty (Shivani) | `GET /me/offerings`, then `GET /offerings/{course_offering_id}/roster` | `academic-management:roster:read` |
| `academic-management.faculty-load` | Department Admin (Himanshu; who builds the widget is pending: issue #2 against issue #100) | `GET /faculty-load?academic_period_id=&department_id=` | `academic-management:faculty-load:read` |

## 7. Data model (summary)

Every table has `organisation_id` and an RLS policy on `app.organisation_id`. Whether the tables live in an
own schema `academic_management` (module standard) or use module-prefixed table names (facility-booking
precedent) is pending with Faizan (issue #100); no migration is written before that decision. Full detail follows in `data-model.md` with the first migration.

| Table | Key columns |
|---|---|
| `term` | id, organisation_id, code, name, starts_on, ends_on, status |
| `programme` | id, organisation_id, code, name, level, department_id, duration_terms, credits_required, status |
| `curriculum` | id, organisation_id, programme_id, version, status, published_at |
| `curriculum_item` | id, organisation_id, curriculum_id, course_id, programme_term, category, credits |
| `course` | id, organisation_id, code, title, credits, lecture_hours, practical_hours, course_type, department_id, status |
| `offering` | id, organisation_id, course_id, academic_period_id, status, programme_ids |
| `section` | id, organisation_id, course_offering_id, code, capacity, status |
| `faculty_assignment` | id, organisation_id, course_offering_id, section_id, faculty_id, role, contact_hours, status |
| `roster_entry` (read model) | id, organisation_id, course_offering_id, section_id, person_id, enrolled_at, status |

`department_id`, `faculty_id` and `person_id` are external IDs (identity, student-information). `person_id` is the
learner identifier (confirmed on issue #100). The staff identifier on assignments (`faculty_id`) is pending with
Faizan (decision A, PR #168).

## 8. Events

The full list with payloads is in `contracts/events.yaml`. Every event carries `organisation_id`.

### 8.1 Published (proposed: consumers to confirm)

| Event | Proposed consumers |
|---|---|
| `academic-management.term.created` | timetable-attendance, examinations, lms, enrolment-registration |
| `academic-management.term.activated` | timetable-attendance, examinations, lms, enrolment-registration |
| `academic-management.programme.created` / `.updated` / `.archived` | enrolment-registration, student-information |
| `academic-management.curriculum.published` | enrolment-registration, examinations |
| `academic-management.course.created` / `.updated` / `.archived` | examinations, lms, timetable-attendance |
| `academic-management.offering.created` / `.updated` / `.status-changed` | timetable-attendance, lms, examinations, enrolment-registration |
| `academic-management.section.created` / `.updated` | timetable-attendance, lms, enrolment-registration |
| `academic-management.faculty-assignment.created` / `.ended` | timetable-attendance, lms, examinations |

`term.*` events identify the academic period by `academic_period_id`; `faculty-assignment.*` events identify the instructor assignment by `instructor_assignment_id`.

### 8.2 Consumed (proposed: not yet in `module.yaml`)

Enrolment is owned and published by `enrolment-registration`. The roster read model (FR-14)
needs these. Confirmed with Praveen on [issue #100](https://github.com/rooman-itsd/Education_OS/issues/100#issuecomment-6186232689):
`person_id` identifies the learner, `course_offering_id` and `section_id` align the two modules,
academic-management defines sections and enrolment-registration allocates students to them, and
integration is through APIs and events only. The event names and payloads below are still a proposal;
they go into `module.yaml` only once Praveen publishes them in his `events.yaml`.

| Proposed event | Needed fields |
|---|---|
| `enrolment-registration.course-registration.confirmed` | organisation_id, registration_id, person_id, student_name, roll_number, course_offering_id, section_id, academic_period_id, confirmed_at |
| `enrolment-registration.course-registration.withdrawn` | organisation_id, registration_id, person_id, course_offering_id, section_id, withdrawn_at |
| `enrolment-registration.section-allocation.changed` | organisation_id, registration_id, person_id, course_offering_id, from_section_id, to_section_id |

### 8.3 Confirmations needed before locking

| Who | What to confirm |
|---|---|
| Praveen (enrolment-registration, student-information) | Approach confirmed on issue #100 (see 8.2). Still open: the event names, payloads and timeline of his enrolment contract; whether he consumes `programme.*` and `curriculum.published` |
| Himanshu (Department Admin dashboard) | Reviewed on PR #168; the agreed changes are in contract 0.2.0 (FR-13). Still open: the `department-admin` grant (waits for the role decision) and who builds the widget |
| Tejaswini (Student dashboard) | Whether any Student widget needs academic-management data directly (none in the current layout) |
| Akshata (Examination Staff dashboard) | Answered on PR #168: examinations needs course code, title, credits, department and term, which the proposed `offering.created` payload carries; assessment schemes are owned by `academics/examinations`, not here. The event itself remains proposed (8.1) |
| Faizan (architecture) | Contract review; that academic terms are owned here and not in `packages/contracts` |

## 9. Permissions

The keys are in `contracts/permissions.yaml`, in `academic-management:<resource>:<action>` form.
Default module roles map to profile roles as in section 3.

## 10. Non-functional requirements

- Tenant isolation: RLS on every table; the cross-tenant leak test from `packages/testing` is in the suite.
- List endpoints are paginated (`limit`, `offset`, `total`).
- Widget endpoints respond within 300 ms at p95 for an organisation with 500 offerings per term.
- Every env key is prefixed `ACADEMIC_MANAGEMENT_` and listed in `config/env.example`.
- No institution-specific names in code; labels come from the vocabulary in section 4.

## 11. Open questions

1. Sections: **decided (confirmed with Praveen on issue #100):** sections are defined here; enrolment-registration allocates students to them.
2. Electives: does enrolment-registration need an "elective group" concept from the curriculum? If so, add `elective_group` to `curriculum_item`.
3. Cross-listed courses (one offering, several programmes): **decided (owner decision C21, [owner decision record](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6099000605)):** `programme_ids` on the offering stays the representation; no other cross-listing model.

## 12. Acceptance for this PRD (week 1)

- Contracts reviewed by Faizan; events confirmed by the owners in 8.3.
- Every widget in section 6 has its endpoint in `contracts/openapi.yaml`.
- Every permission used in section 6 is in `contracts/permissions.yaml`.

## 13. Decisions pending (issue #100)

Work that depends on these waits; nothing below is assumed in code or contracts.

| Decision | Who | Blocks |
|---|---|---|
| Canonical staff identifier; whether assignment fields and events rename `faculty_id` to `instructor_id` (decision A) | Faizan | Assignment table, assignment API and `faculty-assignment.*` payloads |
| Platform role ids or module role names, and the grant mapping | Faizan | `permissions.yaml` roles; which profile roles see each widget |
| Trusted source of a HoD's department | Faizan | Department scoping; the `department_id` default on `GET /faculty-load`; `roster:read-all` for departments |
| Own schema or module-prefixed tables | Faizan | Models, migrations, RLS policies, repository, cross-tenant leak test |
| Outbox `version` column (event-bus contract) | Faizan | Publishing events with the contract envelope |
| Audit integration before the SDK supports it | Himanshu | FR-16 |
| Enrolment contract (event names, payloads, timeline) | Praveen | Roster read model (FR-14, FR-15), section deletion with enrolled students (FR-10) |
| Who builds `academic-management.faculty-load` (issue #2 against issue #100) | Faizan, Himanshu | The faculty-load widget |
