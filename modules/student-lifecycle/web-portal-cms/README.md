# web-portal-cms

**Domain:** student-lifecycle
**Kind:** feature
**Status:** planned

Public website, CMS pages, announcements, news and notices.

## Scope
The organisation's public website: CMS pages, announcements/notices, and the organisation
sign-up page. The sign-up page composes `platform/billing`'s existing `GET /plans` and
`platform/tenancy`'s existing `GET /academy-types` / `POST /register` / `POST /register/verify`
directly — this module does not duplicate registration or plan logic, and never creates an
organisation, a plan, a Person/Student record, or an admissions application.

Explicitly not this module's responsibility: organisation registration and entitlement
(`platform/tenancy`), plans/subscriptions (`platform/billing`), creating a Person/Student record
(`student-information`, a manual staff action), or the admissions funnel (`admissions`, its own
anonymous flow). See [docs/prd.md](docs/prd.md) for the full scope.

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
