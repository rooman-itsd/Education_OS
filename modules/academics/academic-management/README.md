# academic-management

**Domain:** academics
**Kind:** feature
**Status:** in progress (issue #100). Built: domain rules, persistence (prefixed tables, row-level security, own
Alembic chain), every operation of `contracts/openapi.yaml`, event publishing through the shared outbox, an audit
entry for every state change (module-local until the audit SDK ships), the roster read model and the
`academic-management.course-roster` widget. Outstanding shared work (envelope version, audit SDK,
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

Frontend widget: `pnpm --filter @eos/academic-management test`.

## Migrations
```
cd modules/academics/academic-management/db && alembic upgrade head
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
