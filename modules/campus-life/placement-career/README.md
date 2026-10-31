# placement-career

**Domain:** campus-life
**Kind:** feature
**Status:** in-progress (contract)

Campus placement for jobs: company records, drives, job openings, applications and offers.

## Scope
**Is:** company records, placement drives (dated campus events of one company), job openings in a drive or on their
own, student applications along a fixed status sequence, offers, and the reports behind the dashboard widgets
`placement-career.drives` (placement-officer) and `placement-career.openings` (student layouts and placement staff).

**Is not:** internships (field-training), recruiter logins (companies are records), automatic eligibility checks
(students self-declare; the officer shortlists), a one-offer policy. See [docs/prd.md](docs/prd.md) for the owner
decisions on #337 and [docs/user-stories.md](docs/user-stories.md).

**Roles:** `placement-career-officer` (placement-officer, industry-coordinator and practicum-coordinator layouts),
`placement-career-viewer` (industry-liaison), and `student` grants inherited by every learner layout.

**Needs from the host:** `packages/sdk` for identity and audit. No configuration keys yet.

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
