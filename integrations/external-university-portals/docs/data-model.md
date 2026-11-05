# external-university-portals: data model

Own schema, prefix `external_university_portals_`; Alembic chain `eup_0001` with its own version table
`external_university_portals_alembic_version`. Every table carries `organisation_id` and the forced `tenant_isolation`
row-level-security policy (`eos_core.rls.POLICY`).

| Table | Purpose | Notes |
|---|---|---|
| `external_university_portals_exchange` | One record exchange with a partner: direction, format, channel, status, the file (`document_id`, `sha256`), import integrity and unmapped lines, delivery record | Unique `(organisation_id, exchange_key, direction)`: the caller's key makes export and import idempotent |

Status flow: outbound `prepared`, then `sent` (email, live) or `manual_action_required` (download, partner portal), then
`delivered_manually`; inbound `parsed` (or `rejected` for a file that cannot be read; a corrected file under the same key
replaces it). `received` is in the port's vocabulary for the day an API channel delivers; nothing sets it today.

Not kept: the transcript. The source of truth is the calling module. `unmapped` holds `{position, reason}` only. Every
state change writes an outbox event in the same transaction, which is the audit trail.
