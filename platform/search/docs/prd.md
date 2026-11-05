# search - PRD

Owner: Himanshu (@himanshu-rooman) · Backups: Faizan, Srujan · Tier: core · Issue: #87 · Status: contracts for review

## What this is

One search box for the whole product. A person types a name, a course code or a phrase and gets
the students, courses and articles they are allowed to see, grouped by type, in their own
organisation only. A module can also embed a search of just its own records.

`ARCHITECTURE.md` says "search indexes are owned by the module that publishes the data;
`platform/search` only hosts them". This PRD keeps that sentence true: the module decides what is
searchable and who may read it, search keeps the index and enforces the filter.

## What it is explicitly NOT

| Not this | That belongs to |
|---|---|
| Reading another module's tables | Forbidden (module standard, rule 2). Search learns from events and from the module's own provider |
| The record itself | The owning module. A hit is a title, a few display fields and a link |
| Full-text search inside uploaded files (PDF, Word) | Out of scope for v1.0; open question 7 |
| Per-module list filtering such as "students in section A" | The module's own list endpoint, which reads its own database |
| Running the engine (nodes, backups, upgrades) | `infra/` |
| Recommendations or ranking by a person's behaviour | Not planned. Ranking is text relevance only |

## Design decisions

### 1. Indexing: events trigger, the module's provider supplies the document

Event payloads are deliberately thin (`course.updated` carries only `changed_fields`), and search
may not read a module's tables, so the event alone cannot build a document. Pushing whole records
through the bus would break the payload rules ("never the whole entity"). The design:

1. A module opts in by shipping `contracts/searchable.yaml` (format below) and registering a
   **document provider** on a new entry-point group `eos.search_documents` in its
   `backend/pyproject.toml`, the same mechanism as `eos.event_consumers`.
2. The declaration names **trigger events**, each with an action: `upsert` or `delete`, and which
   payload field holds the record id. Search subscribes to those events through the bus like any
   consumer.
3. On an `upsert` trigger, search calls the module's provider with `(organisation_id, type, id)` in
   the event's organisation context. The provider runs in the module's own code with its own
   session and row-level security, and returns a `SearchDocument` or `None` (record gone or no
   longer searchable: search deletes it). Search never learns the module's schema.
4. A `delete` trigger removes the document without calling the provider.

Because the provider reads the record's state at processing time, delivery that is repeated or out
of order is harmless: the last processed event writes the current state. Writes also carry an
external version (the event's `occurred_at`), so a late older event cannot overwrite a newer
document. A failing provider call retries with backoff; after the last retry the document goes to a
dead-letter count (visible in `/platform/health`) and a reindex repairs it.

The provider entry point is the one new platform contract this adds. It is a function the module
implements, not an import by search, so rule 1 holds. The same provider's `iter_documents(
organisation_id, type, after_id, limit)` feeds backfill and reindex (decision 6).

**Alternative considered:** the module's own consumer calls `search.upsert(document)` through the
SDK. Simpler and one fewer entry point, but every module then writes its own event handling and
retry logic, and search cannot rebuild an index without asking the module anyway. Open question 1.

#### The declaration (`contracts/searchable.yaml` in the owning module)

```yaml
module: knowledge-base
types:
  - name: article                         # type key becomes knowledge-base.article
    label: Articles                       # from the profile vocabulary, not hard-coded academy words
    url: /support/knowledge-base/{id}
    triggers:
      - { event: knowledge-base.article.published, action: upsert, id_field: article_id }
      - { event: knowledge-base.article.archived,  action: delete, id_field: article_id }
    fields:
      title:   { kind: text,    analyzer: english,  boost: 3, role: title }
      body:    { kind: text,    analyzer: english,  snippet: true }
      slug:    { kind: keyword, display: true }
      type:    { kind: keyword, filterable: true, display: true }
      category_id: { kind: keyword, filterable: true }
    read_permissions:                     # see "Permission filtering"; the document gets one of these
      any_of: [knowledge-base:article:read]
```

`kind` is one of `text`, `keyword`, `date`, `number`, `boolean`. `analyzer` is chosen from the
closed list search owns (decision 5), so a module cannot ship an arbitrary analyzer. Search
validates a declaration at start-up and refuses a type with an unknown analyzer, a field set
without `role: title`, or no `read_permissions` (fail closed).

### 2. Tenancy

- Every document has `organisation_id`, set by search from the event envelope, **never by the
  provider** and never from the payload. A provider that returns a document for another
  organisation is a bug the indexer rejects (the provider is called inside the event's
  organisation context, and the returned id is checked).
- The document id is `<organisation_id>:<type>:<record id>`, so two organisations whose records
  share an id cannot overwrite one another.
- Every request is built by one function, `build_query(caller, ...)`, whose `caller` argument is
  required and carries the organisation and the grants. It always adds a `term` filter on
  `organisation_id` and sets `routing=<organisation_id>`. There is no code path that queries
  without it, and the port (decision 7) takes a `Caller`, not a bare query. Suggestions, facet
  aggregations and counts go through the same function.
- `organisation_id` is never a request parameter, except in the super admin reindex body.
- The cross-tenant leak test from `packages/testing` runs against the memory engine and the real
  one: organisation A indexes a record with a unique word, organisation B searches for it and
  gets zero hits, zero facet count, zero suggestions and a total of 0.
- A module the organisation is not entitled to (ADR-0005; `tenancy.entitlement.changed`) is
  excluded at query time, so switching a module off hides its records on the next request without
  waiting for a reindex.

### 3. Permission filtering, and how titles do not leak

A search hit is a disclosure on its own: a title such as "Disciplinary review: A. Kumar" leaks even
if the link is refused. So the rule is: **a document the caller may not read must not be matched,
scored, counted, suggested or faceted. It is excluded in the engine's filter, never trimmed after
the fact.**

How:

1. Each document carries `read_any_of`: a list of permission keys, copied from the declaration's
   `read_permissions`. A provider may narrow it per document (for example the knowledge-base
   provider returns `[knowledge-base:article:read-internal]` for an internal article, and
   `[knowledge-base:article:read]` for a public one), but may only use keys declared on that type.
2. A document may also carry `read_users`: user ids who may read it regardless of permissions
   (the owner of an uploaded document, a student reading their own record). Optional.
3. At query time search asks identity for the caller's grant set once per request (cached for the
   request only; a role change takes effect on the next request) and adds a filter:
   `read_any_of` contains any key the caller holds **or** `read_users` contains the caller's
   user id. A document with an empty `read_any_of` and no `read_users` matches nobody (fail
   closed).
4. The filter sits in the engine's `filter` context with the organisation filter, so it applies to
   hits, `total`, facet aggregations and suggestions alike. Counts are therefore not an oracle
   ("3 results" for something you may not see); a caller who may read nothing of a type gets no
   facet for it, and `GET /types` omits the type.
5. Nothing per-user is stored in the index. A role change is effective on the next query with no
   reindex. What the index stores is only the permission needed, so the permission catalogue stays
   the one source of truth.
6. Search never returns a record by id, so there is no "exists but forbidden" answer to probe. A
   404 on `/modules/{module}/query` means the module is not enabled or has no searchable types,
   the same answer for everyone.

What this does not cover, deliberately: row-level rules a permission key cannot express ("faculty
may read only students of their own sections"). The module must either publish the record with
`read_users` listing the allowed users, or not make the type searchable. Open question 2.

Snippets come only from fields the module marked `snippet`, so a field that is more sensitive than
the title (a student's phone number, an applicant's score) is never excerpted. Highlight markers are
two private-use characters, not HTML.

### 4. First modules to be searchable

Chosen from what is merged today and has events:

| Type | Module | Why | Read permission |
|---|---|---|---|
| `student-information.person` | student-information | The most-searched thing in any academy. Events `person.created`, `.updated`, `.status-changed` exist. Display: name, status. Never email or phone | `student-information:person:read` |
| `academic-management.course` | academic-management | `course.created`, `.updated`, `.archived` exist. Low sensitivity, so it proves the pipeline first | `academic-management:course:read` |
| `knowledge-base.article` | knowledge-base | `article.published`, `.archived` exist. Two audiences, so it proves the per-document permission filter | `knowledge-base:article:read` or `:read-internal` |

Wave 2, each waiting on something named:

| Type | Waiting on |
|---|---|
| Library titles | library publishes no catalogue event (`title.*`); needs `library.title.created/updated/removed` |
| Documents (metadata: name, kind) | `documents.*` events have no payload declared; needs one, and an owner ACL via `read_users` |
| Applicants | PII-heavy; needs a decision on who may see applicants in a global box and a retention rule for rejected applicants |
| Staff | hr-payroll `employee.*` exist; needs a decision to expose names and department only |
| Helpdesk tickets | events not reviewed yet |

Nothing is searchable until its module merges a declaration; search itself ships with the three
above as test fixtures inside `platform/search/tests`, so its suite passes alone.

### 5. Mappings and analyzers

- Dynamic mapping is `strict`. Only declared fields exist.
- Every document has the same envelope fields: `organisation_id` (keyword), `type`, `module`,
  `record_id`, `title` (text + `search_as_you_type` sub-field for suggestions), `read_any_of`,
  `read_users` (keyword), `indexed_at`, `source_version`, plus the module's declared fields.
- Search owns the analyzer list: `english` (default text), `name`, `code`, `keyword_lower`.
- `name` is for people: lower-case, ASCII-fold (ICU folding), edge n-grams from 2 to 15
  characters for prefix match as you type, so "pri" finds "Priya".
- `code` keeps case-insensitive whole tokens and splits on punctuation: "CS-101" matches "cs101"
  and "CS 101".
- **Indian names and transliteration is the hard part and is an open question (3).** The same
  person is written "Mohammed/Muhammad/Mohd", "Vijay/Vijaya", "Shreya/Sreya", or in Devanagari or
  Tamil script. v1.0 proposes ICU folding plus a small, reviewed synonym list of common name
  variants and an ICU `Devanagari-Latin` transform for Hindi; other scripts are not promised.
  Phonetic matching (Double Metaphone is tuned for English) is rejected for v1.0.
- Changing a mapping is a new versioned index and a reindex (decision 6), never an in-place edit.

### 6. Operations: index layout, backfill, retention

**Index naming and layout: one shared index per type per environment, routed by organisation.**

- Name `eos-<environment>-<module>-<type>-v<n>`, for example `eos-prod-knowledge-base-article-v1`,
  with a write and read alias `eos-prod-knowledge-base-article` that queries use. `<environment>` is
  `SEARCH_INDEX_ENVIRONMENT` (`dev`, `staging`, `prod`), so environments sharing a cluster cannot
  see one another.
- Every document is written and queried with `routing = organisation_id`, so a tenant's documents
  live on one shard and a query touches one shard.
- Why not an index per organisation per type: the product targets many small academies. Hundreds
  of tenants times tens of types is thousands of tiny indexes and shards, which is the failure mode
  of OpenSearch clusters (cluster state, heap per shard), and a mapping change becomes thousands of
  reindexes. A shared index with a mandatory organisation filter and routing is the standard
  answer, and decision 2 puts the filter in one place with a leak test. The trade-off accepted: the
  isolation is application-enforced, not engine-enforced. If an organisation ever needs hard
  isolation (a contract term, or size), the layout allows a dedicated index behind the same alias
  scheme; open question 4.
- ARCHITECTURE.md's "search indexes are prefixed by organisation": satisfied by document id,
  routing key and filter, not by the index name. Flagged for the lead to confirm (open question 4).

**Reindex and backfill.** `POST /reindex` for a module (optionally one type) in an organisation creates a job and runs it as an
`arq` job. The provider's `iter_documents` feeds it in rate-limited batches. Because one shared index
serves every organisation, the job writes the organisation's documents into the live alias with a new
`reindex_run` stamp, then deletes that organisation's documents of the type that lack the stamp
(`delete_by_query` with routing), so a record deleted at the source while an event was lost also
disappears. A mapping change is different: it builds a new `-v<n+1>` index for all organisations,
then moves the alias in one atomic operation; a failure leaves the old index live
(`search.reindex.failed`). The API is the same for both. When a module first opts in, search runs a
backfill once per entitled organisation. One job per organisation, module and type at a time.

**Deletion and DPDP erasure.**

- A source record deleted or archived: its trigger event (`delete` action) removes the document.
  Archived records stay out of search by default; a module that wants them searchable keeps the
  `upsert` action and sets a `status` field facet.
- Erasure of a person (DPDP): the module must publish an event the declaration maps to `delete`,
  and the provider must return `None` for an erased person so a later reindex cannot bring them
  back. **student-information has no erasure event today; this is a gap** (open question 5).
- Organisation purge: `tenancy.organisation.purged` runs `delete_by_query` on `organisation_id`
  with routing across every search index and publishes `search.organisation.purged` with the count.
  Until the purge, an archived organisation's documents remain but unreachable: nobody in an
  archived organisation can sign in.
- Deleted documents are physically removed by segment merges within days; a force-merge on a
  schedule after an erasure is an operations item for infra, not a promise in the API.
- The index holds personal data (names). It is covered by the same backup and retention rules as
  the database: the index is rebuildable, so it is **not** backed up; restore means reindex.
  That keeps erasure from reappearing out of a snapshot. Open question 6.
- Query text is not logged and not audited, to avoid recording what people looked for. Only
  reindex requests are audited.

### 7. API surface (see `contracts/openapi.yaml`)

| Endpoint | Purpose | Permission |
|---|---|---|
| `GET /query` | Global search with `types` and per-type facets | `search:record:read` |
| `GET /modules/{module}/query` | One module's types, plus `filters` on declared fields | `search:record:read` |
| `GET /suggest` | 2 to 50 chars, at most 10 title suggestions | `search:record:read` |
| `GET /types` | Types the caller may use, for tabs and filters | `search:record:read` |
| `POST /reindex`, `GET /reindex`, `GET /reindex/{id}` | Rebuild; list and read jobs | `search:index:manage` |
| `GET /health` | Index state of the caller's organisation | `search:index:manage` |
| `GET /platform/health` | Engine health, totals only | `platform:search:read` |

Bounds, all enforced in the schema and again in the service: `q` 1 to 200 characters, plain
text only (it is passed as a `match` or `simple_query_string` with all operators disabled, never
as raw query syntax); `limit` 1 to 50 (default 20); `types` at most 20; `filters` at most 10 pairs;
cursor at most 2000 characters; suggest prefix 2 to 50; query timeout 2 seconds; a request
over the bound is a 422.

**Pagination is a cursor, never an offset.** Relevance sort with the document id as a tiebreaker,
`search_after`, on a point-in-time kept for 5 minutes. The cursor is signed (HMAC with
`SEARCH_CURSOR_SECRET`) and carries the user id and a hash of `q`, `types` and `filters`; a cursor
from another user, query or an expired one is a 422. A page deeper than 10 000 hits is not offered.
Counts above 10 000 report the bound with `total_is_lower_bound`.

**Errors.** Engine down is a 503, never an empty result, so a client does not read an outage as
"nothing found". No error includes the query or any document content.

### 8. Local, dev and CI

`SearchEngine` is a port in `application/ports.py`: `ensure_index`, `index`, `delete`,
`delete_by_organisation`, `search`, `suggest`, `swap_alias`, `health`. Every method takes a
`Caller` or an organisation id, not a bare query.

- `InMemoryEngine` implements the port with the same filter semantics (organisation, permissions,
  entitled modules, prefix match on `title`, simple tokenised match on text, cursor). It is the
  default (`SEARCH_ENGINE=memory`), and is refused when `EOS_DEV_MODE` is false, as notification
  does for its `memory` transport. Unit tests, API tests and every other module's tests that use
  search through `packages/testing` run on it.
- `OpenSearchEngine` implements the port with `opensearch-py` (approved stack).
- One **contract test suite** runs against both engines, so the fake cannot drift: the
  tenancy leak test, the permission filter test (fail closed on empty ACL, `read_users`, role
  change takes effect on the next query), cursor binding, bounds, delete and purge. Anything the
  fake cannot reproduce faithfully (analyzers, relevance order) is tested only against the real
  engine and marked `opensearch`.
- Real engine locally: a `search` profile in `infra/docker/docker-compose.yml` (single node,
  security plugin off, 512 MB heap, the `analysis-icu` plugin installed). `docker compose --profile
  search up`, then `SEARCH_ENGINE=opensearch pytest -m opensearch`. The compose change is its own
  small PR in `infra/`; it is not part of this one.
- CI: the default `api / test` job never needs OpenSearch. The `opensearch` marker runs in a
  separate job with a service container; whether it is required is open question 8.

### 9. Data (search's own schema, for the implementation PR)

`search.reindex_job` (id, organisation_id, module, type, status, counts, error, requested_by,
timestamps) and `search.index_state` (organisation_id, type, documents, last_indexed_at). Both have
`organisation_id` and row-level security. The index itself is not a source of truth and is never
read to answer anything but a search.

## Users

| Who | Does |
|---|---|
| Anyone signed in | Searches; sees only what they could open in the modules |
| Organisation admin | Rebuilds the index for a module, reads index health |
| Super admin | Reads engine health; reindexes for an organisation |
| A module (code) | Declares searchable types and a provider; gets scoped search for its own screen |

## Rules

1. A query without an organisation filter and a permission filter is impossible to construct.
2. A document without a read permission is not indexed.
3. Search never calls a module's database; it calls the module's provider.
4. The index is rebuildable from the modules; it is never restored from a snapshot.
5. An outage is a 503, not an empty page.

## Scope, week by week (issue estimate: 1 week, M3)

| Step | Delivers |
|---|---|
| 0 (this PR) | PRD and contracts, reviewed by Himanshu |
| 1 | Port, in-memory engine, declaration loader and validation, query builder with the leak and permission tests |
| 2 | OpenSearch engine, mappings, index naming, alias swap, compose profile |
| 3 | Indexer consumer, provider entry point, the three first types as fixtures, reindex job, purge |
| 4 | API, health, audit entries, README, staging |
| later | Wave 2 types, each in the owning module's PR |

Step 1 to 4 do not fit in the 1 week estimate on issue #87 if the three first types need
provider PRs in three other modules. Estimate: 1 week for search with fixtures, plus about half a
day in each module to add its declaration and provider.

## Dependencies

`platform/identity` (the caller's grants, entitlements), `platform/audit` (reindex), `platform/event-bus`
(delivery, `eos.event_consumers`). The `eos.search_documents` entry-point group is new and gets a
line in `module-standard.md` when the implementation merges. OpenSearch and `opensearch-py` are on
the approved stack; the `analysis-icu` plugin is an infra requirement.

## Success

- A student in organisation A never sees organisation B's records in a hit, a facet, a total or a
  suggestion (leak test, both engines).
- A person without `knowledge-base:article:read-internal` never sees an internal article's title.
- A new record is searchable within 5 seconds of its event at p95; suggest answers in 100 ms or
  less at p95 on 1 million documents.
- Reindexing one organisation's 100 000 documents completes in under 10 minutes without raising
  query latency by more than 20 percent.

## Open questions for review

1. **Provider callback or module pushes?** The proposal has search call a module-implemented
   provider (new entry-point group `eos.search_documents`). The alternative is the module's own
   consumer calling an SDK `search.upsert`. The first keeps retry, backfill and reindex in one
   place; the second needs no new mechanism. Which?
2. **Row-level read rules.** Permission keys cannot express "own sections only". Is `read_users`
   (a list written by the provider) acceptable, with its size bounded (proposal: at most 50 ids),
   or should such types be excluded from global search?
3. **Indian names and transliteration.** Is ICU folding plus a curated variant list enough for
   v1.0? Which scripts must work (Devanagari? Tamil? Urdu)? Who owns the variant list?
4. **Shared index with routing versus an index per organisation.** Confirm the shared layout, and
   that "prefixed by organisation" in ARCHITECTURE.md and ADR-0005 may be read as document id plus
   routing plus filter rather than the index name. Should a large organisation get a dedicated
   index later?
5. **Erasure.** student-information has no erasure or deletion event. Which event does a DPDP
   erasure of a person publish, and who adds it? Proposal: each module publishes
   `<module>.<entity>.erased`, and declarations map it to `delete`.
6. **Backups.** Confirm the index is excluded from backups and restored by reindex only. What
   is the recovery time we accept for search after a restore?
7. **Attachments.** Is content search of uploaded documents wanted for v1.0? Proposal: no. It needs
   text extraction (a pipeline and the ingest-attachment plugin) and a PII review.
8. **CI.** Should the OpenSearch job block merges, or run nightly and on changes under
   `platform/search`? A service container adds about a minute and 1 GB to a run.
9. **Entitlements at query time.** Does identity expose the organisation's entitled modules per
   request, or must search keep its own copy from `tenancy.entitlement.changed`?
10. **Wave-2 owners.** Who adds the library catalogue events and the documents event payloads,
    since each belongs to another module's owner?
11. **Audit.** Should a search for a sensitive type (persons) be audited with the type, never the
    query text? Proposal: no, volume and privacy.
12. **Declaration file name and place.** `contracts/searchable.yaml` is new in every module and is
    not in the module template. Should `modules/_template` and `check-manifests.py` learn it?
