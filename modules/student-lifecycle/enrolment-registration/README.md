# enrolment-registration

**Domain:** student-lifecycle
**Kind:** feature
**Status:** planned

Programme enrolment with roll numbers, term registration windows, course registration and section allocation.

## Scope
The source of truth for who is enrolled in which programme and who is registered for which course offering and
section in each term. academic-management (roster), examinations (candidates), lms (course members) and
timetable-attendance (section members) build their own copies from this module's events.

Not this module: persons (`student-information`), terms, programmes, offerings, sections and capacity
(`academics/academic-management`), exam eligibility (`academics/examinations`), fees (`fees-accounts`). Electives,
registration holds and student self-service are out of scope for this release. See [docs/prd.md](docs/prd.md),
including the decisions in section 11.

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
