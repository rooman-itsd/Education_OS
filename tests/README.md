# tests/

Repo-level test suites. Everything here spans **more than one module** or exercises the
composed apps. Tests that belong to a single module stay inside that module so the module
remains portable.

## Where a test goes

| Test is about | Put it in | Runs with |
|---|---|---|
| One module's domain / use-case logic | `<module>/backend/tests/` | module alone |
| One module's React pages / components | `<module>/frontend/tests/` | module alone |
| One module end to end against platform stubs | `<module>/tests/e2e/` | module + `packages/testing` stubs |
| Two or more modules talking via API or events | [`tests/integration/`](integration/) | `apps/backend` with those modules enabled |
| A module honouring another module's published contract | [`tests/contract/`](contract/) | consumer + provider contracts only |
| Full user journeys through `apps/frontend` / `apps/mobile` | [`tests/e2e/`](e2e/) | full stack via `infra/docker` |
| Load, soak, stress | [`tests/performance/`](performance/) | full stack, on demand |
| Shared seed data, factories, fixtures used by the suites above | [`tests/fixtures/`](fixtures/) | — |

Rule of thumb: if the test would still make sense after the module is copied to another
repo, it belongs in the module. Otherwise it belongs here.

## Layout inside each suite

```
tests/<suite>/
├── README.md              what this suite covers, how to run it
├── conftest.py            pytest fixtures (API-level suites)
└── <feature-or-flow>/     one folder per journey or module pair, e.g. admissions-to-fees/
```

- API-level suites (`integration`, `contract`, `performance`): **pytest**.
- Browser suites (`e2e`): **Playwright** (TypeScript).
- Name files `test_<what>.py` / `<what>.spec.ts`.

## Running

```
pnpm --filter e2e e2e                  # Playwright; starts its own API and web server, see e2e/README.md
```

Planned, added with their first suite:

```
uv run pytest tests/integration        # needs apps/backend up with modules enabled
uv run pytest tests/contract
uv run pytest tests/performance -m load
```

CI runs `tests/contract` on every PR and `tests/integration` + `tests/e2e` on merge to `main`.
See [.github/workflows/README.md](../.github/workflows/README.md).
