# facility-booking

**Domain:** facilities
**Kind:** feature
**Status:** in-progress (backend and widgets built; enabled in `apps/backend` and `apps/frontend`)

Generic resource-booking pattern (ADR-0004). People find a bookable resource, see when it is free and book it, with optional approval. Each academy names the resource in its profile vocabulary (`facility-booking.resource`), for example "Practice room", "Lab / skills room" or "Edit suite / studio".

## Scope
Responsible for: resource types and resources, opening hours and closures, availability,
single and recurring bookings, approval, conflict prevention, check-in and no-show.

Not responsible for: sports grounds (`sports-facilities`), fixed assets (`asset-management`),
repairs (`maintenance`), lending movable items (`inventory-equipment`), class timetables
(`timetable-attendance`). Those modules may book through this module's API.

Requirements: [docs/prd.md](docs/prd.md). Stories: [docs/user-stories.md](docs/user-stories.md).

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
Python package `eos_facility_booking` in `backend/src/`, in four layers:

| Layer | Path | What is in it |
|---|---|---|
| domain | `domain/rules.py` | Booking rules, conflicts, recurrence, availability. Pure Python. |
| application | `application/service.py`, `jobs.py` | Use cases; every state change publishes its event to the outbox. Scheduler sweeps (no-show, completed). |
| infrastructure | `infrastructure/models.py`, `repository.py`, `config.py` | Tables (`facility_booking_*`, `organisation_id` on every one), tenant-scoped queries, `FACILITY_BOOKING_*` settings. |
| api | `api/router.py`, `deps.py`, `schemas.py` | `router: APIRouter`, mounted by the host under `/api/v1/facility-booking`; token check and permissions. |

Run the tests alone (they always use a throwaway SQLite file, never a real database):

```bash
pip install -e packages/core -e packages/testing -e "modules/facilities/facility-booking/backend[test]"
cd modules/facilities/facility-booking/backend && python -m pytest
```

Migrations (own chain, own version table `facility_booking_alembic_version`; RLS policies on Postgres):

```bash
cd modules/facilities/facility-booking/db && alembic upgrade head   # uses EOS_DATABASE_URL
```

### Needs from the host repo
- `packages/core` (`eos_core`) and, for tests, `packages/testing` (`eos_testing`).
- `facilities/facility-booking` in `apps/backend/config/modules.enabled.yaml` mounts
  `eos_facility_booking.api.router:router` under `/api/v1/facility-booking`, and in
  `apps/frontend/config/modules.enabled.yaml` registers the widgets (both since #288).
- Users need the module roles (`facility-booking-user`, `-approver`, `-manager`) in their token roles, or an
  identity mapping from academy roles to them.
- A scheduler that calls `application.jobs.run_sweeps` every few minutes, until `platform/scheduler` exists.

## Frontend
`frontend/src/widgets/index.ts` exports the dashboard widgets; the role layouts in `platform/identity/config/dashboards/`
place them by id, and the shell titles them with the academy's vocabulary.

| Widget | Dashboards | Endpoint | Permission |
|---|---|---|---|
| `facility-booking.bookings` | coach, medical-staff | `GET /bookings?scope=managed&from=now` | `facility-booking:booking:read` |
| `facility-booking.bookings-today` | facility-staff and 13 instructor and lead roles | `GET /bookings?scope=managed&date=today`, `GET /summary` | `facility-booking:booking:read` |
| `facility-booking.my-bookings` | 10 learner and performer roles (musician, dancer, actor, ...) | `GET /bookings?scope=mine&from=now` | `facility-booking:booking:read` |

- **bookings** and **my-bookings** list bookings not yet over (pending, confirmed, checked in), earliest first, six at
  a time with "N more upcoming": day ("Today", "Tomorrow", "Fri 31 Oct"), time window, resource and status in words.
  `bookings` covers the resources the viewer approves; `my-bookings` the viewer's own, booked by or for them.
- **States:** loading, empty, and error with a retry when trying again can help; until the backend answers, the error
  reads "Booking data is not available yet." 401 and 403 offer no retry.
- **Read-only for now:** the cancel and check-in actions the PRD lists for these rows (driven by `Booking.can`), and
  whether `bookings` also shows the viewer's own bookings, come in #421.
- **Data:** `src/api/client.ts`, a hand-written typed client that the generated client will replace.
- **Tests:** `cd modules/facilities/facility-booking/frontend && pnpm test` (vitest and Testing Library).

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
