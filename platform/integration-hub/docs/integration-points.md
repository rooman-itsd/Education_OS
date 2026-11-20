# integration-hub: integration points

## How modules call a port

In process, through the `eos.integration_hub` entry point (`invoke`), as the calling module and for its organisation:

```python
from importlib import metadata

(point,) = metadata.entry_points(group="eos.integration_hub", name="invoke")
invoke = point.load()
result = invoke(
    port="meetings",
    operation="create_meeting",
    input={...},
    idempotency_key="lms:class-session:<id>",
    caller_reference="<id>",
    caller_module="lms",
)
# {delivery_id, status, output, error: {code, retryable, retry_after_s, detail} | None, provider_reference, replayed}
```

The PRD proposes `sdk.integrations.invoke`. `packages/sdk` has no Python client of any platform service yet (empty
`src/`, not installable), so the hub publishes `invoke` the way modules reach platform services today without
importing them: an entry point, like `eos.event_consumers` and `eos.scheduler_jobs`. When `packages/sdk` gains its
first client, `sdk.integrations.invoke` wraps this entry point and no caller changes.

- `organisation_id` defaults to the current tenant (`eos_core.tenant`); pass it explicitly from a job or consumer.
- `provider` is needed only when the organisation has two enabled connections for the port.
- `account_link_id` (or `input.account_link_id`) makes the call for that person's link; it must be active, else
  `consent_required`.
- Business failures are returned, never raised: handle `error.code` the same way whoever the provider is.

## How the hub finds adapters

Entry point group `eos.integration_adapters` (`contracts/ports/adapter.yaml`, "registration"). The calling convention
is in the README, "Writing an adapter". `INTEGRATION_HUB_ADAPTERS` limits which installed adapters are loaded.

## Published events

Written to the `eos_core` outbox in the same transaction as the change; platform/event-bus relays them. Payloads are
exactly those of [`contracts/events.yaml`](../contracts/events.yaml): ids, keys and statuses, never a credential, token,
document, reading, name or contact detail. Tests compare every published payload with the contract.

| Event | When |
|---|---|
| `connection.created`, `.updated`, `.enabled`, `.disabled`, `.mode-changed` | the matching `/connections` call; `.disabled` also when a required credential is removed or another connection of the same port and provider is enabled |
| `connection.authorised` | the OAuth callback completed for an organisation connection |
| `connection.credentials-rotated` | a credential set, rotated or removed (name and fingerprint) |
| `connection.health-changed` | a healthcheck result differs from the previous one (once per transition) |
| `account-link.connected`, `.revoked` | a person linked; a link ended (person, admin, provider, failed refresh) |
| `delivery.succeeded`, `.failed`, `.manual-action-required` | outcome of an **async** operation (sync callers have the answer) |
| port events (`certificate.*`, `academic-record.*`, `regulatory-package.*`, `meeting*.*`, `wearable-data.received`, `inter-institution-record.exchanged`) | from an operation's output or a callback's notification (`domain/port_events.py`) |
| `job.finished` | one of the hub's scheduled jobs finished (platform/scheduler's protocol; added to events.yaml by this build) |

## Consumed events

`scheduler.job.due` for the hub's own jobs (`eos.event_consumers`):

| Job | Default cron | Does |
|---|---|---|
| `integration-hub.process-deliveries` | every minute | runs due async operations and retries, processes acknowledged callbacks the background task did not finish |
| `integration-hub.health-checks` | every 15 minutes | healthchecks enabled connections older than `INTEGRATION_HUB_HEALTH_INTERVAL_MIN` |
| `integration-hub.refresh-tokens` | every 5 minutes | refreshes OAuth tokens within `INTEGRATION_HUB_TOKEN_REFRESH_LEAD_S` of expiry |
| `integration-hub.purge` | 02:40 daily | retention of inputs, raw callbacks, log rows and OAuth states |

## Platform services

| Service | How | Use |
|---|---|---|
| identity | `eos_identity.api.deps` (declared dependency) | who is calling and their permission keys |
| audit | `eos_audit.application.service.record` in the caller's transaction (declared dependency) | every connection change, credential set (name and fingerprint), mode change, link, revoke, manual retry and inbound rejection |
| event-bus | `eos_core.events.publish` (outbox) | the events above |
| scheduler | `eos.scheduler_jobs` entry point | the four jobs above |
| documents, notification | through events only | files are referenced by document id in port payloads; notification tells org admins from `health-changed` and `delivery.failed` |
