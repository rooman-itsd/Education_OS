# tournament-events

**Domain:** sports
**Kind:** feature
**Status:** planned

Tournaments, fixtures, results, officials and event logistics.

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
| `tournament-events.upcoming` | athlete | `tournament:read` | `GET /tournaments?status=ongoing` and `?status=published`, then per tournament shown (up to 5) `GET /tournaments/{id}/entries` and, where the athlete is entered, `GET /tournaments/{id}/fixtures?from=<today>` |
| `tournament-events.calendar` | coach | `tournament:read` | `GET /calendar?from=<today>&to=<today + 27 days>` |

`upcoming` lists ongoing, then not yet started, published tournaments (drafts and cancelled ones are never listed),
each marked entered (confirmed), entry pending, entries open (until `registration_closes_on`, inclusive) or entries
closed, and the athlete's next three fixtures (scheduled from now on, or in progress) in the tournaments they are
entered in. "Entered" relies on the backend narrowing the entry list to the athlete's own entries; the widget is
meant for the athlete layout only. `calendar` shows the next four weeks' published tournaments (ongoing ones
included) and their fixtures that are not cancelled, by time, eight rows and then a count; the backend caps the
period at 366 days. Both say "Tournament data is not available yet." with a retry while the API is missing.

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
