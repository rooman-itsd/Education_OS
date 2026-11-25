# Changelog — documents

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
Contract 0.2.0 (additive): versions, `include_superseded`, 409 on a replayed intent after confirm.

### Security
- Hardened upload constraints, pending upload cleanup, deletion privacy, and permissions (security review, November 2026, N11):
  - `/upload-intent` and `/{id}/versions` now issue signed POST policy credentials (`method: "POST"`, `upload_fields`) binding `key`, `Content-Type`, and `content-length-range` into MinIO's signature rather than an unconstrained presigned PUT URL.
  - Added hourly `documents.sweep-pending-uploads` scheduler job (`scheduler.job.due` consumer, `DOCUMENTS_PENDING_UPLOAD_TTL_SECONDS`, default 3600s) to remove abandoned `pending_upload` objects from storage and mark rows deleted.
  - `delete_document` and the pending-upload sweep now blank `filename`, `title`, and `tags` (and publish an empty `filename` on `documents.document.deleted`) so `?status=deleted` retains no sensitive document names.
  - Removed `documents:document:read-any` from `department-admin` in `contracts/permissions.yaml` so org-wide document reading stays restricted to `org-admin`.
- Delete stored files on organisation purge: subscribe to `tenancy.organisation.purged`, remove all objects under
  the organisation's prefix in object storage, and publish `documents.organisation.purged` (security review,
  November 2026, N9, #676). The purge removes every version and delete marker of those objects, so a versioned bucket
  keeps no earlier version of a purged organisation's file.

### Fixed
- A confirmed file can no longer be overwritten (#317 follow-up). A replayed upload intent handed out a fresh PUT
  URL for the document's own storage key even after confirm, and the original URL (valid 15 minutes) named the same
  key: the audit overwrote a confirmed 9-byte PDF with 60 MB of HTML. Each upload now goes to a key of its own
  (`upload_path`, migration `documents_0002`); confirm validates it, copies it to `storage_path` and deletes it, so
  a late PUT lands where nothing reads. A replay after confirm answers 409. Confirm locks the row, so concurrent
  confirms run one at a time. Pending rows from before the migration still confirm from `storage_path`.

### Added
- Versions: `POST /{id}/versions` (next version of the latest confirmed one, by the first version's uploader) and
  `GET /{id}/versions` (newest first). Every version is a row (`version`, `version_of`, `superseded_by`); confirming
  a new version supersedes the previous one, which stays readable. Lists show each document's latest version
  unless `include_superseded=true`. Two new versions racing from one predecessor: the second confirm is refused.
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
