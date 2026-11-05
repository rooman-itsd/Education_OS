# integration-hub

**Domain:** platform
**Kind:** platform
**Status:** contracts proposed (v0.2.0); not built

The one place Education OS meets outside systems. Modules call a **port**; the hub runs the call on the organisation's
enabled **connection** for that port; an **adapter** in `integrations/` speaks to the provider. No module talks to a
vendor, so changing provider is configuration, not code (`integrations/README.md`, "Swap rule").

## Scope
- Ports, one per kind of integration: [`contracts/ports/`](contracts/ports/) (certificate-issuance, academic-records,
  regulatory-submission, meetings, wearable-data, inter-institution-records), plus the contract every adapter
  implements ([`adapter.yaml`](contracts/ports/adapter.yaml)).
- Connections per organisation: settings, credentials in a secret store (never the database), mock, sandbox and live.
- OAuth for organisations and for people linking their own accounts.
- Provider callbacks: signature verification, handshakes, deduplication, acknowledge first.
- Delivery log, retries with backoff, dead letters; health checks.

Not: provider protocols (the adapters), the decision to issue, schedule or file (the modules), email and SMS
(`platform/notification` and `messaging-providers`), payments (`payment-sbiepay`). See [docs/prd.md](docs/prd.md).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)
- Ports: [contracts/ports/](contracts/ports/), called through `packages/sdk` (`integrations.invoke`)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/` or `integrations/`;
adapters are found by the `eos.integration_adapters` entry point.

## Layout
| Path | Purpose |
|---|---|
| `docs/` | PRD, user stories, data model, screen list |
| `contracts/` | OpenAPI, event schemas, permission catalogue, ports |
| `backend/` | Domain, application, infrastructure, API layers + unit tests |
| `frontend/` | Pages, components, API client + tests |
| `mobile/` | Mobile screens (optional) |
| `db/` | Migrations and seed data, own schema only |
| `config/` | `env.example`, feature flags |
| `tests/e2e` | End-to-end tests runnable in isolation |

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../docs/architecture/module-standard.md#portability-checklist).
