# training-video-analysis

**Domain:** sports
**Kind:** feature
**Status:** planned

Training plans, sessions, video upload, tagging and annotation.

## Scope
_Owner fills in: what this module is responsible for, and what it explicitly is not._

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dashboard widgets
`frontend/src/widgets/index.ts` exports the widgets the role layouts in `platform/identity/config/dashboards/` name:

| Widget | Layout | Permission | Endpoints |
|---|---|---|---|
| `training-video-analysis.reviews-pending` | coach | `video:read` | `GET /videos?limit=20`, `GET /videos/{id}/annotations` for each of those |

The contract has no review status on a video and no annotation count, so a video waits for review while it has no
annotation. Finding those takes one annotations request per video, so the widget checks only the 20 most recently
recorded videos and says how many older ones it did not check. The coach's `session-plan` and the athlete's
`training-schedule` are not built here yet: their layout ids still name athlete-performance.

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
