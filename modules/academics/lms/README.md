# lms

**Domain:** academics
**Kind:** feature
**Status:** in-progress (contract 0.1.0; backend, migration `lms_0001`, tests and the two dashboard widgets built; not
enabled in `apps/*` yet)

Learning management: content, assignments, quizzes, discussions, grading.

## Scope
Owner: Shivani (@shivanisinghrooman-09). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** the learning space of each course offering: content units and materials (documents by
platform/documents id, links, pages); assignments and submissions with a late policy and attempts; quizzes with
automatically scored and essay questions, attempts with a time limit; coursework grades, feedback and their release;
the gradebook; discussions and their moderation; a coursework activity report.

**Not in scope:** examination marks and results (examinations; coursework grades are not examination results),
offerings, sections and instructor assignments (academic-management), registrations (enrolment-registration), file
storage (platform/documents), notifications, search, plagiarism checking (docs/prd.md section 3).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml), mounted at `/api/v1/lms`
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)
- Dashboard widgets: `lms.assignments-to-grade` (Faculty) and `lms.course-materials` (Student), exported from
  `frontend/src/widgets/index.ts`
- Data model: [docs/data-model.md](docs/data-model.md); events, consumers and platform services:
  [docs/integration-points.md](docs/integration-points.md)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

What it needs from the host repo:
- `packages/core` (`eos_core`): database base and tenant scoping, row-level-security policy, token checks,
  permission catalogue, outbox for events. `packages/testing` for the cross-tenant leak test.
- `packages/ui-kit` for the widgets.
- platform/event-bus to deliver the consumed academic-management and enrolment-registration events: without them no
  offering, instructor or student is known to lms, and nothing can be created or seen.

## Backend

`backend/src/eos_lms`, in four layers:

| Layer | What |
|---|---|
| `domain/rules.py` | Statuses and transitions, the late policy, submission content, quiz questions, answers and scoring, attempt deadlines, which attempt a quiz grade follows, moderation |
| `application/` | Use cases by area (`content`, `coursework`, `quizzes`, `scoring`, `grades`, `discussions`, `reports`), who may see or change a course space (`access`, `common`), the consumers and the overdue-attempt job |
| `infrastructure/` | SQLAlchemy models (16 tables) and scoped queries |
| `api/` | `router.py` (every contract operation with its `x-permission`), `deps.py` (token, organisation, keys), `schemas.py` (request bodies, all bounded) |

How a caller is scoped (docs/prd.md section 13): an operation's route requires its `x-permission`; the use case then
narrows to the caller's course spaces. `-assigned` keys cover the spaces the caller teaches (an active instructor
assignment for the offering), `-own` the spaces they teach or learn in (an active registration, in a visible
section), `-all` every space. A student never sees a draft space, unpublished content, content in an unpublished unit
or content for another section, and never an answer key; quiz scores reach them once the quiz grade is released.

Errors are `{"detail": {"code", "message", "details"?}}`: 400 for a malformed body or query parameter, 403 outside
the caller's scope, 404 for what does not exist in the caller's organisation (or is hidden from them), 409 for the
current state (an archived space, a closed assignment, no attempts left), 422 for a domain rule (unknown offering,
unit or student; points above the maximum; a missing reason).

```
pip install -e modules/academics/lms/backend[test]                # into the repo .venv
cd modules/academics/lms/backend && python -m pytest -q            # throwaway SQLite, never a real database
cd modules/academics/lms/db && alembic upgrade head                # own tables and lms_alembic_version only
```

## Frontend

`frontend/src/widgets`: `AssignmentsToGradeWidget` (`lms.assignments-to-grade`, `GET /me/grading-queue`) and
`CourseMaterialsWidget` (`lms.course-materials`, `GET /me/course-materials`), through the typed client in
`frontend/src/api/client.ts`. Each has loading, empty and error states; the error state offers a retry unless the
answer was 401 or 403. Labels are the neutral defaults until the profile vocabulary keys are decided (LQ15).

```
pnpm --filter @eos/lms typecheck && pnpm --filter @eos/lms test
```

## Assumptions to revisit

Where the PRD leaves a question open, the simplest reading was built; each is easy to change.

1. **Who teaches and who learns (LQ4, LQ5, LQ6).** lms consumes academic-management `faculty-assignment.*` and
   enrolment-registration `course-registration.*` / `section-allocation.changed`, and reads `faculty_id` and
   `person_id` as identity user ids (the token subject), as academic-management reads `faculty_id`. An instructor
   assigned to one section teaches the whole course space.
2. **Department scope (LQ13).** The caller's department is not known, so `-department` keys widen nothing yet: a
   department head sees the spaces they teach or learn in. `GET /reports/coursework-activity` answers an empty
   report to a holder of `lms:report:read-department` only, and 403 `department_unverified` when they name a
   department.
3. **The LMS administrator.** `org-admin`'s layout lists no lms module role, so an organisation administrator does not
   hold `lms-admin` and cannot create course spaces until the layout (platform/identity) lists it or the role is
   granted. Not changed here (one module per PR).
4. **Archiving (LQ3).** Manual only. An archived space is read-only for everyone: no content, grading, release or
   moderation changes (409 `course_space_archived`); students still read it.
5. **Unpublished units** hide their assignments and quizzes from students too, not only materials.
6. **Submissions.** `file_and_text` needs both files and text; `none` refuses online submissions (409
   `offline_submission`); `late_cutoff_at` needs `accept_late`. Document ids are not checked against
   platform/documents yet (LQ7).
7. **Quiz scoring.** Automatic questions are all or nothing; `short_answer` compares trimmed text without regard to
   case. `highest` takes the best graded attempt; `latest` takes the latest submitted attempt once it is graded.
   When a later attempt changes a released quiz grade, the grade gets a new version and is released again
   (`change_reason` "recomputed from the quiz attempts").
8. **Quiz grades by hand.** Entering a quiz grade always needs a reason (it overrides the attempts); from then on the
   grade no longer follows the attempts.
9. **Attempt deadlines.** An attempt past its deadline is submitted by the system at that deadline the next time
   anything reads it, and by `application/jobs.py` `submit_overdue_attempts()` once platform/scheduler calls it.
10. **Grading queue.** Only the spaces the caller teaches (an administrator teaching nothing sees an empty queue),
    archived spaces left out. A quiz's `due_at` there is its `closes_at`.
11. **Release.** Without `student_ids`, every draft is released and `skipped` is 0; with them, `skipped` counts the
    listed students without a draft grade.
12. **Discussions.** Members (instructors and students of the space) take part; the LMS administrator may too
    (`lms:discussion:moderate-all`). Hiding an already hidden post is not an error. Moderation reasons are not stored.
13. **Grades are entered** for students registered in the offering, or who submitted or attempted the item.

## Layout
| Path | Purpose |
|---|---|
| `docs/` | PRD, data model, integration points |
| `contracts/` | OpenAPI, event schemas, permission catalogue |
| `backend/` | Domain, application, infrastructure, API layers + tests |
| `frontend/` | Widgets, API client + tests |
| `mobile/` | Mobile screens (optional) |
| `db/` | Alembic chain `lms_0001`, own tables only |
| `config/` | `env.example` |
| `tests/e2e` | End-to-end tests runnable in isolation |

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
