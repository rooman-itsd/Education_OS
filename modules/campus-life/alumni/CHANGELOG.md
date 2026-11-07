# Changelog — alumni

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contract 0.1.0 (#337): alumni directory kept by staff (records verified on creation, archived not deleted, mentor
  flag), mentoring assignments (one active mentor per student) and optional sessions, and `GET /me/mentoring` behind
  the widget `alumni.mentoring`; error codes; seven events with ids only; permissions with the module roles
  `alumni-coordinator` and `alumni-mentee`.
- PRD (`docs/prd.md`) with the owner's decisions A1 to A6 (#337) and `docs/user-stories.md`. v1.0 is the directory
  and mentoring; events, donations and campaigns are v1.1.
- The management-institute layouts hold the module roles: `placement-officer` holds `alumni-coordinator` and
  `management-student` holds `alumni-mentee`, so `alumni.mentoring` is backed for the management student.
- Review changes (#422), contract still 0.1.0 (unreleased): no future dates (`started_on` today or earlier, `ended_on`
  between `started_on` and today, Asia/Kolkata; 422 `invalid_date`) and `PUT /directory/{id}` as a full replace with
  `AlumnusUpdate` (`is_mentor` required), both owner decisions A7 and A8 on #337; events `alumni.alumnus.restored`
  and `alumni.mentoring-session.rescheduled` (nine events); `required` lists on response schemas; 404 `not_found`
  on every operation that takes an id; `maxLength` on free text; `MyMentoring.assignment` typed `[object, "null"]`;
  "upcoming" defined; `limit` on an assignment's sessions; tenancy rules for `student_id` in the PRD data model.
- Backend (#337), package `eos_alumni`: every operation of the contract with its permission; the directory (records
  verified by their creator, `PUT` as a full replace with `is_mentor` required, archive and restore), mentoring
  assignments (one active mentor per `(organisation_id, student_id)`, kept by a partial unique index; no future
  `started_on` or `ended_on` on the Asia/Kolkata date; ending cancels scheduled sessions) and sessions (schedule, edit
  or move, complete, cancel), and `GET /me/mentoring` for the widget `alumni.mentoring`. The nine events go to the
  outbox in the same transaction with exactly the payloads of `events.yaml`; every state change writes an
  `alumni_audit_entry`. Alembic chain `alumni_0001` (four `alumni_*` tables, own version table, `tenant_isolation` on
  Postgres). Tests: every route's success and error codes, 403s, the cross-tenant leak test with `GET /me/mentoring`
  for a student id in two organisations, events, contract drift and migrations against the models. Not enabled in the
  host yet. `docs/data-model.md` and `docs/integration-points.md`; assumptions to revisit listed in the README.
- Frontend (#337): dashboard widget `alumni.mentoring` ("My mentor") for the management student, behind
  `alumni:self:read`, reading `GET /me/mentoring` through a typed client: the mentor with role, background, focus,
  start date and contact links, and up to five upcoming sessions with date and time in Asia/Kolkata; empty state "No
  mentor assigned yet" when `assignment` is null; loading and error states with retry; vitest and Testing Library
  tests.
