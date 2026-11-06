# productions

**Domain:** practice
**Kind:** feature
**Status:** in-progress

Productions and events: performances, exhibitions, recitals, screenings, hackathons, competitions, conferences.


## Scope

The generic "something is being put on" pattern (ADR-0004): a production with its dates and venue, the
parts people hold in it, and the preparation tasks behind it. One module serves every academy — a concert,
an exhibition, a screening, a hackathon, a moot court, a conference — and the profile vocabulary supplies
each one's word. `kind` is for display and filtering; no rule depends on it.

**Not this module:** booking the hall (`facilities/facility-booking`; a production may carry its
`resource_id`), costumes and equipment (`facilities/inventory-equipment`), marking a performance
(`academics/examinations`), auditions (`practice/selection-process`), ticketing (not planned for v1.0).

See [docs/prd.md](docs/prd.md) for the rules and [docs/user-stories.md](docs/user-stories.md).

## Dashboard widgets

| Widget | Permission | Endpoint |
|---|---|---|
| `productions.calendar` | `productions:production:read` | `GET /calendar` |
| `productions.upcoming` | `productions:production:read` | `GET /upcoming` |
| `productions.my-roles` | `productions:role:read-own` | `GET /my-roles` |
| `productions.in-preparation` | `productions:task:read` | `GET /in-preparation` |

## Running the tests

    tools/scripts/py-setup.sh
    .venv/bin/python -m pytest modules/practice/productions/backend -q
    pnpm --filter @eos/productions test

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
