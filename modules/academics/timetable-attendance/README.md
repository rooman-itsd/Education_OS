# timetable-attendance

**Domain:** academics
**Kind:** feature
**Status:** in progress (issue #325). Built: domain rules, persistence (prefixed tables, row-level security, own
Alembic chain, interim audit table) and the timetable operations of `contracts/openapi.yaml` (list, create, get, update,
replace slots, list conflicts). Not built yet: publishing, class generation, scheduled classes, attendance, reports,
widgets, and the consumers that fill the read models. Open decisions: [docs/reviewer-decisions.md](docs/reviewer-decisions.md).

Timetable generation, class scheduling, attendance capture and reports.

## Scope
_Owner fills in: what this module is responsible for, and what it explicitly is not._

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
