# rti

**Domain:** governance
**Kind:** feature
**Status:** in-progress (contracts proposed)

RTI request intake, assignment, tracking and responses.

## Scope
Owner: Madhumita (@madhumitha-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** recording RTI requests received by post, in person, by email or through an online portal, with the
applicant's details and fee metadata; assignment to an officer; referrals to internal custodians; responses, transfers
to other public authorities and closing; first appeals to the internal appellate authority; configurable due dates
worked out when read; the deadline list behind the Governance widget `rti.nearing-deadline`. Applicant personal data is
visible only to RTI officers and the appellate authority.

**Not in scope:** collecting fees (fees-accounts), a public online form or applicant self-service, attachments, second
appeals to outside bodies, messages to applicants, reminders and timers.

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
