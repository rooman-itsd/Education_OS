# academic-management

**Domain:** academics
**Kind:** feature
**Status:** in progress (issue #100). Built: domain rules, persistence (prefixed tables, row-level security, own
Alembic chain), every operation of `contracts/openapi.yaml`, event publishing through the shared outbox, an audit
entry for every state change (module-local until the audit SDK ships), the roster read model and the
`academic-management.course-roster` and `academic-management.faculty-load` widgets. Outstanding shared work (envelope version, audit SDK,
error format, backend module loader, HoD department claim, faculty-name lookup): [docs/prd.md](docs/prd.md) section 13.

Programmes, curriculum, courses, credits, faculty-course assignment.

## Scope
The academic catalogue of an organisation: terms, programmes and versioned curricula, the course catalogue,
course offerings and their sections, faculty assignments and faculty load, and a read-only course roster built
from enrolment events.

Not here: student enrolment and allocation to sections (`student-lifecycle/enrolment-registration`), student
records (`student-lifecycle/student-information`), departments, users and roles (`platform/identity`),
timetables and attendance, coursework, and exams. See [docs/prd.md](docs/prd.md) section 2 and the stories in
[docs/user-stories.md](docs/user-stories.md).

## Tests
Backend, from `modules/academics/academic-management/backend` (a throwaway SQLite database, never a real one):
```
PYTHONPATH="src:../../../../packages/core/src:../../../../packages/testing/src" python -m pytest -q
```
(use `;` instead of `:` on Windows). With `PYTHONPATH=src` only, the domain and application tests run and the
API, migration and tenancy tests are skipped.

Frontend widgets: `pnpm --filter @eos/academic-management test`.

## Migrations
```
cd modules/academics/academic-management/db && alembic upgrade head
```
The database URL comes from `EOS_DATABASE_URL`, or `alembic -x url=... upgrade head`.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Backfill: `POST /offerings/republish` (permission `academic-management:offering:write`). **Run it once per
  organisation after deploy.** See [Backfill](#backfill-run-once-per-organisation-after-deploy).
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Backfill: run once per organisation after deploy
A module that consumes offering or section events (timetable-attendance, examinations, lms, enrolment-registration)
has no row for offerings created before it started consuming. `POST /api/v1/academic-management/offerings/republish`,
called as an organisation admin or department admin of the organisation, announces every offering and section of
that organisation again and returns `{"offerings": n, "sections": n, "published": n}`:

- per offering, `offering.created` (course details as they are now) and `offering.status-changed` with `from_status`
  equal to `to_status`, the current status (`offering.created` carries none);
- per section, `section.created` and `section.updated` (current capacity and status).

Each is a new event (new envelope id, `occurred_at` now). Consumers apply a creation once and a status by
`occurred_at`, so a consumer that already has an offering keeps it and the call is safe to repeat; run it again
whenever a consumer has lost its copy, or if a status changed while it was running. It changes nothing and writes no
audit entry. Faculty assignments, terms, programmes and courses are not republished.

Before running it where platform/reporting ingests events: reporting counts each `offering.created` as a new
offering (`academics.course_offerings`), so until it ignores a second fact for the same offering a republish
inflates that metric.

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
