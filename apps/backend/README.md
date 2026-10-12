# apps/backend

The backend: Python FastAPI host, package `eos-backend` (import `eos_backend`).

FastAPI host. Mounts every platform service and enabled feature module under `/api/v1/<module>` behind
the **entitlement gate** (ADR-0005): a request to a feature module is refused with 403
`module_not_entitled` unless the caller's organisation is entitled to it, `organisation_inactive` if the
organisation is suspended, and `read_only` for writes after a trial ends. Platform services
(identity, tenancy, billing, ...) are always reachable and do their own permission checks.

| Mounted today | Package |
|---|---|
| `/api/v1/identity` | `platform/identity/backend` |
| `/api/v1/tenancy` | `platform/tenancy/backend` |
| `/api/v1/billing` | `platform/billing/backend` |
| `/api/v1/health` | this host |

Feature modules are added to `PLATFORM_ROUTERS`/`config/modules.enabled.yaml` as they ship.

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
```

`apps/backend/tests/test_foundation.py` is the phase 1 gate: register, verify, sign in, trial entitlement
enforced by the gate, upgrade unlocks, org admin toggles, super admin overrides, impersonation,
suspension, and the cross-tenant leak check.
