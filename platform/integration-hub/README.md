# integration-hub

**Domain:** platform
**Kind:** platform
**Status:** backend built on the draft contracts (v0.2.0); no screens yet (PRD open question 7)

The one place Education OS meets outside systems. Modules call a **port**; the hub runs the call on the organisation's
enabled **connection** for that port; an **adapter** in `integrations/` speaks to the provider. No module talks to a
vendor, so changing provider is configuration, not code (`integrations/README.md`, "Swap rule").

## Scope
- Ports, one per kind of integration: [`contracts/ports/`](contracts/ports/) (certificate-issuance, academic-records,
  regulatory-submission, meetings, wearable-data, inter-institution-records), plus the contract every adapter
  implements ([`adapter.yaml`](contracts/ports/adapter.yaml)).
- Connections per organisation: settings, credentials in a secret store (never the database), mock, sandbox and live.
- OAuth (authorization code with PKCE S256) for organisations and for people linking their own accounts.
- Provider callbacks: signature verification by the adapter, handshakes, deduplication, acknowledge first.
- Delivery log, retries with exponential backoff and full jitter, dead letters; health checks; super admin overview.

Not: provider protocols (the adapters), the decision to issue, schedule or file (the modules), email and SMS
(`platform/notification` and `messaging-providers`), payments (`payment-sbiepay`). See [docs/prd.md](docs/prd.md).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml), mounted at `/api/v1/integration-hub`
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)
- Ports, called in process: entry point `eos.integration_hub` / `invoke` (see
  [docs/integration-points.md](docs/integration-points.md); the PRD's `sdk.integrations.invoke` once `packages/sdk`
  has clients)

## Setup

The hub is enabled in `apps/backend/config/modules.enabled.yaml`; `tools/scripts/py-setup.sh` installs it with its
entry points, and its Alembic chain is `db/` (`cd platform/integration-hub/db && alembic upgrade head`).

Before the first connection is created on a server:

1. Give the API a writable volume for the secret store **outside the database and its backups** and point
   `INTEGRATION_HUB_SECRET_DIR` at it (mode 0700, owned by the API user).
2. Set `INTEGRATION_HUB_SECRET_KEK` to 32 random bytes, base64:
   `python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"`. Outside dev mode the hub refuses
   to store or read a secret without it (503 `secret_store_unavailable`). Keep it out of git and out of the database
   backups; losing it loses every stored credential.
3. Set `INTEGRATION_HUB_PUBLIC_BASE_URL` (callback URLs and the OAuth redirect URI are built on it) and
   `INTEGRATION_HUB_ALLOWED_RETURN_HOSTS` (the web app's host).
4. Install the adapters; each has its own `config/env.example` for its platform credentials.

Rotating the key: set the new key in `INTEGRATION_HUB_SECRET_KEK` and the old one in
`INTEGRATION_HUB_SECRET_KEK_PREVIOUS`, run
`python -c "from eos_integration_hub.infrastructure.secrets import get_store; print(get_store().rotate_kek())"` once
in the API's environment (it prints how many secrets it re-encrypted), then empty the previous key.

Development: `EOS_DEV_MODE=true` uses a key derived from `EOS_JWT_SECRET` when no KEK is set, and
`INTEGRATION_HUB_SECRET_BACKEND=env` reads secrets from `INTEGRATION_HUB_SECRET__<ORG>__<CONNECTION>__<NAME>`
(read only). `INTEGRATION_HUB_ALLOW_MOCK=true` allows mock mode; never set it in production.

## Configuration

Every key is in [config/env.example](config/env.example), prefixed `INTEGRATION_HUB_`, with its default and range.

## Modes and what is mocked

| Mode | What the adapter does | Who may choose it |
|---|---|---|
| `mock` | answers from recorded responses, no network | `connection:manage`, only where `INTEGRATION_HUB_ALLOW_MOCK=true` (development and demo) |
| `sandbox` | the provider's test environment, test credentials | `connection:manage` |
| `live` | production | `connection:go-live`, with every credential set, a healthy check in the same request and `confirm_live: true` |

The hub itself mocks nothing: whether a provider has a sandbox, and what stays mocked until an agency approves the
institution (DigiLocker, NAD, the government portals), is each adapter's README. Going live later is a credential entry
and one request, no release. A mock connection may be enabled without credentials; sandbox and live need all of them.

## Writing an adapter (the calling convention)

`contracts/ports/adapter.yaml` defines what an adapter does; this is how the hub calls it in Python.

- Register on the entry point group `eos.integration_adapters` under the adapter's folder name. The entry point loads
  an adapter object, or a zero-argument factory (a class or a function) that returns one.
- `describe()` returns the registry row: `{adapter, version, ports: [{port, version}], providers: [...]}` with the
  provider fields of adapter.yaml. `platform_credential_names` are environment variables of the adapter, either full
  names (`DIGILOCKER_CLIENT_SECRET`) or short ones prefixed with the adapter name (`client_secret` ->
  `DIGILOCKER_CLIENT_SECRET`); the super admin sees which are missing.
- Every operation of adapter.yaml and of the ports is a method named as the contract names it, called as
  `method(context, input)` or `method(context)` when it takes none. For port operations an adapter may instead offer
  one dispatcher, `invoke(context, operation, input)`; `context.port` says which port.
- `context` reads as attributes or as a mapping: `organisation_id`, `connection_id`, `provider`, `mode`, `settings`,
  `secrets` (name -> value, for this call only), `account_link` (`{id, person_id, provider_subject}` or None),
  `delivery_id`, `attempt`, `idempotency_key`, `deadline`, `port`, `operation`. For an app-level callback
  (`/inbound/{adapter}`) the connection fields are None: verify with the adapter's platform credentials.
- Return a mapping or object with `output`, or `error: {code, retry_after_s, detail, provider_code}`, and optionally
  `provider_reference`. A mapping with neither key is taken as the output. The hub keeps the contract's retryable flag
  per code, maps an unknown code or an exception to `provider_error` and a timeout to `transport_unavailable`.
- `verify_inbound` may add `ack_status` (200, 202 or 204) to its output for a provider that expects another success
  status (Graph: 202). `begin_authorisation` also receives `code_challenge_method: "S256"`.
- Never log or raise with a secret in the message; the hub logs only exception type names.

## Dependencies
See `module.yaml`. This module imports only `packages/` and the platform services it declares (identity for who is
calling, audit for the audit trail); adapters are found by entry point, never imported.

## Layout
| Path | Purpose |
|---|---|
| `docs/` | PRD, data model, integration points |
| `contracts/` | OpenAPI, event schemas, permission catalogue, ports |
| `backend/src/eos_integration_hub/` | `domain/` (vocabulary, rules, port events), `infrastructure/` (models, config, secret store, registry, ports), `application/` (use cases, jobs, consumers, `invoke`), `api/` (router, schemas) |
| `backend/tests/` | the suite, with a test-only adapter in `tests/fake_adapter/` (registered through its own dist-info) and recorded responses in `tests/fixtures/` |
| `db/` | Alembic chain, own tables only |
| `config/` | `env.example` |

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../docs/architecture/module-standard.md#portability-checklist).
