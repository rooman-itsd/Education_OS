# lms: data model

Source of truth: `backend/src/eos_lms/infrastructure/models.py` and the Alembic chain in `db/migrations/` (revision
`lms_0001`). `backend/tests/test_migrations.py` checks that the two match and that the chain downgrades cleanly.

## Conventions

- Every table is named `lms_<entity>` in the default schema and carries `organisation_id` (eos_core `TenantMixin`,
  indexed).
- Every table gets the shared row-level-security policy `tenant_isolation` (eos_core `rls.POLICY`, enabled and
  forced) on Postgres: rows are visible only when `organisation_id` matches the session's `app.organisation_id`.
- Every query goes through eos_core `scoped()` (`infrastructure/repository.py`), so the SQLite tests enforce the
  same rule. The organisation always comes from the verified token (or, for consumed events, the event envelope),
  never from a request body.
- The chain keeps its own version table, `lms_alembic_version`: `cd modules/academics/lms/db && alembic upgrade head`.
- Foreign keys stay inside the module. `course_offering_id`, section ids, `student_id`, `instructor_id`,
  `department_id`, `document_id` and `scheduled_class_id` are other modules' ids, stored as strings.
- Instants are stored in UTC (`DateTime(timezone=True)`); an instant sent without an offset is read as UTC.
- Section lists (`visible_section_ids`, `target_section_ids`), submission `document_ids`, quiz options, answer keys
  and attempt answers are JSON columns. An empty section list means every section.

## Tables

| Table | Purpose | Uniqueness |
|---|---|---|
| `course_space` | The learning space of one course offering (FR-1, FR-2); `department_id` cached from the offering | (organisation_id, course_offering_id) |
| `content_unit` | Ordered grouping inside a space (FR-4); positions stay 0..n-1 | — |
| `course_material` | Document (`document_id` only), link (`url`) or page (`body`) (FR-5) | — |
| `assignment` | Coursework with due date, points, submission type, attempts and late policy (FR-6) | — |
| `submission` | One student's attempt at an assignment (FR-7); earlier attempts become `superseded` | (organisation_id, assignment_id, student_id, attempt) |
| `quiz` | Window, time limit, attempts, scoring rule, auto release (FR-8) | — |
| `quiz_question` | Questions with options, answer key and points; replaced as a whole while the quiz is a draft, frozen after | — |
| `quiz_attempt` | One student's attempt (FR-9, FR-10): answers, `must_submit_by`, automatic score, essay scores by question (`question_scores`), `manual_score` | (organisation_id, quiz_id, student_id, attempt_number) |
| `grade` | One coursework grade per (item, student) (FR-11, FR-12); `version` rises on each change after release; `source` is `attempts` while a quiz grade follows its attempts and `manual` once an instructor entered it | (organisation_id, item_type, item_id, student_id) |
| `discussion_thread` | Threads (FR-14); `locked` and `hidden` flags give the state (open, locked, hidden), so unhiding restores the lock | — |
| `discussion_post` | Replies, `visible` or `hidden` (FR-15) | — |
| `offering_ref` | Read model: course offerings from academic-management (code, title, department, period, status) | (organisation_id, course_offering_id) |
| `instructor_ref` | Read model: instructor assignments from academic-management (`instructor_id` = identity user id) | (organisation_id, instructor_assignment_id) |
| `member_ref` | Read model: course registrations from enrolment-registration (`student_id` = identity user id, section, name) | (organisation_id, registration_id) |
| `processed_event` | Envelope ids of consumed events, so a redelivered event is applied once | (organisation_id, event_id) |
| `audit_entry` | Who changed what and when, one row per state change (FR-20), until the audit SDK ships. Ids and the action only, never content | — |

Read-model rows also keep `status_as_of`, the envelope `occurred_at` of the event that last set their status, so an
older event arriving late never overwrites a newer state.

## Lifecycles

```
course space:   draft -> active -> archived           (archived is read-only for everyone)
content unit:   unpublished <-> published
material:       draft -> published <-> unpublished
assignment:     draft -> published -> closed
submission:     submitted -> graded; superseded by a later attempt
quiz:           draft -> published -> closed          (questions frozen once published)
quiz attempt:   in_progress -> submitted -> graded    (graded at once when there is no essay)
grade:          draft -> released                     (a change after release: reason, version + 1, released again)
thread:         open <-> locked; open|locked <-> hidden
post:           visible <-> hidden
```

Nothing is hard-deleted: submissions, attempts, grades and hidden discussion content are kept (FR-20). The only rows
the use cases delete are the questions of a draft quiz when its questions are replaced.
