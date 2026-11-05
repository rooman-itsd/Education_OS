# search

**Domain:** platform
**Kind:** platform
**Status:** in-progress (contracts and PRD; no code yet)

Global and per-module search on OpenSearch, indexed from events, filtered by organisation and by what the caller may read.

## Scope
Search hosts the index and answers queries. A module opts in by declaring which of its records are
searchable and which permission reads each; search indexes them from the module's events and never
reads another module's tables. Every query is limited to the caller's organisation and to documents
the caller may read. Not in scope: ranking by personal behaviour, search over uploaded file contents,
the record itself (a hit links to the module's own screen), and the physical engine operations
(`infra/`). Full design and open questions: [docs/prd.md](docs/prd.md).

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
Follow [docs/architecture/module-standard.md](../../docs/architecture/module-standard.md#portability-checklist).
