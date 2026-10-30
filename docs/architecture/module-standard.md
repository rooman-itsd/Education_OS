# Module Standard

What every module under `modules/`, `platform/` and `integrations/` must look like, and the
checklist that makes it portable to another repo.

## Anatomy

```
<module>/
├── module.yaml            manifest: name, kind, tier, field, owners, dependencies, exposed contracts
├── README.md              scope, public surface, layout
├── CHANGELOG.md           semver per module
├── docs/                  prd, user-stories, data-model, screens, integration-points
├── contracts/
│   ├── openapi.yaml       the ONLY way other modules call this one synchronously
│   ├── events.yaml        the ONLY way other modules learn what happened here
│   └── permissions.yaml   permission keys and default roles, registered with identity
├── backend/
│   ├── src/domain/        entities, value objects, domain rules. No framework imports
│   ├── src/application/   use cases, orchestrating domain + ports
│   ├── src/infrastructure/ repositories, SDK clients, adapters implementing ports
│   ├── src/api/           HTTP handlers mapping contracts to use cases
│   └── tests/             unit + integration tests
├── frontend/
│   ├── src/pages/         route-level screens
│   ├── src/components/    module-local components (shared ones go to packages/ui-kit)
│   ├── src/api/           generated client from contracts/openapi.yaml
│   ├── src/widgets/       dashboard widgets (DashboardWidget[] from packages/ui-kit)
│   └── tests/
├── mobile/src/            optional mobile screens
├── db/
│   ├── migrations/        own schema only, forward-only, timestamped
│   └── seeds/             demo / test data
├── config/env.example     every env key, prefixed with the module name
└── tests/e2e/             runs against the module alone plus platform stubs
```

## Hard rules

1. **No code imports across modules.** Only `packages/*` and the module's own folder.
2. **One schema per module.** No foreign keys to another module's tables.
3. **Contracts first.** API, events and permissions are written before code and reviewed as a PR.
4. **Platform via SDK.** Identity, notification, documents, workflow, audit, search, scheduler and
   events are reached through `packages/sdk`, never through their internals.
5. **Config is declared.** Every env key appears in `config/env.example` and is prefixed `<MODULE>_`.
6. **Tests run alone.** The module's test suite passes with only `packages/` and platform stubs available.
   Tests that need a second real module belong in the repo-level [`tests/`](../../tests/) folder, not in the module.
7. **Semver per module.** Breaking a contract bumps the major version and is recorded in CHANGELOG.
8. **Manifest is truth.** `module.yaml` lists every dependency. CI will fail a module that imports
   something it did not declare.
9. **Tier is declared.** `tier: core | common | specialized`, with `field:` for specialized. A common
   module must not assume one field; its labels come from the profile vocabulary. See ADR-0004.
10. **Enabled means entitled.** A module is on for an organisation only if its entitlement (profile ∩ plan,
   ADR-0005) includes it. Nothing in a module may depend on another module being enabled; it reacts to events if they come.
11. **Tenant-aware from the first migration.** Every table has `organisation_id` with a row-level-security
   policy on `app.organisation_id`; every query is scoped; every event carries `organisation_id`; documents,
   search and cache keys are prefixed by organisation. The cross-tenant leak test from `packages/testing` runs in the module's suite.

## Permission catalogues

`contracts/permissions.yaml` declares the module's keys (`<module>:<resource>:<action>`) and which
roles are granted them. The platform reads every catalogue (`eos_core.config.permissions_for`);
a module never computes permissions itself. A module grants its own
roles (`<module>-learner`, `-reviewer`, `-coordinator`, ...), not each academy's. The layout of each profile role
(`platform/identity/config/dashboards/<role>.yaml`) lists which module roles that role holds in `module_roles`,
and a role whose layout `extends: student` or `extends: faculty` also inherits that role's grants and
`module_roles` (ADR-0004, "Role inheritance"). Name an academy role in the catalogue only to give it more than
its layout grants it. A catalogue that grants no role at all leaves its widgets unbacked.
The host test `apps/backend/tests/test_role_inheritance.py` checks that every dashboard widget of a
module with a catalogue is backed by a key the layout's role holds.

## Portability checklist

Set `portable: true` in `module.yaml` only when all of these pass:

- [ ] `grep` for imports shows nothing outside the module folder and `packages/`
- [ ] All platform calls go through `packages/sdk`
- [ ] Migrations create and use only the module's own schema
- [ ] `config/env.example` is complete; module boots with those keys and nothing else
- [ ] `tests/e2e` passes with platform stubs from `packages/testing`
- [ ] `contracts/` fully describes every endpoint, event and permission
- [ ] README states what the module needs from the host repo (which packages, which platform services)
- [ ] No reference to university-specific names in code; those live in config and reference data
- [ ] No field-specific words in a `common` module; terms come from the profile vocabulary
- [ ] Every table has `organisation_id` and an RLS policy; the cross-tenant leak test passes

## Moving a module to another repo

1. Copy the module folder.
2. Add `packages/contracts`, `packages/core`, `packages/sdk` as dependencies (published packages or vendored).
3. Provide the platform services listed in `module.yaml` → `depends_on.platform`, or stubs from `packages/testing`.
4. Register the module in the host app's `modules.enabled.yaml`.
5. Run migrations, seed reference data, run `tests/e2e`.

## Naming

| Thing | Convention | Example |
|---|---|---|
| Module folder | kebab-case noun | `facility-booking` |
| DB schema | snake_case module name | `facility_booking` |
| API base path | `/api/v1/<module>` | `/api/v1/facility-booking` |
| Event | `<module>.<entity>.<past-verb>` | `facility-booking.booking.approved` |
| Permission | `<module>:<resource>:<action>` | `facility-booking:booking:approve` |
| Env var | `<MODULE>_<KEY>` | `FACILITY_BOOKING_MAX_DAYS_AHEAD` |

## Stack mapping (ADR-0002)

| Module path | Technology | Entry point |
|---|---|---|
| `backend/` | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, pytest | `backend/src/api/router.py` exports `router: APIRouter` |
| `frontend/` | React, TypeScript, Vite, Vitest | `frontend/src/index.ts` exports `routes` and `widgets` |
| `mobile/` | React Native (proposed) | `mobile/src/index.ts` exports `screens` |
| `db/migrations` | Alembic, one version chain per module, own schema only, `organisation_id` + RLS on every table. Until the first chain exists, `eos_core.init_db()` creates tables and applies the RLS policies at startup | `db/alembic.ini` |
| `contracts/` | OpenAPI 3.1 → Pydantic + TS types via `packages/contracts` | — |
| `tests/e2e` | pytest (API) + Playwright (UI) against platform stubs | — |

`apps/backend` includes every enabled module's `router` under `/api/v1/<module>`.
`apps/frontend` mounts every enabled module's `routes` and registers its `widgets` with the dashboard shell.
