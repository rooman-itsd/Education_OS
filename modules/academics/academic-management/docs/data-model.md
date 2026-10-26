# academic-management: data model

Source of truth: `backend/src/eos_academic_management/infrastructure/models.py` and the Alembic chain in
`db/migrations/` (revision `am_0001`). `backend/tests/test_migrations.py` checks that the two match.

## Conventions

- Every table is named `academic_management_<entity>` in the default schema and carries `organisation_id`
  (eos_core `TenantMixin`, indexed).
- Every table gets the shared row-level-security policy `tenant_isolation` (eos_core `rls.POLICY`) on Postgres:
  rows are visible only when `organisation_id` matches the session's `app.organisation_id`.
- Every query goes through eos_core `scoped()` (`infrastructure/repository.py`), so SQLite tests enforce the same
  rule. The organisation always comes from the verified token (or, for consumed events, the event envelope),
  never from a request body.
- The chain keeps its own version table, `academic_management_alembic_version`:
  `cd modules/academics/academic-management/db && alembic upgrade head`.
- Foreign keys stay inside the module. `department_id`, `faculty_id` (platform/identity user) and `person_id`
  (student-information Person) are external ids stored as strings.
- Credits and weekly hours are `NUMERIC(10, 2)`.

## Tables

| Table | Purpose | Uniqueness |
|---|---|---|
| `term` | Academic periods (FR-1, FR-2) | (organisation_id, code) |
| `programme` | Programmes (FR-3) | (organisation_id, code) |
| `course` | Course catalogue (FR-6, FR-7) | (organisation_id, code) |
| `curriculum` | Versioned curricula of a programme (FR-4) | (organisation_id, programme_id, version) |
| `curriculum_item` | Courses of a curriculum by programme term | — |
| `offering` | A course in a term (FR-8, FR-9) | — |
| `section` | Sections of an offering (FR-10) | (organisation_id, course_offering_id, code) |
| `faculty_assignment` | Who teaches an offering or section (FR-11, FR-12) | — |
| `roster_entry` | Read model of course registrations (FR-14), one row per registration | (organisation_id, registration_id) |
| `processed_event` | Envelope ids of consumed events, so a redelivered event is applied once | (organisation_id, event_id) |

Rows are never deleted by the use cases: courses and programmes are archived, sections closed, assignments ended,
and withdrawn registrations kept with `status = withdrawn`.
