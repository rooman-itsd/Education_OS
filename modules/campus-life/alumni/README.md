# alumni

**Domain:** campus-life
**Kind:** feature
**Status:** in-progress (contracts)

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
