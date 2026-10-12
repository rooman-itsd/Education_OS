# student-information

**Domain:** student-lifecycle
**Kind:** feature
**Status:** planned

Student master record (SIS): profiles, documents, ID cards, status history.

## Scope
The Person system of record (SIS): profile, contact and guardian details, status history
(pending, active, suspended, graduated, withdrawn, alumnus), attached identity/supporting
documents, and ID card issuance. A Person record is created only by an authorised staff role
(registrar, or admissions staff with the permission) — never through public sign-up.

Explicitly not this module's responsibility: login credentials (`platform/identity`), raw file
storage (`platform/documents`), the admissions funnel (`admissions`), organisation onboarding and
sign-up (`web-portal-cms` + `platform/tenancy`), programme enrolment (`enrolment-registration`),
academic records (`academics/*`), or fee invoices (`finance-operations/fees-accounts`). See
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
