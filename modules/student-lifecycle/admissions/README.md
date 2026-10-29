# admissions

**Domain:** student-lifecycle
**Kind:** feature
**Status:** in progress (backend, widgets and Track page built; see "What the host must provide")

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

| Widget | Kind | Permission | Data |
|---|---|---|---|
| `admissions.funnel` | chart | `admissions:report:read` | `GET /reports/funnel` |
| `admissions.application-status` | list | `admissions:application:read` | `GET /applications` |
| `admissions.pending-documents` | list | `admissions:document:verify` | `GET /documents?verification_status=pending` |

The frontend also exports `TrackApplicationPage` (`<TrackApplicationPage orgSlug="..." />`), the applicant's public
view of their application by reference number and email.

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`. It uses
`packages/core` (database, tenant scoping, outbox events, row-level-security policy) and, in tests,
`packages/testing`.

## What the host must provide
- **Public routes through the gateway.** `apps/backend`'s entitlement gate must let
  `/api/v1/admissions/public/{org_slug}/*` through without a token, after resolving the slug to an active
  organisation entitled to admissions (404 otherwise), and set `request.state.organisation_id`. Until it does,
  the five public routes answer 401 behind the gateway. See [docs/integration-points.md](docs/integration-points.md).
- **A public page for tracking.** `apps/frontend` mounts `TrackApplicationPage` on the public site (for example
  `#/apply/{org_slug}/track`).

## Run and test
```
.venv\Scripts\python.exe -m pytest modules/student-lifecycle/admissions/backend/tests
pnpm --filter @eos/admissions test
pnpm --filter @eos/admissions typecheck
cd modules/student-lifecycle/admissions/db && alembic upgrade head    # uses EOS_DATABASE_URL
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
