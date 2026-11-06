# digilocker

DigiLocker adapter. Implements the **certificate-issuance** port defined by `platform/integration-hub`
([`contracts/ports/certificate-issuance.yaml`](contracts/ports/certificate-issuance.yaml)): issue academic documents
to students' DigiLocker (Pull by default, Push where the account is known), replace and withdraw them, answer
DigiLocker's Pull URI and Pull Doc requests, and fetch a person's documents with their consent (requester OAuth, PKCE).
Never Aadhaar.

**Status:** built (0.3.0) against the draft contracts; mock mode complete, sandbox and live paths built but untested
against DigiLocker until it grants access. See [docs/prd.md](docs/prd.md).

## How the hub uses it

```python
# eos_digilocker.application.adapter:get_adapter, found by entry point
adapter = entry_point("eos.integration_adapters", "digilocker")()
adapter.describe()  # identity, ports, providers
result = adapter.invoke("issue", context, input)
# {"output": ..., "provider_reference": ...} or {"error": {"code": ..., "retryable": ...}}
```

`invoke` never raises. Operations: `capabilities`, `healthcheck`, `begin_authorisation`, `complete_authorisation`,
`refresh_authorisation`, `revoke_authorisation`, `verify_inbound` (always rejects: DigiLocker sends no webhooks),
`parse_inbound`, `handle_provider_request` (channels `pull-uri` and `pull-doc`), and the port's `issue`, `replace`,
`withdraw`, `get_issuance`, `fetch_holder_document`, `list_holder_documents`.

## Modes

Selected per connection (`context.mode`):

| Mode | Behaviour |
|---|---|
| `mock` (default in dev and CI) | A stateful simulator (`infrastructure/mock.py`) answers in the shapes of the Requester API v1.12 on `httpx.MockTransport`: no network. Refused unless `EOS_DEV_MODE=true`. Documents are kept in memory unless the host injects platform/documents |
| `sandbox` | Real calls to `DIGILOCKER_SANDBOX_BASE_URL` with the sandbox requester app. Not usable until DigiLocker issues sandbox access |
| `live` | Real calls to `DIGILOCKER_LIVE_BASE_URL`. Refuses to run without the issuer API key (Pull requests), push credentials (when push is enabled), the requester app, and `DIGILOCKER_SEARCH_KEY_PEPPER` |

Credentials come only from the hub's secret store (per institution, in `context.secrets`) and the deployment's
environment (Rooman's requester app). They are never logged, returned or written to the database.

## Configuration

Deployment keys are in [config/env.example](config/env.example). Per-institution connection settings and secrets are
entered on the hub's connection:

| Kind | Name | Notes |
|---|---|---|
| setting | `issuer_id` | The Issuer ID from the DigiLocker partner portal |
| setting | `doc_types` | `[{doc_kind, doc_type, search_fields, send_pdf_on_uri_request, has_xml}]`; `search_fields` default to `roll_number`, `year` |
| setting | `push_enabled` | Needs the issuer's app credentials and DigiLocker's permission |
| secret | `issuer_api_key` | Checked on Pull requests through `keyhash` |
| secret | `push_client_id`, `push_client_secret` | For Push URI and account verify |

Register the two callback URLs the hub shows on the DigiLocker partner portal (`.../pull-uri`, `.../pull-doc`).

## How to get sandbox access

Apply on the DigiLocker partner portal (https://partners.digilocker.gov.in, API Setu https://apisetu.gov.in), as an
issuer for the Pull channels and as a requester (Authorised Partner) for fetching documents; the demo partner portal is
https://devpartners.digitallocker.gov.in. Then set `DIGILOCKER_SANDBOX_*`, run the contract tests in
`tests/test_sandbox.py` by hand, and compare the recorded fixtures in `tests/fixtures/` with what DigiLocker sends.

## What is mocked until DigiLocker approves

Everything that talks to DigiLocker: Push URI, account verify, token exchange and refresh, revoke, issued files, file by
URI, pull on demand. The fixtures in `tests/fixtures/` are built from the Requester API Specification v1.12 and the Pull
API Specification v1.3 as cited in the PRD; the PRD lists what is **not verified** (exact Pull XML, sandbox URL, rate
limits). Assumptions this build makes, to confirm against the specs DigiLocker sends at onboarding:

- Push HMAC: SHA-256 of the client secret followed by `clientid, digilockerid, uri, doctype, description, docid,
  issuedate, validfrom, validto, action, ts` (the order the PRD lists them); `ts` is epoch seconds.
- Account verify: signed with the same scheme over `clientid, mobile, ts`; answers `{status, digilockerid}`.
- File HMAC: HMAC-SHA256 of the content keyed by the requester client secret, hex, in the `hmac` response header.
- Pull request timestamp: ISO 8601; one without a zone is read as IST. `keyhash` is hex SHA-256 of key + `ts`.
- Pull search parameters arrive as elements named like the doc type's search fields, or as `UDF1..n` in field order.

## Tests

`tests/` runs with no network and no other module: recorded request/response pairs replayed against the real client,
golden Pull responses, PKCE and HMAC checks against the simulator, tenancy (cross-tenant leak, organisation_id and
policies on every table), the Alembic chain, and the Adapter contract. `tests/test_sandbox.py` runs only when
`DIGILOCKER_SANDBOX_*` is set.

- `contracts/ports/` the port and the Adapter contract, copied from integration-hub
- `contracts/openapi.yaml` the Pull Issuer channels and the operator view
- `docs/data-model.md`, `docs/integration-points.md`
