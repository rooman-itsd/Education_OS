# knowledge-base

**Domain:** support
**Kind:** feature
**Status:** in-progress (contracts proposed)

Articles, FAQs and how-to guides for self-service.

## Scope
Owner: Madhumita (@madhumitha-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** articles, FAQs and how-to guides for every signed-in person, with `everyone` and `staff` audiences;
a two-level category tree and tags; drafts and immutable revisions with history and rollback; review, publish,
archive and restore; browse and full-text search (`GET /articles?q=`); helpful / not-helpful feedback; the usage
statistics behind the Support Staff widget `knowledge-base.top-articles`. Article ids are stable so helpdesk tickets
can link to them.

**Not in scope:** helpdesk tickets and their links (helpdesk), incidents and problems (incident-management), public
website pages and news (web-portal-cms), course content (lms), the library catalogue (library), the search engine and
file storage themselves (platform/search, platform/documents), attachments in v1, AI answers, translation.

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
