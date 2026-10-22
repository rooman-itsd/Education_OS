# academic-management

**Domain:** academics
**Kind:** feature
**Status:** in progress (issue #100): domain rules and the faculty-load use case are built; persistence, API, events and widgets wait for the decisions in [docs/prd.md](docs/prd.md) section 13.

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
```
cd modules/academics/academic-management/backend
PYTHONPATH=src python -m pytest -q
```
`PYTHONPATH=src` is needed until the package is installed (`pip install -e backend`).

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
