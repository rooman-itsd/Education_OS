# search

**Domain:** platform
**Kind:** platform
**Status:** in-progress (backend built on the draft contracts; no module has opted in yet)

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
See `module.yaml`. This module must not import code from any other module under `modules/`. It imports
`eos_core`, `eos_identity` (the caller and its grants) and `eos_audit` (reindex requests); the event bus finds its
consumer through the `eos.event_consumers` entry point and nothing imports the bus.

## Setup
```bash
tools/scripts/py-setup.sh                     # the shared venv
.venv/bin/pip install -e platform/search/backend[test]
.venv/bin/python -m pytest platform/search/backend -q       # the in-memory engine; no cluster needed
```
The host does not mount search yet (`apps/backend/config/modules.enabled.yaml`); enabling it is a one-line change in
its own PR, once a module has opted in. Its Alembic chain is `platform/search/db` (version table
`search_alembic_version`); `cd platform/search/db && alembic upgrade head`.

## Configuration
Every key is `SEARCH_*` and is documented in [config/env.example](config/env.example). The ones that decide behaviour:

| Key | Meaning |
|---|---|
| `SEARCH_ENGINE` | `memory` (default in dev and CI) or `opensearch`. `memory` is **refused** when `EOS_DEV_MODE=false`. |
| `SEARCH_OPENSEARCH_URL`, `_USER`, `_PASSWORD`, `_VERIFY_CERTS`, `_TIMEOUT_SECONDS` | The cluster. A query that exceeds the timeout, or answers `timed_out`, is a 503. |
| `SEARCH_INDEX_ENVIRONMENT` | `dev`, `staging`, `prod`: part of every index name, so environments sharing a cluster cannot see each other. |
| `SEARCH_CURSOR_SECRET` | HMAC key of the cursors, at least 32 characters, required when `EOS_DEV_MODE=false`. |
| `SEARCH_MAX_QUERY_LENGTH`, `SEARCH_MAX_PAGE_SIZE`, `SEARCH_CURSOR_TTL_SECONDS` | Bounds; they can be lowered, never raised past the contract (200, 50, one hour). |
| `SEARCH_INDEX_ATTEMPTS`, `SEARCH_INDEX_RETRY_BACKOFF_SECONDS` | Indexing retries (3, doubling from 0.2 s) before a document is dead-lettered. |
| `SEARCH_REINDEX_BATCH_SIZE`, `SEARCH_REINDEX_MAX_DOCS_PER_SECOND` | Rebuild batch and throttle. |
| `SEARCH_JOB_RUNNER` | `inline` (the API process runs the job after answering; dev and CI) or `arq` (enqueue for `arq eos_search.worker.WorkerSettings`, Redis at `SEARCH_REDIS_URL`). |

The router refuses to import (so the host refuses to start) with the in-memory engine outside dev mode, an unknown
engine, or no cursor secret outside dev mode.

## How it works
- **Indexing.** `application/consumers.py` is registered on `eos.event_consumers`. For every trigger event a module
  declared, `application/indexer.py` asks that module's provider for the record's current document in the event's
  organisation and writes it with an external version taken from the event's `occurred_at`; a `delete` trigger removes
  the document without a call. `organisation_id` comes from the event envelope only (the one exception is
  `tenancy.organisation.purged`, whose envelope has none, so its payload id is used for the purge and nothing else).
  A failing provider or engine call is retried, then counted in `search_dead_letter` (visible in
  `GET /platform/health`); a reindex repairs and clears it.
- **Querying.** `application/query.py: build_query(caller, ...)` is the only way to a `Query`, and a `Query` refuses to
  exist without the organisation filter, `routing=<organisation_id>` and the permission filter
  (`read_any_of` holds a key the caller has, or `read_users` names the caller). Hits, `total`, facets and suggestions all
  come from that one filtered set. Both engines run the same body: `InMemoryEngine` evaluates it.
- **Engines.** `SearchEngine` (`application/ports.py`) has two implementations: `infrastructure/memory_engine.py`
  and `infrastructure/opensearch_engine.py` (opensearch-py). Mappings and analyzers: `infrastructure/mappings.py`.
- **Reindex.** `POST /reindex` creates a job (audited, one active job per organisation, module and type) and runs it
  in the background. If the live mapping is current, the organisation's documents are rewritten with a run stamp and the
  ones without it are deleted; if the declaration changed the mapping, a new `-v<n+1>` index is built for every
  organisation and the alias moves in one atomic request.
- **Purge.** `tenancy.organisation.purged` deletes the organisation's documents from every index, forgets its rows and
  publishes `search.organisation.purged`.

## What each first module must add (not done in this PR)
Search ships with the three first types as test fixtures, so its suite passes alone. For a type to be searchable in
the product, its owning module adds, in its own PR:

1. `contracts/searchable.yaml` (format in [docs/prd.md](docs/prd.md), decision 1). Ready-made declarations to start
   from are in `backend/tests/fixtures/searchable/`.
2. A provider, an object with `declaration` (the parsed YAML as a mapping, or a path to it), `get_document(organisation_id,
   type, record_id)` and `iter_documents(organisation_id, type, after_id, limit)`, registered in the module's
   `backend/pyproject.toml`:
   ```toml
   [project.entry-points."eos.search_documents"]
   knowledge-base = "eos_knowledge_base.search:PROVIDER"
   ```
   The entry-point name is the module name and must equal `module:` in the declaration. `type` is the short type name
   (`article`). Both methods run in the module's own code, with its own session, in the organisation's context, and
   return plain mappings, never an object of search (a module imports nothing from search):
   `{"record_id": "...", "fields": {<declared field>: value}, "read_any_of": [<declared key>] (optional, may only
   narrow), "read_users": [<user id>] (optional, at most 50)}`. `get_document` returns `None` when the record is gone
   or no longer searchable; it must also return `None` for an erased person. `iter_documents` returns documents in
   record-id order after `after_id`, up to `limit`.
3. Its trigger events must exist in its `contracts/events.yaml` and start with the module's name.

| Type | Module | Events to declare as triggers | Read permission |
|---|---|---|---|
| `student-information.person` | student-information | `person.created`, `.updated`, `.status-changed` (upsert), id field `person_id`. No erasure event exists (PRD open question 5) | `student-information:person:read` |
| `academic-management.course` | academic-management | `course.created`, `.updated` (upsert), `.archived` (delete), id field `course_id` | `academic-management:course:read` |
| `knowledge-base.article` | knowledge-base | `article.published` (upsert), `.archived` (delete), id field `article_id`; internal articles return `read_any_of: [knowledge-base:article:read-internal]` | `knowledge-base:article:read` |

Until a module does, `GET /types` is empty and nothing is indexed, by design.

## Tests
`backend/tests` (200 tests on the in-memory engine, 20 more that need a cluster). The engine **contract suite**
(`test_search_engine_contract.py`) runs against the fake always and against a real cluster when
`SEARCH_TEST_OPENSEARCH_URL` points at one (the tests marked `opensearch` are skipped otherwise):
```bash
docker run -d -p 9200:9200 -e discovery.type=single-node -e DISABLE_SECURITY_PLUGIN=true opensearchproject/opensearch:2
SEARCH_TEST_OPENSEARCH_URL=http://localhost:9200 .venv/bin/python -m pytest platform/search/backend -m opensearch
```
Analyzer behaviour (stemming, name folding and transliteration, relevance order) needs the `analysis-icu` plugin and is
not covered by the fake; the OpenSearch request building is unit-tested against a recording client without a network.

## Layout
| Path | Purpose |
|---|---|
| `docs/` | PRD, data model, integration points |
| `contracts/` | OpenAPI, event schemas, permission catalogue |
| `backend/` | Domain, application, infrastructure, API layers + tests |
| `frontend/` | Pages, components, API client + tests (not started) |
| `mobile/` | Mobile screens (optional) |
| `db/` | Migrations (own schema, version table `search_alembic_version`) |
| `config/` | `env.example` |
| `tests/e2e` | End-to-end tests runnable in isolation |

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
