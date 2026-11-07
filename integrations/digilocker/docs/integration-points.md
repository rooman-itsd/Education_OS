# digilocker: integration points

## Used

| What | How | Notes |
|---|---|---|
| platform/integration-hub | Finds this adapter by the `eos.integration_adapters` entry point (`digilocker = eos_digilocker.application.adapter:get_adapter`), passes a context (mode, settings, secrets, account link) with every call, receives DigiLocker's Pull requests and hands them to `handle_provider_request` | The hub is built in parallel; this adapter is tested standalone against `contracts/ports/adapter.yaml` |
| platform/documents | Reads the signed PDF to check its hash and serve it; stores a file fetched with a person's consent | Through the `DocumentStore` protocol (`infrastructure/documents.py`); the hub or host injects the real client with `get_adapter().configure(documents=...)`. `packages/sdk` has no documents client yet |
| DigiLocker issuer APIs | Push URI and account verify (issuer app credentials) | Requester API Specification v1.12 |
| DigiLocker requester APIs | OAuth 2.0 with PKCE S256, issued files, file by URI with HMAC | Rooman's requester app (`DIGILOCKER_REQUESTER_*`) |

## Exposed

- The certificate-issuance port and the Adapter contract (`contracts/ports/`).
- DigiLocker's Pull URI and Pull Doc channels, served by the hub's provider-request route.
- `GET /api/v1/digilocker/issuances`, the read-only operator view (`digilocker:issuance:read`).

## Not done here

- Events: none (`contracts/events.yaml`). The hub publishes `integration-hub.certificate.*`, using the `notifications`
  the adapter returns (`document_pulled` from Pull Doc) and the results of `issue`, `replace` and `withdraw`.
- Audit: the hub audits connection and delivery changes; this adapter keeps its own `issuance_history`.
