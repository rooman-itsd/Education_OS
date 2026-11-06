# search — data model

Search owns four small tables (Alembic chain `search_0001`, version table `search_alembic_version`). Each has
`organisation_id NOT NULL` with a non-empty check and the forced `tenant_isolation` row-level-security policy. The index
itself is not a source of truth and is rebuilt from the modules (docs/prd.md, rule 4).

| Table | Holds | Notes |
|---|---|---|
| `search_reindex_job` | one rebuild: module, type (null = every type of the module), status, counts, error sentence, requester, times | A partial unique index allows one `queued`/`running` job per organisation and `scope_key` (`<module>|<type or empty>`); the service also refuses overlapping scopes. |
| `search_index_state` | per organisation and type: `last_indexed_at`, `last_reindex_at` | Document counts are read from the engine, not stored. |
| `search_entitlement` | the modules an organisation may use, copied from `tenancy.entitlement.changed` | Absent means "not seen yet": nothing is filtered on its account. The per-document permission filter still applies. |
| `search_dead_letter` | a document that failed every retry or was refused: ids and a short reason code | No content. Counted in `GET /platform/health`; a reindex of the organisation and module clears it. |

## The engine document

One shared index per type, `eos-<environment>-<module>-<type>-v<n>` behind the alias without `-v<n>`, written and queried
with `routing = organisation_id`. Strict mapping.

| Field | Type | |
|---|---|---|
| `doc_id` | keyword | `<organisation_id>:<module>.<type>:<record id>`; the sort tiebreaker |
| `organisation_id`, `type`, `module`, `record_id` | keyword | `organisation_id` is set by search from the event envelope, never by the provider |
| `title` | text (+ `title.sayt`, search_as_you_type) | the field with `role: title`, with its declared analyzer |
| `read_any_of`, `read_users` | keyword | the permission keys that may read the document; user ids that may read it regardless |
| `indexed_at`, `source_version`, `reindex_run` | date, long, keyword | `source_version` is the external version (the event time in microseconds) |
| `fields.<name>` | per declared kind | the module's declared fields, under a prefix so they can never collide with the above |
