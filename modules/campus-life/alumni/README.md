# alumni

**Domain:** campus-life
**Kind:** feature
**Status:** in-progress (contracts and backend)

Alumni directory and mentoring.

## Scope
- **In (v1.0):** a directory of alumni kept by staff (alumni have no login), a mentor flag, assignment of a mentor
  to a student, optional mentoring sessions, and the student's own view of their mentor (widget `alumni.mentoring`).
- **Not in v1.0:** alumni logins or self-registration, students browsing the directory, automatic matching, alumni
  events, donations and engagement campaigns (v1.1).

Product requirements and the owner's decisions: [docs/prd.md](docs/prd.md). Stories: [docs/user-stories.md](docs/user-stories.md).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml), base `/api/v1/alumni`
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml). Module roles `alumni-coordinator` and
  `alumni-mentee`; management-institute maps `placement-officer` and `management-student` onto them in their layouts.

## Dependencies
See `module.yaml`: platform identity and audit, through `packages/sdk`. This module must not import code from any
other module under `modules/`.

## Backend

| Layer | Path | Contents |
|---|---|---|
| domain | `backend/src/eos_alumni/domain/rules.py` | Record values (name, graduation year, email, phone, URL), the no-future-dates rule for `started_on` and `ended_on`, session time and duration. Pure Python. |
| application | `application/service.py` | Directory (list, add, read, full replace, archive, restore); assignments (list, start, read, end); sessions (list, schedule, edit or move, complete, cancel); `GET /me/mentoring`. |
| | `application/access.py`, `application/errors.py` | Permission keys of the catalogue; the error a use case raises with its contract status and code. |
| infrastructure | `infrastructure/models.py` | 4 `alumni_*` tables: `alumnus`, `mentoring_assignment`, `mentoring_session`, `audit_entry`. Each has `organisation_id`. |
| api | `api/router.py`, `api/schemas.py`, `api/deps.py` | Every operation of the contract, strict request bodies, and the token and permission check through `eos_core`. |
| db | `db/` | Alembic chain `alumni_0001` with its own version table `alumni_alembic_version`. It applies the `tenant_isolation` policy on Postgres. Data model: [docs/data-model.md](docs/data-model.md). |

Rules the code keeps:
- **Students see only their own mentor** (A5). A student holds `alumni:self:read` and nothing else, so every directory
  and mentoring route answers them 403. `GET /me/mentoring` looks the caller up by `(organisation_id, student_id)`,
  never by `student_id` alone, and returns only their active assignment: the mentor as a `MentorCard` (contact
  details included) and up to five upcoming sessions. Once the assignment ends the student sees nothing of it.
- **Staff notes stay with staff.** An alumnus's `notes` and a session's `notes` and cancel reason are returned only on
  the staff routes. `MentorCard` and `MySession` carry neither, and no event or audit row carries any text.
- **Upcoming** means status `scheduled` and `scheduled_at` at or after now, soonest first; a past session nobody marked
  completed drops off. An assignment's `next_session_at` uses the same rule.
- **Verified on creation** (A2): `verified_by` and `verified_at` are the creator and the creation time.
- **Full replace** (A8). `PUT /directory/{id}` takes `AlumnusUpdate`: a field left out is cleared and `is_mentor` is
  required (422 without it). `PUT /mentoring/sessions/{id}` replaces the session's fields the same way.
- **Archived, never deleted.** An archived record is not edited (409 `alumnus_archived`) or assigned; only an archived
  record is restored (409 `not_archived`). A mentor with an active assignment is neither archived nor has the flag
  cleared (409 `mentor_has_active_assignments`); the mentor row is locked while an assignment is made, so the two
  cannot cross.
- **One active mentor per student per organisation.** Checked before the insert (409 `student_already_assigned`) and
  kept by the partial unique index `uq_alumni_assignment_active_student` on `(organisation_id, student_id)` where the
  status is active; a concurrent second assignment hits the index and answers the same 409. A mentor may have several
  mentees; `active_mentees` counts them.
- **No future dates** (A7). "Today" is the Asia/Kolkata date (UTC+05:30, a fixed offset: India has no daylight saving
  and tzdata is not on the approved stack). `started_on` defaults to today and is today or earlier; `ended_on`
  defaults to today and is between `started_on` and today; otherwise 422 `invalid_date` with the field. The current
  year for `graduation_year` (1900 to this year, else `invalid_graduation_year`) is the Asia/Kolkata year too.
  Timestamps are stored and returned in UTC.
- **Sessions.** Scheduled only on an active assignment (409 `assignment_not_active`), not before the assignment started
  (the Asia/Kolkata date of `scheduled_at` is on or after `started_on`, else 422 `invalid_scheduled_at`), 1 to 480
  minutes long (`invalid_duration`). Only a scheduled session is edited, completed or cancelled (409
  `session_not_scheduled`). Moving it publishes `alumni.mentoring-session.rescheduled` with the new time; an edit that
  keeps the time publishes nothing. Ending an assignment cancels its scheduled sessions, each with its own
  `alumni.mentoring-session.cancelled`.
- **Events.** All nine events of `events.yaml` go to the `eos_core` outbox in the same transaction as the change, with
  exactly the declared payload (ids, dates and the mode; no names or contact details). A test runs every operation and
  checks each published event's keys and types.
- **Every state change is audited.** An `alumni_audit_entry` row (actor, action, entity, id; never text) is written in
  the same transaction, until the audit SDK exists, as e-office and hr-payroll do.
- **Tenancy.** Every query goes through `eos_core.db.scoped`; an id of another organisation answers 404 `not_found`
  exactly like a missing one, for reads and writes. On Postgres the `tenant_isolation` policy is forced on every table.
- **Lists.** `GET /directory` lists active records unless `status=archived`, newest first; `q` matches name, company or
  designation (case-insensitive, `%` and `_` taken literally). `GET /mentoring/assignments` lists active first, then
  newest. Both page with an opaque `cursor` (400 `invalid_cursor` for one this API did not return) and `limit` (1 to
  200, default 50). `GET /mentoring/assignments/{id}/sessions` returns at most `limit` sessions, soonest first.

### Running the tests

```sh
pip install -e packages/core -e packages/testing -e "modules/campus-life/alumni/backend[test]"
pytest modules/campus-life/alumni/backend
```

The suite needs no other module: tokens are made with `eos_core.security` for the management-institute roles
`placement-officer` and `management-student`, whose layouts hold the module roles. It covers every route's success and
error codes, the 403s, the cross-tenant leak test (including `GET /me/mentoring` for a student id that exists in two
organisations), events against `events.yaml`, route, permission, status, error-code and enum drift against the
contract, response properties against the schemas, and the Alembic chain against the models.

### Migrations

```sh
cd modules/campus-life/alumni/db
alembic upgrade head                     # uses EOS_DATABASE_URL
```

### Needs from the host repo
- **Mounting, install and CI:** a `campus-life/alumni` entry in `apps/backend/config/modules.enabled.yaml` mounts the
  router at `/api/v1/alumni` (package `eos_alumni`) behind the entitlement gate, and makes `py-setup.sh`, the API
  image, CI and the auto-deploy install it, run its tests and upgrade its chain. That entry is a separate PR; until
  then CI runs this suite with the disabled modules (`tools/scripts/test-disabled-modules.sh`).
- **Dashboard:** the widget `alumni.mentoring` (frontend, separate PR) reads `GET /me/mentoring`; the
  management-student layout places it.
- **Identity:** `student_id` is not checked against identity until `packages/sdk` offers a user lookup (PRD open
  question 1); the coordinator's screen picks the student from identity's user list and sends `student_name` as a copy.
- **Notification:** nothing is sent in v1.0. The assignment and session events carry what a reminder would need.
- No settings: `config/env.example` keeps only `ALUMNI_FEATURE_ENABLED`; the rules are fixed, not configured.

### Assumptions to revisit
Where the contract and PRD are silent, the backend takes the most conservative reading below. None of these is an
owner decision.
- **Phone format.** Digits with an optional leading `+`, spaces, dots, hyphens and brackets, 7 to 15 digits in all;
  anything else is 422 `invalid_phone`.
- **LinkedIn URL.** Any absolute `http` or `https` address with a host (not only linkedin.com); anything else is 422
  `invalid_url`.
- **Blank text.** Surrounding spaces are trimmed and an empty optional field (`""`) is stored as null.
- **Filters.** `programme` matches the whole programme name, ignoring case; `q` is a substring match.
- **Restore** clears `archived_at` and `archive_reason`; the audit trail keeps that the record was archived.
- **Sessions cancelled by ending an assignment** get the cancel reason "The assignment ended."; the end reason stays on
  the assignment only.
- **Session times.** A session may be scheduled in the past (to record one that happened) and completed before its
  time; the contract names no error for either. Only a time before the assignment started is refused. A time sent
  without an offset is taken as UTC.
- **Ids.** A path id that is not a record of the caller's organisation, a malformed one included, is 404 `not_found`,
  and so is a `mentor_id` in a body. `student_id` must be a UUID (422 otherwise) and is stored in lower case, the form
  identity issues.
- **Request bodies are strict.** Unknown fields are refused with 422, read-only fields of `Alumnus` included, so a
  client sends `AlumnusUpdate` fields only. Checks the contract gives no code (a missing required field, a wrong type,
  over-long free text) answer FastAPI's standard 422 body, as in the other modules.
- **Order of checks.** On `PUT /directory/{id}`: 404, then 409 `alumnus_archived`, then the 422 field codes, then 409
  `mentor_has_active_assignments`. On `POST /mentoring/assignments`: 404, `alumnus_archived`, `not_a_mentor`,
  `invalid_date`, `student_already_assigned`.
- **Per organisation.** A student with an active mentor in one organisation may be assigned one in another; the
  one-active-mentor rule holds per `(organisation_id, student_id)` as the PRD's tenancy rules state.
- **Open questions 2 to 4 of the PRD** (consent for contact details, erasure, duplicate records) are not implemented:
  no consent field, no hard delete, no duplicate check.

## Layout
| Path | Purpose |
|---|---|
| `docs/` | PRD, user stories, data model, screen list |
| `contracts/` | OpenAPI, event schemas, permission catalogue |
| `backend/` | Domain, application, infrastructure, API layers + unit tests |
| `frontend/` | Pages, components, API client + tests |
| `mobile/` | Mobile screens (optional) |
| `db/` | Migrations and seed data, own schema only |
| `config/` | `env.example`, feature flags |
| `tests/e2e` | End-to-end tests runnable in isolation |

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
