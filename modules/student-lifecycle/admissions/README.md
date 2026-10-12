# admissions

**Domain:** student-lifecycle
**Kind:** feature
**Status:** planned

Online application, document verification, merit lists, counselling and offers.

## Scope
The application funnel for one academic cycle: public/anonymous submission, document upload,
staff document verification and eligibility review, merit lists, offers, and offer accept/decline
(also anonymous, verified by reference number + email — no applicant account is created).

Explicitly not this module's responsibility: organisation onboarding or Organisation Admin
creation (`web-portal-cms` + `platform/tenancy` + `platform/billing`), creating a Person/Student
record (`student-information`, a manual staff action after acceptance), programme enrolment
(`enrolment-registration`), fee invoicing (`finance-operations/fees-accounts`, which consumes this
module's `accepted` event instead), or running portfolio/selection rounds themselves
(`practice/portfolio`, `practice/selection-process`, referenced by id only). See
[docs/prd.md](docs/prd.md) for the full scope.

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
