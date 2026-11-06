# wearables: data model

Own tables, all prefixed `wearables_`, all with `organisation_id` and a forced `tenant_isolation` row-level-security policy
(Alembic chain `db/`, version table `wearables_alembic_version`). No foreign keys to another module.

| Table | Holds | Notes |
|---|---|---|
| `link_state` | one row per account link the adapter has seen: connection, hub `account_link_id`, `person_id`, provider, the athlete's id at the provider, status (`pending`, `active`, `expired`, `revoked`, `error`) and since when, the data types it covers, last sync, last data, failure streak and its start, last error code | No token: those are the hub's. `provider_subject` is how a webhook finds its link. A revoked row stays (the coach's alert "link revoked") but its records are gone |
| `record` | one normalised record per `(account_link_id, data_type, provider_record_id)`: the day it belongs to, the port's normalised fields as JSON (fixed units), `display_scope` (`all` or `athlete_only`) and `received_at` | The PRD sketches one table per data type; one table with `data_type` and the port's shape in `fields` holds the same thing and adds a data type without a migration. Upserted, so a redelivery or a correction changes one row. Deleted at once when the link is revoked, and daily past `WEARABLES_RETENTION_DAYS` |
| `read_log` | who asked (calling module), for which athlete, data type and range, with which purpose, when | No readings. Written for every read that was answered |
| `audit_entry` | actor (the hub's delivery id), action, entity, entity id, time | Ids and the action only. Written in the same transaction as the change; stands in for the audit SDK until it ships |

State changes that write an audit entry: `link.started`, `link.connected`, `link.expired`, `link.revoked`,
`link.revoked_by_provider`, `link.narrowed`, `records.stored`, `records.deleted`, `records.expired`. The adapter publishes no
events of its own (`contracts/events.yaml`), so there is nothing for the outbox; the hub publishes
`integration-hub.wearable-data.received` from the output of `sync`, and `integration-hub.account-link.*`.

## Strava data

`record.display_scope` is `athlete_only` for every Strava record unless the connection's `strava_shared_display_approved` was
true when it was stored. `read` returns a Strava record to anyone but its athlete only if the record is `all` **and** the
connection's setting is still true at the time of the read, so withdrawing Strava's approval hides the data again at once.
