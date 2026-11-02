# athlete-performance

**Domain:** sports
**Kind:** feature
**Status:** in-progress

Athlete profiles, performance metrics, fitness testing, benchmarks.

## Scope
Responsible for: the sports catalogue (disciplines, metric definitions, fitness tests), athlete sports profiles,
performance results and their history, fitness assessments, benchmarks and the comparison with them, fitness
clearance (status only) and the squad summary report.

Not responsible for: tournaments and fixtures (`tournament-events`), training plans and video
(`training-video-analysis`), medical records, injuries and nutrition (`sports-nutrition-health`), student records
(`student-information`) and sign-in (`platform/identity`). Those are linked by reference ids and events, never by
foreign keys.

Athletes see only their own profile, results, assessments, history and clearance; coaches, medical staff and
administrators see their organisation's athletes (`application/service.py`).

How benchmarks are matched (history, comparison): a benchmark applies when its discipline, if set, is one of the
athlete's and its gender, if set, is theirs or `any`. The most specific one wins (discipline over none, a gender over
`any`); among equals, the newest. The age group is shown but not matched, so benchmarks that differ only by age group
resolve to the newest. A comparison without `level` may pick different levels for different metrics; each row's
`benchmark_id` says which one was used, and `?level=` fixes it.

A clearance reads `not_cleared` when none was recorded or once its `valid_until` has passed.

Requirements: [docs/prd.md](docs/prd.md). Tables: [docs/data-model.md](docs/data-model.md).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dashboard widgets
`frontend/src/widgets/index.ts` exports the widgets the role layouts in `platform/identity/config/dashboards/` name:

| Widget | Layout | Permission | Endpoints |
|---|---|---|---|
| `athlete-performance.squad-overview` | coach | `report:read` | `GET /reports/squad-summary`, `GET /metrics` |
| `athlete-performance.fitness-clearances` | medical-staff | `clearance:read` | `GET /reports/clearances` |
| `athlete-performance.performance-trend` | athlete | `result:read` | `GET /athletes` (own profile), `GET /metrics`, `GET /results`, `GET /assessments`, `GET /athletes/{id}/history` for up to 4 metrics |
| `athlete-performance.body-composition-trend` | nutritionist | `report:read` | `GET /reports/squad-summary`, `GET /metrics`, `GET /fitness-tests` |

`GET /reports/clearances` lists every active athlete's clearance most urgent first (not cleared, restricted,
lapsing within `lapsing_within_days`, cleared) with counts over all of them; an athlete gets only their own row.
The `nutritionist` profile role reads athletes and summaries (`report:read`) for the body-composition widget, but
not clearances. Metrics have no category: a metric is body composition when a fitness test
whose name mentions body composition measures it, or its name does (body fat, weight, BMI, lean or muscle mass,
skinfolds, waist). The coach's `session-plan` and the athlete's `training-schedule` belong to training-video-analysis
(plans and sessions), not here.

## Dependencies
See `module.yaml`. From the host it needs `packages/core` (database, tenant scoping, outbox, tokens) and, for its
tests, `packages/testing`. The backend is `eos_athlete_performance.api.router:router`; its Alembic chain is `db/`. This module must not import code from any other module under `modules/`.

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
