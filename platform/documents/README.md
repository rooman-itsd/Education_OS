# documents

**Domain:** platform
**Kind:** platform
**Status:** in-progress

Document and media management: storage abstraction, presigned upload/download URLs, metadata catalog, access control.

## Scope
- **Responsible for:** Document metadata catalog (`Document`); storage port abstraction (`StoragePort`) with MinIO and in-memory test implementations; presigned upload intent (`/upload-intent`) and confirmation (`/{id}/confirm`); presigned download URL generation (`/{id}/download-url`); document listing and filtering by entity/status; soft deletion and storage object purging; outbox event publishing (`documents.document.uploaded`, `documents.document.deleted`); organisation-level tenant isolation enforced by PostgreSQL RLS (`documents_document`); MIME type validation and executable extension blocking; frontend typed API client and helpers (`@eos/documents`).
- **Explicitly NOT:** Document content parsing or OCR extraction; document version diffing; approval lifecycle or signature chains (`platform/workflow`); event audit trails (`platform/audit`); arbitrary filesystem access or bypassing storage authorization.

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
