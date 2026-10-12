# tests/e2e

Full user journeys through `apps/frontend` in a real browser (Playwright). Each run starts its own API
(`apps/backend`, on port 8100) and web dev server (port 5180) with a fresh SQLite database, so it never
touches a dev server you have running, and stops them afterwards.

| Journey | Spec |
|---|---|
| Register an organisation, verify the email, sign-in refused until a super admin approves, sign in, land on the Organisation Admin dashboard | [onboarding/register-approve-signin.spec.ts](onboarding/register-approve-signin.spec.ts) |

The approval step calls the API until the super admin approval queue exists in `apps/frontend`.

## Run

Once: set up Python (`tools/scripts/py-setup.sh`), `pnpm install`, then download the browser:

```
pnpm --filter e2e e2e:install
```

Every time:

```
pnpm --filter e2e e2e            # headless
pnpm --filter e2e e2e:headed     # watch it click through
pnpm --filter e2e e2e:report     # open the HTML report of the last run
```

Failures keep a screenshot and a trace in `tests/e2e/.cache/test-results/`
(`pnpm exec playwright show-trace <trace.zip>` replays it step by step).

| Env var | Default | Use |
|---|---|---|
| `E2E_PYTHON` | `.venv/bin/python` (`.venv\Scripts\python.exe` on Windows) | Python with the backend installed |
| `E2E_API_PORT`, `E2E_WEB_PORT` | `8100`, `5180` | Ports for the suite's own servers |

The script is `e2e`, not `test`, on purpose: `web.yml` runs every package's `test` script on each PR,
and this suite needs browsers and both servers. CI runs it on merge to `main` once that job exists.

## Adding a journey

One folder per journey (`tests/e2e/<journey>/<what>.spec.ts`). Find elements the way a person does:
`getByRole`, `getByLabel` (with `exact: true` when one label is part of another), `getByText`. Give each
run its own organisation slug so journeys never collide.
