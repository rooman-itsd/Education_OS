# wearables: integration points

| With | How |
|---|---|
| `platform/integration-hub` | Finds the adapter by entry point `eos.integration_adapters` / `wearables`; passes the call context (`account_link` names the athlete); receives the providers' callbacks at `/inbound/wearables?provider=<provider>` and asks `verify_inbound` / `parse_inbound`; keeps accounts links, OAuth tokens and secrets; publishes `integration-hub.wearable-data.received` and the account-link events. Not imported: the port files in `contracts/ports/` are copies |
| `integration-hub.account-link.revoked` | Consumed on the `eos.event_consumers` entry point (`application/consumers.py`): deletes every record collected under the link at once |
| `platform/identity` | Registers `wearables:alert:read` (coach, org-admin); `GET /alerts` reads the platform token through `eos_core` |
| `platform/audit` | Until the audit SDK ships, `wearables_audit_entry` in the same transaction |
| `modules/sports/athlete-performance`, `sports-nutrition-health` | Callers of the wearable-data port through `packages/sdk`: they state a purpose with every `read` |
| Dashboard | The widget `wearables.alerts` (`frontend/src/widgets`) reads `GET /alerts`; the coach layout `platform/identity/config/dashboards/coach.yaml` already lists it |

## Providers

| Provider | Auth | Data | Delivery | Notes |
|---|---|---|---|---|
| Garmin | OAuth 2.0 + PKCE | dailies, sleeps, activities, hrv, body composition | push (Starter) or ping and pull (Enterprise); `deregistrations`, `userPermissionsChange` | tier is the connection setting `garmin_tier`; pushes are matched to an active link by Garmin user id (Garmin's own signing not yet documented to us) |
| Polar AccessLink | OAuth 2.0, tokens do not expire; `POST /v3/users` | exercises, daily activity, sleep | one webhook, `Polar-Webhook-Signature` HMAC-SHA256, PING on creation | no HRV, body composition or history |
| Fitbit (Google Health API) | Google OAuth 2.0 + PKCE | all five (assumed) | pull only: webhooks refused until Google documents their verification | endpoints and shapes are assumptions until access is granted |
| Strava | OAuth 2.0, `activity:read_all` | activities | push subscription, no signature | shown only to its athlete; rate gate per app |
