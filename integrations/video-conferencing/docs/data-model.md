# video-conferencing: data model

Own tables, all prefixed `video_conferencing_`, all with `organisation_id` and a forced `tenant_isolation` row-level-security
policy (Alembic chain `db/`, version table `video_conferencing_alembic_version`). No foreign keys to another module.

| Table | Holds | Notes |
|---|---|---|
| `meeting` | one row per `(organisation_id, meeting_key)`: connection, provider, provider meeting id, Zoom/Webex instance id, host user at the provider, Jitsi room name, status (`creating`, `scheduled`, `started`, `ended`, `cancelled`), schedule, actual times | `join_url`, `host_join_url`, `passcode` are Fernet-encrypted. `creating` reserves the key while the provider call runs, so two concurrent creates cannot make two meetings; it is deleted if the call fails and hidden from the operator view |
| `attendance` | one row per participant of the latest report | `person_id` when matched, `display_name` **only when unmatched**; no email is stored. Replaced on each fetch |
| `recording` | provider recording id, kind, bytes, times, `document_id` and `sha256` once imported | `bytes` is 64-bit |
| `graph_subscription` | Teams subscription id, resource, expiry, `client_state_ref` | the ref is a nonce; Graph's `clientState` is `HMAC(data key, connection id + nonce)` and is never stored |
| `host_quota` | calls per `(connection, provider user, UTC day)` | Zoom's 100 create/update calls per user per day |
| `audit_entry` | actor (the hub's delivery id), action, entity, entity id, time | ids and the action only: never names, links or passcodes. Written in the same transaction as the change; stands in for the audit SDK until it ships |

State changes that write an audit entry: `meeting.created/updated/started/ended/cancelled`, `attendance.stored`,
`recording.imported`, `subscription.created/renewed`. The adapter publishes no events of its own (`contracts/events.yaml`),
so there is nothing for the outbox; the hub publishes `integration-hub.meeting.*` from the notifications `parse_inbound` returns.
