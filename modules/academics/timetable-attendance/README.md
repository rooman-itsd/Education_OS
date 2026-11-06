# timetable-attendance

**Domain:** academics
**Kind:** feature
**Status:** in progress (issue #325). Built: domain rules, persistence (prefixed tables, row-level security, own
Alembic chain `tt_0001`, `tt_0002`, interim audit table), the timetable operations of `contracts/openapi.yaml` (list,
create, get, update, replace slots, list conflicts) and the academic-management event consumers that fill the term,
offering and section read models. Not built yet: publishing, class generation, scheduled classes, attendance, reports,
widgets, and the consumers whose identity mappings are unconfirmed. Open decisions:
[docs/reviewer-decisions.md](docs/reviewer-decisions.md).

Timetable generation, class scheduling, attendance capture and reports.

## Scope
_Owner fills in: what this module is responsible for, and what it explicitly is not._

## Classes, attendance and reports
`api/classes_attendance.py` serves the scheduled-class, attendance-session, attendance-record, report and `/me` operations
of `contracts/openapi.yaml` (contract 0.2.0), so the status line above is out of date for them: what is still not built is
class generation from a timetable (it waits on the organisation's time zone) and closing open sessions automatically at
their deadline (FR-11, needs a scheduler job). Rules the code applies, and why, are in
[docs/reviewer-decisions.md](docs/reviewer-decisions.md) section D. In short:

- Ad-hoc classes take their academic period and instructor from the read models; a class's date is its start's date in the
  offset the request gives. Cancelling a class with an open session marks the session `cancelled` (reviewer decision).
- Open, close, mark and correct: the class's instructor (`instructor_id` is the caller's user id), widened by
  `attendance-session:override`. Reads of sessions and records: the instructor or `report:read-all`.
- Reports count closed sessions of classes that are not cancelled; excused classes leave the denominator; a group with no
  counted class has a null percentage. The academic period defaults to the known term containing today (UTC), else 404
  `active_term_not_found`.
- The department keys (`report:read-department`, `attendance-record:correct-department`) grant nothing beyond the
  other keys until the caller's department can be known (PRD Q9): department and student reports need `report:read-all`.
- Opening a session snapshots the students of `section_member`, which the enrolment-registration consumers fill (see
  Event consumers below).

## Widgets
`frontend/src/widgets/index.ts` exports the five widgets the role layouts name. Each one fetches through
`frontend/src/api/client.ts`:

| Widget | Layouts | Endpoint | Empty state |
|---|---|---|---|
| `timetable-attendance.today` | student and the layouts extending it | `GET /me/schedule?date=<viewer's date>` | No classes today |
| `timetable-attendance.attendance-summary` | student and the layouts extending it | `GET /me/attendance-summary` | No attendance recorded yet (also with no active term) |
| `timetable-attendance.today-classes` | faculty and the layouts extending it | `GET /me/teaching-schedule?date=<viewer's date>` | No classes to teach today |
| `timetable-attendance.attendance-to-mark` | faculty and the layouts extending it | `GET /me/attendance-to-mark` | No attendance waiting to be marked |
| `timetable-attendance.department-attendance` | department-admin | `GET /reports/department-attendance` | No department attendance yet (also with no active term) |

Frontend tests: `cd modules/academics/timetable-attendance/frontend && pnpm test`.

## Event consumers
`application/consumers.py` is registered under the `eos.event_consumers` entry point (`backend/pyproject.toml`) and
lists its events in `module.yaml` (`consumes_events`). The event relay (`platform/event-bus`) finds the consumers of the
modules the host has enabled, so they run only when this module is enabled in `apps/backend/config/modules.enabled.yaml`.

| Event | Read model |
|---|---|
| `academic-management.term.created` | `term_ref` (code, name, `starts_on`, `ends_on`) |
| `academic-management.offering.created` | `offering_ref` (period, course code and title, department) |
| `academic-management.offering.status-changed` | `offering_ref.status` |
| `academic-management.section.created` | `section_ref` (code) |
| `academic-management.section.updated` | `section_ref.status` |
| `enrolment-registration.course-registration.confirmed` | `registration_ref`; `section_member` in the section from the date of `confirmed_at` |
| `enrolment-registration.course-registration.withdrawn` | `registration_ref.withdrawn_on`; memberships end on the date of `withdrawn_at` |
| `enrolment-registration.section-allocation.changed` | `registration_ref.moves`; the old section ends the day before `effective_on`, the new one starts on it |

Delivery is at-least-once and unordered: each handler is idempotent on the envelope id (`processed_event`), tolerates an
event arriving before its creation, orders status changes by the envelope `occurred_at`, and applies an event only in its
own organisation. A registration's memberships are rebuilt from all the facts its events carried, so any arrival
order gives the same rows. `person_id` is stored as `student_id`. Not consumed, pending decisions (see the decisions
page): `faculty-assignment.*` (identity mapping), `offering.updated` and `course.*` (no new values in the payload).

## Tests
Backend, from `modules/academics/timetable-attendance/backend` (a throwaway SQLite database, never a real one):
```
PYTHONPATH="src:../../../../packages/core/src:../../../../packages/testing/src" python -m pytest -q
```
(use `;` instead of `:` on Windows). The Postgres row-level-security tests run only when
`TIMETABLE_ATTENDANCE_TEST_POSTGRES_URL` points at a throwaway PostgreSQL server as a superuser.

## Migrations
```
cd modules/academics/timetable-attendance/db && alembic upgrade head
```
The database URL comes from `EOS_DATABASE_URL`, or `alembic -x url=... upgrade head`.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

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
