# CI workflows

Live: `api.yml` installs every Python package and runs the foundation tests on SQLite and on Postgres with row-level security, on every push and PR. `web.yml` runs typecheck, tests and the web build on every push and PR, and on `main` publishes the build to the `web-dist` branch for the server to pull (see `infra/autodeploy/`).

`governance.yml` enforces the team rules on every PR: approved stack only, module boundaries, module manifests (`check-manifests.py`: every `module.yaml` complete and consistent with its folder, dependencies that exist, owners from `docs/team/members.yaml`, exposed files present once past `planned`), migrations (`check-migrations.py`: every table a migration creates has `organisation_id` and an RLS policy on `app.organisation_id`), ruff, conventional commits scoped by module, one module per PR. The scripts' own tests run in the same job. `auto-assign.yml` hands each person their next issue the moment their current one closes (one open issue per person). `metrics.yml` publishes the per-person status report to the `team-status` branch every 6 hours.

Planned jobs (stack: FastAPI + React + PostgreSQL, see ADR-0002):

| Job | Purpose |
|---|---|
| `module-boundaries` | import-linter (Python) + ESLint no-restricted-imports (TS): fail on imports outside the module and `packages/` |
| `contracts-lint` | Validate every `contracts/*.yaml` |
| `test-changed-modules` | Run tests only for modules touched by the PR |
| `test-contract` | Run root `tests/contract` on every PR |
| `test-system` | Run root `tests/integration` and `tests/e2e` on merge to `main`; `tests/performance` on demand |
| `build-apps` | Build `apps/*` with their enabled module lists |
