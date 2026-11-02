# Changelog — documents

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
### Added
- Implemented core domain model `Document` with status state machine (`pending_upload`, `available`, `archived`, `deleted`), file size bounds, MIME type allowlist, and dangerous executable file extension blocks.
- Storage abstraction via `StoragePort` protocol with implementations for MinIO (`MinioStorage`) and in-memory mock (`MemoryStorage`).
- Application service layer (`eos_documents.application.service`) supporting upload intent generation, upload confirmation with storage verification, presigned download URL creation, metadata retrieval, filtering/listing, soft deletion, and outbox event publishing.
- Added database migration `documents_0001` with PostgreSQL Row Level Security (`rls.POLICY`) and `ix_documents_document_organisation_id` index.
- Added FastAPI routes under `/api/v1/documents` (`/upload-intent`, `/{id}/confirm`, `/{id}`, `/{id}/download-url`, `/`, `DELETE /{id}`) with strict permission enforcement via `require(...)`.
- Defined contracts: OpenAPI 3.1 specification (`contracts/openapi.yaml`), event schemas (`contracts/events.yaml`: `documents.document.uploaded`, `documents.document.deleted`), and permission catalogue (`contracts/permissions.yaml`).
- Configured environment variables template in `config/env.example` for MinIO endpoints, credentials, bucket names, and URL expiry.
- Implemented frontend client `@eos/documents` with typed API client, human-readable file size formatters, error handling, and unit test suite.
- Registered `documents` platform service in `apps/backend/config/modules.enabled.yaml`.
- Added comprehensive test suite: domain model tests, storage port tests, application service tests, API route tests, Alembic migration round-trip tests, and PostgreSQL RLS tenant isolation tests.
