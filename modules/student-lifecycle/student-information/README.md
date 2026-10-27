# student-information

**Domain:** student-lifecycle
**Kind:** feature
**Status:** in-progress (backend, migrations, test suite, and host registration complete; frontend widgets placeholder verified)

Student master record (SIS): profiles, documents, ID cards, status history.

## Scope
Owner: Praveen (@praveen-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** The Person system of record (SIS): profile, contact and guardian details, status history
(pending, active, suspended, graduated, withdrawn, alumnus), attached identity/supporting
documents, and ID card issuance (`IDC-{ORG4}-{YYYYMM}-{RANDOM6}`). A Person record is created only by an authorised staff role
(registrar, or admissions staff with the permission) — never through public sign-up.

**Not in scope:** Login credentials (`platform/identity`), raw file
storage (`platform/documents`), the admissions funnel (`admissions`), organisation onboarding and
sign-up (`web-portal-cms` + `platform/tenancy`), programme enrolment (`enrolment-registration`),
academic records (`academics/*`), or fee invoices (`finance-operations/fees-accounts`). See
[docs/prd.md](docs/prd.md) for the full scope.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)
- Dashboard widgets: None yet (`frontend/src/widgets/index.ts` exports `widgets = []`)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

What it needs from the host repo:
- `packages/core` (`eos_core`): database base and tenant scoping, row-level-security policy, token checks,
  permission catalogue, outbox for events.
- `packages/testing` (`eos_testing`): multi-tenant cross-leak assertions.
- Package name: `eos-student-information` (`backend/pyproject.toml`).
- API router: `eos_student_information.api.router:router`, mounted in `apps/backend/config/modules.enabled.yaml` under `/api/v1/student-information`.

## Running checks & tests

### Standard test suite (SQLite)
```bash
# Editable install into monorepo virtual environment:
pip install -e modules/student-lifecycle/student-information/backend[test]

# Run unit, contract drift, and tenant isolation tests (SQLite):
pytest modules/student-lifecycle/student-information/backend/tests -q
```

### Live PostgreSQL Row-Level Security (RLS) verification
Row-level security enforcement on live PostgreSQL (`tests/test_rls_postgres.py`) runs whenever `STUDENT_INFORMATION_TEST_POSTGRES_URL` (or `EOS_TEST_POSTGRES_URL`) is configured. It is skipped automatically when neither is set.

#### 1. Test runner prerequisites & least-privilege role
The test runner connects to a local PostgreSQL cluster (e.g. `localhost:5432` or a throwaway container like `postgres:16-alpine`). It requires only permissions to create and drop isolated databases and probe roles (`CREATEDB`, `CREATEROLE`). It does **not** require superuser status.

To set up a dedicated test runner on your local PostgreSQL instance:
```sql
CREATE ROLE eos_test WITH LOGIN PASSWORD '<test_password>' CREATEDB CREATEROLE NOSUPERUSER NOBYPASSRLS;
```

#### 2. Run the tests
Set `STUDENT_INFORMATION_TEST_POSTGRES_URL` as a process-scoped environment variable (do not commit credentials to source control):

**PowerShell (Windows):**
```powershell
$env:STUDENT_INFORMATION_TEST_POSTGRES_URL = "postgresql+psycopg://eos_test:<test_password>@localhost:5432/postgres"

# Dedicated RLS test suite (2 tests):
.venv\Scripts\python.exe -m pytest modules/student-lifecycle/student-information/backend/tests/test_rls_postgres.py -v

# Complete module test suite (62 tests):
.venv\Scripts\python.exe -m pytest modules/student-lifecycle/student-information/backend/tests -v

# Clear the environment variable after testing:
$env:STUDENT_INFORMATION_TEST_POSTGRES_URL = $null
```

**Bash / Linux / CI:**
```bash
STUDENT_INFORMATION_TEST_POSTGRES_URL="postgresql+psycopg://eos_test:<test_password>@localhost:5432/postgres" \
  pytest modules/student-lifecycle/student-information/backend/tests/test_rls_postgres.py -v
```

#### 3. Test lifecycle & isolation guarantees
- The test fixture automatically creates an isolated throwaway database (`student_info_rls_<uuid>`) and an unprivileged probe role (`student_info_probe_<uuid>` with `NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT`).
- Migrations apply via Alembic to configure `FORCE ROW LEVEL SECURITY` and `tenant_isolation` policies on all 4 tables (`person`, `status_history`, `document`, `id_card`).
- The probe role exercises tenant isolation using `SET LOCAL ROLE` and `app.organisation_id`.
- The fixture drops both the temporary database (`WITH (FORCE)`) and the probe role at completion, guaranteeing zero leftover state.

## Layout
| Path | Purpose |
|---|---|
| `docs/` | PRD, user stories, data model, screen list |
| `contracts/` | OpenAPI, event schemas, permission catalogue |
| `backend/` | Domain, application, infrastructure, API layers + unit tests |
| `frontend/` | Pages, components, API client + widgets export |
| `mobile/` | Mobile screens (optional) |
| `db/` | Alembic migrations (`student_information_alembic_version`) |
| `config/` | `env.example`, feature flags |
| `tests/e2e` | End-to-end tests runnable in isolation |

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
