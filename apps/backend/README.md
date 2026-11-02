# apps/backend

The backend: Python FastAPI host, package `eos-backend` (import `eos_backend`).

FastAPI host. Mounts every platform service and enabled feature module under `/api/v1/<module>` behind
the **entitlement gate** (ADR-0005): a request to a feature module is refused with 403
`module_not_entitled` unless the caller's organisation is entitled to it, `organisation_inactive` if the
organisation is suspended, and `read_only` for writes after a trial ends. Platform services
(identity, tenancy, billing, ...) are always reachable and do their own permission checks.

Around the gate sit `platform/api-gateway`'s middlewares: rate limits per user and per organisation for
signed-in requests, per client address for the rest, and for sign-in/sign-up (429 with `Retry-After`,
`code: rate_limited`), CORS, and the security headers on every response. The limiter decodes the bearer token
once and the gate reuses it (`eos_api_gateway.token_claims`, `request.state.token_claims`). Settings and the
proxy requirements: [platform/api-gateway/README.md](../../platform/api-gateway/README.md).
The plan's user limit (staff accounts; learners are not counted) is enforced by identity through a hook wired
here to billing (`409 plan_limit_reached`).

## What it mounts: `config/modules.enabled.yaml`

One file decides what this host serves:

```yaml
modules:                    # feature modules, <domain>/<module>
  - academics/academic-management
  - campus-life/hostel
  - support/helpdesk
integrations: []            # adapters under integrations/, e.g. payment-sbiepay
platform: [identity, tenancy, billing, api-gateway]
```

Every entry follows the same layout, so the entry alone is enough: package `eos_<name>` (from
`<entry>/backend/`, or the entry folder itself for an adapter with `src/` at its root), router
`eos_<name>.api.router:router` mounted at `/api/v1/<name>`, and its Alembic chain, if any, in `<entry>/db`.
`/api/v1/health` lists the mounted modules and integrations. A listed entry that is not installed stops
start-up with a message naming it, instead of serving 404s. An entry whose `module.yaml` declares
`router: false` (`api-gateway`, middleware only) is installed like the rest and mounts nothing; any other
entry without `api/router.py` stops start-up too.

`tools/scripts/enabled-modules.py` reads the same file for everything that runs before the API:
`tools/scripts/py-setup.sh` and the API image install every entry, CI runs each enabled module's tests and
its chain (upgrade, row-level-security check, downgrade) on Postgres, and the API auto-deploy upgrades
every enabled chain before restarting.

**Enabling a module's backend** is a one-line PR adding its entry here (block style, alphabetical),
reviewed by the app owner, once the module has `api/router.py` and its migrations. The frontend has its
own list, `apps/frontend/config/modules.enabled.yaml`, with the same entry format. Every frontend-enabled
module whose backend has `api/router.py` must be enabled here too (`tests/test_module_loader.py` checks),
otherwise the dashboard shows widgets whose requests 404; a module with an API and no widgets is listed
only here.

| Mounted today | From |
|---|---|
| `/api/v1/identity`, `/tenancy`, `/billing`, `/notification` | `platform:` |
| (no routes: headers and rate limits on every response) | `platform: api-gateway` |
| `/api/v1/academic-management`, `/hostel`, `/helpdesk` | `modules:` (`modules/<domain>/<module>`) |
| `/api/v1/health` | this host |

## Run locally

```
tools/scripts/py-setup.sh            # creates .venv and installs every backend package (editable)
source .venv/bin/activate
EOS_SUPER_ADMIN_EMAIL=root@platform.example.com EOS_SUPER_ADMIN_PASSWORD=RootPassw0rd! uvicorn eos_backend.main:app --reload --port 8000
```

The super admin email must be a valid address with a dot after the `@`; sign-in rejects one like
`root@local`. On Windows (PowerShell), after creating `.venv` with `py -3.12 -m venv .venv` and the same
`pip install -e` lines as `py-setup.sh`:

```
$env:EOS_SUPER_ADMIN_EMAIL='root@platform.example.com'; $env:EOS_SUPER_ADMIN_PASSWORD='RootPassw0rd!'
.\.venv\Scripts\python.exe -m uvicorn eos_backend.main:app --reload --port 8000
```

SQLite by default (`EOS_DATABASE_URL=sqlite:///./eos.db`). For Postgres with row-level security:
`EOS_DATABASE_URL=postgresql+psycopg://eos:eos@localhost/eos`. `EOS_DEV_MODE=true` returns the
verification token in the register response so the flow can be driven without email.

## Tests

```
pytest apps/backend packages/core platform/identity/backend
for t in $(python tools/scripts/enabled-modules.py tests); do pytest "$t"; done   # enabled platform services' and modules' own suites
```

`apps/backend/tests/test_module_loader.py` covers the mounting rules above. `apps/backend/tests/test_foundation.py` is the phase 1 gate: register, verify, sign in, trial entitlement
enforced by the gate, upgrade unlocks, org admin toggles, super admin overrides, impersonation,
suspension, and the cross-tenant leak check.
