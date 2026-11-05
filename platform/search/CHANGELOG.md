# Changelog — search

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Backend (issue #87, built on the draft contracts of PR #518): the `SearchEngine` port with an in-memory engine
  (default in dev and CI, refused outside dev mode) and `OpenSearchEngine`; indexing from events through
  `eos.event_consumers` and the new `eos.search_documents` provider entry point (external versions, retries, dead
  letters); `build_query(caller)` as the single query builder (organisation filter and routing, permission filtering
  before scoring, facets, counts, suggestions); every route of the draft openapi with signed expiring cursors and input
  bounds, 503 on an engine outage; reindex per organisation and module with stale-document cleanup and an alias swap for
  mapping versions; purge on `tenancy.organisation.purged`; entitlement copy from `tenancy.entitlement.changed`;
  Alembic chain `search_0001` (jobs, index state, entitlement copy, dead letters).
- Config keys added to `config/env.example`: `SEARCH_INDEX_ATTEMPTS`, `SEARCH_INDEX_RETRY_BACKOFF_SECONDS`,
  `SEARCH_JOB_RUNNER`, `SEARCH_REDIS_URL`, `SEARCH_JOB_STALE_SECONDS`.
- PRD and contracts (issue #87): API, events, permissions, config keys.
- Module scaffolded.
- PRD and contracts (issue #87): API, events, permissions, config keys. No implementation yet.
