# sports-nutrition-health

**Domain:** sports
**Kind:** feature
**Status:** planned

Diet plans, medical records, injury tracking, physio sessions.

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
| `sports-nutrition-health.nutrition-plan` | athlete | `plan:read` | `GET /nutrition-plans?status=active` (the athlete's own plans) |
| `sports-nutrition-health.injured-athletes` | medical-staff | `injury:read` | `GET /injuries?status=active`, `GET /injuries?status=recovering` |
| `sports-nutrition-health.appointments-today` | medical-staff | `appointment:read` | `GET /appointments?on=<UTC day>`, once or twice |
| `sports-nutrition-health.athletes-on-plans` | nutritionist | `plan:read` | `GET /nutrition-plans?status=active` |
| `sports-nutrition-health.plan-reviews-due` | nutritionist | `plan:read` | `GET /nutrition-plans?status=active&review_due_before=<today + 7 days>` |

Athletes are referenced by id only and this module has no endpoint that names them, so rows show a short id
("Athlete 3f2a9c7e"); a widget does not call athlete-performance for names. No widget shows an injury's clinical
notes or an appointment's notes: the client drops them before a widget sees the row.

`?on=` is a UTC calendar day, while "today" is the viewer's local day. A local day overlaps two UTC days unless the
viewer is on UTC (in India, 00:00 to 05:30 local is the previous UTC day), so appointments-today asks for each UTC
day the local day overlaps and keeps the appointments between local midnight and midnight. It lists the whole
organisation's appointments, not only the viewer's own (the widget does not know the viewer's user id).
List widgets load one page of 200 per request (the contract maximum); athletes-on-plans says so when more active
plans exist than it loaded.

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
