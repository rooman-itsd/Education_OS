# Changelog — selection-process

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [0.1.0] - 2026-10-31
### Added
- Complete generic selection-process domain, database schema, and Alembic initial migration `selection_process_0001`.
- PostgreSQL RLS policies and multi-tenant constraints for process types, processes, stages, panels, candidates, decisions, and slots.
- Duplicate candidate registration protection (database unique constraint + HTTP 409 `duplicate_candidate`).
- Multi-panelist decision uniqueness per candidate per stage (database unique constraint + HTTP 409 `already_decided`).
- Outbox event emission for candidate registration, decisions, withdrawal, and final outcomes.
- FastAPI REST API mounted at `/api/v1/selection-process` matching OpenAPI 3.1 contract.
- Four frontend dashboard widgets: `selection-process.my-applications`, `selection-process.open-calls`, `selection-process.to-judge`, and `selection-process.upcoming`.
- Enabled module configuration across backend and frontend.
