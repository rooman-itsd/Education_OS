# apps/backend

The backend: Python FastAPI host, package `eos-backend` (import `eos_backend`).

FastAPI host. Mounts every platform service and enabled feature module under `/api/v1/<module>` behind
the **entitlement gate** (ADR-0005): a request to a feature module is refused with 403
`module_not_entitled` unless the caller's organisation is entitled to it, `organisation_inactive` if the
organisation is suspended, and `read_only` for writes after a trial ends. Platform services
(identity, tenancy, billing, ...) are always reachable and do their own permission checks.

## What it mounts: `config/modules.enabled.yaml`

One file decides what this host serves:

```yaml
modules:                    # feature modules, <domain>/<module>
  - campus-life/hostel
integrations: []            # adapters under integrations/, e.g. payment-sbiepay
platform: [identity, tenancy, billing]
```

Every entry follows the same layout, so the entry alone is enough: package `eos_<name>` (from
`<entry>/backend/`, or the entry folder itself for an adapter with `src/` at its root), router
`eos_<name>.api.router:router` mounted at `/api/v1/<name>`, and its Alembic chain, if any, in `<entry>/db`.
`/api/v1/health` lists the mounted modules and integrations. A listed entry that is not installed stops
start-up with a message naming it, instead of serving 404s.

`tools/scripts/enabled-modules.py` reads the same file for everything that runs before the API:
`tools/scripts/py-setup.sh` and the API image install every entry, CI runs each enabled module's tests and
its chain (upgrade, row-level-security check, downgrade) on Postgres, and the API auto-deploy upgrades
every enabled chain before restarting.

**Enabling a module's backend** is a one-line PR adding its entry here (block style, alphabetical),
reviewed by the app owner, once the module has `api/router.py` and its migrations. The frontend has its
own list, `apps/frontend/config/modules.enabled.yaml`, with the same entry format; the two need not match.

| Mounted today | From |
|---|---|
| `/api/v1/identity`, `/tenancy`, `/billing` | `platform:` |
| `/api/v1/hostel` | `modules:` (`modules/campus-life/hostel`) |
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
for t in $(python tools/scripts/enabled-modules.py tests); do pytest "$t"; done   # enabled modules' own suites
```

`apps/backend/tests/test_module_loader.py` covers the mounting rules above. `apps/backend/tests/test_foundation.py` is the phase 1 gate: register, verify, sign in, trial entitlement
enforced by the gate, upgrade unlocks, org admin toggles, super admin overrides, impersonation,
suspension, and the cross-tenant leak check.
