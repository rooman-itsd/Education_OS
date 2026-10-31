# sports-facilities

**Domain:** facilities
**Kind:** feature
**Status:** in-progress (backend built; no dashboard widgets are planned for this module)

Registry of grounds, courts, pools, gyms and their usage.

## Scope
Responsible for: the registry of sports facilities (grounds, courts, pools, gyms, tracks, halls, ranges) and the
spaces inside them, weekly operating hours, availability (operational, limited, closed, under maintenance, with a
reason and an expected end), usage records and utilisation.

Not responsible for: booking and approving slots (`facility-booking`, which references facilities by id), repairs
(`maintenance`), equipment (`inventory-equipment`), fixed assets (`asset-management`), non-sports venues.

Requirements: [docs/prd.md](docs/prd.md).

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

## Backend
Python package `eos_sports_facilities` in `backend/src/`, in four layers:

| Layer | Path | What is in it |
|---|---|---|
| domain | `domain/rules.py` | Usage window, weekly slots, periods, hours open and hours in use. Pure Python. |
| application | `application/service.py` | Use cases; every state change publishes its event to the outbox and writes an audit entry in the same transaction. |
| infrastructure | `infrastructure/models.py`, `repository.py`, `config.py` | Tables (`sports_facilities_*`, `organisation_id` on every one), tenant-scoped queries, `SPORTS_FACILITIES_*` settings. |
| api | `api/router.py`, `deps.py`, `schemas.py` | `router: APIRouter`, mounted by the host under `/api/v1/sports-facilities`; token check and permissions. |

Rules the contract leaves to the module, as built:
- Dates are local dates in `SPORTS_FACILITIES_TIMEZONE` (default `Asia/Kolkata`); instants are stored in UTC.
- Facility names are unique in an organisation, space names in their facility (`400 duplicate_name`).
- Slots of one day may not overlap (`400 overlapping_slots`); a status `until` must be in the future (`400 until_in_past`).
- `GET /usage?from&to` returns the records that touch those local dates.
- Utilisation: `hours_used` is the time the facility was in use inside the period, so two groups at once count
  once; each `by_purpose` entry is counted the same way within its purpose, and only purposes with use are listed.
  Use outside the operating hours still counts, so `utilisation_pct` can pass 100.
- Usage may be recorded on a closed facility or an inactive space (for example maintenance work, or a past use).
- Until the audit SDK ships, `sports_facilities_audit_entry` holds the audit trail (shaped like platform/audit's record).

Run the tests alone (they always use a throwaway SQLite file, never a real database):

```bash
pip install -e packages/core -e packages/testing -e "modules/facilities/sports-facilities/backend[test]"
cd modules/facilities/sports-facilities/backend && python -m pytest
```

Migrations (own chain, own version table `sports_facilities_alembic_version`; RLS policies on Postgres):

```bash
cd modules/facilities/sports-facilities/db && alembic upgrade head   # uses EOS_DATABASE_URL
```

### Needs from the host repo
- `packages/core` (`eos_core`) and, for tests, `packages/testing` (`eos_testing`).
- `facilities/sports-facilities` is listed in `apps/backend/config/modules.enabled.yaml`, which mounts
  `eos_sports_facilities.api.router:router` under `/api/v1/sports-facilities` behind the entitlement gate, and in
  `apps/frontend/config/modules.enabled.yaml` (its widgets list is empty).
- Users hold the sports-college profile roles granted in `contracts/permissions.yaml` (`facility-staff`, `org-admin`,
  `coach`, `athlete`) or the module roles.

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
