# integration-hub: data model

Own Alembic chain (`db/`, version table `integration_hub_alembic_version`), tables prefixed `integration_hub_`. Every
table carries `organisation_id` with the forced `tenant_isolation` row-level-security policy. **No column holds a
secret**: credentials and tokens are references into the secret store; the three blobs kept for a while are AES-256-GCM
encrypted under `INTEGRATION_HUB_SECRET_KEK` and purged on short retention.

| Table | Holds | Notes |
|---|---|---|
| `connection` | one organisation's configuration of one adapter, provider and port: mode, enabled, display name, non-secret `settings` (validated against the provider's `settings_schema`), `connection_key_hash`, `authorised`, health (status, detail, checked at, expiry), on-demand health window, `throttled_until`, `changed_at` | The inbound URL key itself is in the secret store; only its SHA-256 is here, for lookup. `changed_at` moves on every change that can fix a failure (credentials, settings, mode, authorisation), which is what lets a non-retryable delivery be retried by hand. |
| `connection_credential` | per credential name: `secret_ref`, 8-hex `fingerprint`, `source` (admin, oauth), `set_by`, `set_at`, `expires_at` | Unique per connection and name. Never the value. |
| `account_link` | one person's link at a person-scope provider: connection, person, port, provider, `provider_subject`, status, purpose, granted scopes, `secret_ref` of the tokens, linked / expires / last synced / revoked at, revoke cause | The tokens are one JSON secret per link. |
| `oauth_state` | a pending authorisation: SHA-256 of the state, adapter, connection, link, person, encrypted PKCE verifier, return URL, expiry, used at | Single use; purged a day after expiry. |
| `delivery` | the log: direction, connection, link, port, operation, sync, mode, provider, caller module and reference, idempotency key, `subject_key` / `object_id` / `person_id` / `refs` of the port object, status, attempts, next attempt, last error code, provider reference, encrypted input (async only), inbound receipt, timings | `refs` keeps only non-personal keys of the input (doc_kind, award_kind, form_code, period, partner_id, format, data_types, from, to), so a later callback or operation (withdraw, submit, attendance) can be matched to the module that asked and its event filled in. The input is purged `INTEGRATION_HUB_DELIVERY_PAYLOAD_RETENTION_DAYS` after the delivery ends; the row `INTEGRATION_HUB_DELIVERY_LOG_RETENTION_DAYS` after it was made. |
| `delivery_attempt` | per attempt: started at, duration, outcome, error code, provider code | Rendered as `attempt_log` by `GET /deliveries/{id}`. |
| `inbound_receipt` | one callback as it arrived: adapter, connection, channel, dedupe key, verdict (accepted, rejected, handshake), encrypted raw body and headers, received / processed at | Written by the hub's platform role before the tenant is known; `organisation_id` is set once the connection is. Unique on (adapter, dedupe key). Raw body purged after `INTEGRATION_HUB_INBOUND_RAW_RETENTION_DAYS`. |

Audit records go to `platform/audit` (`audit_record`, append only) in the same transaction as the change. Events go to
the `eos_core` outbox in the same transaction.

The adapter registry of the PRD is **not** a table: it is rebuilt from each adapter's `describe()` when the process
starts (`infrastructure/registry.py`), so an installed adapter and the registry cannot disagree.

## Delivery statuses

```
queued -> in_progress -> succeeded
                      -> retry_scheduled -> in_progress ... -> dead_lettered   (retryable, attempts exhausted)
                      -> failed                                                  (non-retryable, or a sync call)
                      -> manual_action_required                                  (no API path; a person files it)
inbound: queued -> in_progress -> succeeded | retry_scheduled | failed | dead_lettered;  rejected_inbound
```

`in_progress` carries a lease (`next_attempt_at`): a sweep that finds one past its lease runs it again.
