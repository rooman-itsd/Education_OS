# field-training

**Domain:** practice
**Kind:** feature
**Status:** in-progress (contract 0.1.0; backend, migrations, tests and the five widgets built; not yet listed in the
apps)

Field training placements: clinical rotations, teaching practice, farm rotations, internships, court visits.


## Scope
Owner: Tejaswini (@tejaswini-rooman). Requirements: [docs/prd.md](docs/prd.md). Stories:
[docs/user-stories.md](docs/user-stories.md).

Generic "Field training" pattern used by every academy type. Labels come from the academy profile
vocabulary (`field-training.placement`, `field-training.site`, `field-training.supervisor`); the module
names no field.

**In scope:** host sites and their supervisors; openings with seats, period and required hours;
placements by assignment or application; the logbook of hours and activities with supervisor
verification; mid and final assessment outcome; completion and withdrawal.

**Not in scope:** paid job placement drives (placement-career), rubric-based skill assessment
(skill-progress), class attendance (timetable-attendance), site agreements as documents
(platform/documents), and any field-specific rule (a profile setting or a specialized module).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)
- Dashboard widgets, exported from `frontend/src/widgets/index.ts`:

| Widget | Permission | Endpoint |
|---|---|---|
| `field-training.my-placement` | `field-training:self:read` | `GET /me/placements` |
| `field-training.hours-logged` | `field-training:self:read` | `GET /me/hours` |
| `field-training.trainees-to-assess` | `field-training:supervision:read` | `GET /me/trainees` |
| `field-training.placements-open` | `field-training:opening:read` | `GET /openings?status=open&has_seats=true` |
| `field-training.active-placements` | `field-training:placement:read` | `GET /placements?status=active` |

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

What it needs from the host repo:
- `packages/core` (`eos_core`): database base and tenant scoping, row-level-security policy, token checks,
  permission catalogue, outbox for events. `packages/testing` for the cross-tenant leak test.
- `packages/ui-kit` for the widgets. No platform service is called directly yet: events go to the outbox, audit
  entries to the module's own table, and the daily job (`backend/src/eos_field_training/application/jobs.py`,
  `run_daily`: start assigned placements on their start date) waits for `platform/scheduler` to call it.
- The API router is `eos_field_training.api.router:router`, to be mounted under `/api/v1/field-training` by the module
  loader from `apps/backend/config/modules.enabled.yaml`; the widgets are registered from
  `apps/frontend/config/modules.enabled.yaml`. Neither lists the module yet.

## Run the checks
```
pip install -e modules/practice/field-training/backend[test]       # into the repo .venv
cd modules/practice/field-training/backend && python -m pytest -q  # throwaway SQLite, never a real database
pnpm --filter @eos/field-training typecheck && pnpm --filter @eos/field-training test
cd modules/practice/field-training/db && alembic upgrade head      # own tables and field_training_alembic_version only
```

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
