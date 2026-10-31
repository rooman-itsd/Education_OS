# CI workflows

Live: `api.yml` installs every Python package and runs the foundation tests on SQLite and on Postgres with row-level security, on every push and PR. `web.yml` runs typecheck, tests and the web build on every push and PR, and publishes the build for the servers to pull: on `main` to the `web-dist` branch (staging), on the highest `vX.Y.Z` release tag to the `web-release` branch (production). See `infra/autodeploy/README.md`, section "Environments". `system.yml` runs the `tests/e2e` journeys in Chromium (the suite starts its own API and web server on a fresh database) after every merge to `main`, on PRs that change `tests/e2e/`, `apps/frontend/` or the dashboard layouts, and by hand; given a URL by hand it also runs the read-only smoke checks against that site. On failure it keeps the Playwright report, screenshots and traces as the `e2e-report` artifact for 7 days.

`governance.yml` enforces the team rules on every PR: approved stack only, module boundaries, module manifests (`check-manifests.py`: every `module.yaml` complete and consistent with its folder, dependencies that exist, owners from `docs/team/members.yaml`, exposed files present once past `planned`), migrations (`check-migrations.py`: every table a migration creates has `organisation_id` and an RLS policy on `app.organisation_id`), ruff, conventional commits scoped by module, one module per PR. The scripts' own tests run in the same job. `auto-assign.yml` hands each person their next issue the moment their current one closes (one open issue per person). `metrics.yml` publishes the per-person status report to the `team-status` branch every 6 hours.

Planned jobs (stack: FastAPI + React + PostgreSQL, see ADR-0002):

| Job | Purpose |
|---|---|
| `module-boundaries` | import-linter (Python) + ESLint no-restricted-imports (TS): fail on imports outside the module and `packages/` |
| `contracts-lint` | Validate every `contracts/*.yaml` |
| `test-changed-modules` | Run tests only for modules touched by the PR |
| `test-contract` | Run root `tests/contract` on every PR |
| `test-system` | Root `tests/integration` on merge to `main`; `tests/performance` on demand (`tests/e2e` is live in `system.yml`) |
| `build-apps` | Build `apps/*` with their enabled module lists |
