# tests/performance

Load tests for the composed API (#152), run on demand, never in CI and **never against production**: they register
organisations. [load/run.py](load/run.py) refuses to start unless the API reports `dev_mode`, which production never
has, and names everything it creates `load-<run>-...`.

| File | What |
|---|---|
| [load/run.py](load/run.py) | Seeds organisations (register, verify, approve, Standard plan, a management user), then runs four scenarios at rising numbers of simultaneous users and prints, per scenario and stage: requests per second, p50/p95/p99 response time, error rate. Exit 1 when an objective is missed |
| [slo.yaml](slo.yaml) | The service level objectives the run is checked against. **Proposed; the lead confirms them** |

## Scenarios

| Scenario | What one virtual user does, in a loop with no pause |
|---|---|
| `signin` | `POST /identity/auth/login` as one of the seeded admins (a password hash check each time) |
| `dashboard` | Opens the Organisation Admin dashboard: the seven GETs it sends together (`/identity/auth/me`, `/billing/plans`, `/billing/subscription`, `/billing/invoices`, `/tenancy/organisation/entitlement`, `/identity/users`, `/audit/records?limit=5`), as that organisation, so row-level security applies to every read |
| `management` | Opens the Management dashboard as the organisation's management user: `/identity/auth/me` and six widget GETs, five of them feature modules (`/admissions/reports/funnel`, `/fees-accounts/reports/collection-vs-target`, `/grievance/stats/open`, `/regulatory-reports/calendar`, `/productions/upcoming`) plus `/reporting/widgets/attendance-and-results`. A feature module's request passes the host's entitlement gate, which looks up the organisation's entitlement first; `dashboard` reads platform services only and never pays that |
| `registration` | `POST /tenancy/register` for a new organisation |

`--scenarios dashboard,management` runs only those (default: all four).

Users never pause, so **50 simultaneous users here is far more load than 50 people**: a person opens a dashboard every
half minute or so, not continuously.

## Run it

Against a stack started for the purpose, with the load generated **inside Docker's network** (from Windows, Docker
Desktop's port forwarding is slower than the API and would be measured instead). From the repository:

```
# 1. A throwaway stack: its own project name, dev mode on (scratch.env holds EOS_DB_PASSWORD, EOS_APP_DB_PASSWORD,
#    EOS_JWT_SECRET, EOS_SUPER_ADMIN_EMAIL, EOS_SUPER_ADMIN_PASSWORD, EOS_DEV_MODE=true, EOS_API_TAG=loadtest, and
#    EOS_RATE_LIMIT_AUTH_PER_MINUTE, EOS_RATE_LIMIT_AUTH_BURST, EOS_RATE_LIMIT_LOGIN_PER_MINUTE and
#    EOS_RATE_LIMIT_LOGIN_BURST at 100000: every virtual user signs in from the generator's one address, so the
#    gateway's sign-in limits would refuse them. The limiter stays on, so its cost is measured)
docker compose -p eosload -f infra/docker/docker-compose.api.yml --env-file scratch.env up -d --build

# 2. The load, from a container on the same network, using the API image's Python (it has httpx and pyyaml)
docker run --rm --network eosload_default -e EOS_SUPER_ADMIN_EMAIL -e EOS_SUPER_ADMIN_PASSWORD \
  -v "$PWD/tests/performance:/perf:ro" --entrypoint python eos-api:loadtest \
  /perf/load/run.py --base http://api:8000 --orgs 50 --stages 10,25,50 --seconds 20 --processes 4

# 3. Remove it all
docker compose -p eosload -f infra/docker/docker-compose.api.yml --env-file scratch.env down -v
```

`--processes` splits the users over several generator processes: one Python process tops out at a few dozen requests a
second, and would otherwise be what is measured. `--out results.json` keeps the numbers.

On a staging host, run step 2 there against `http://127.0.0.1:8000` (staging runs in dev mode) only with the lead's
agreement: it adds organisations to staging's database. The seeding waits out a `429` (`Retry-After`), so it also
works where the sign-in limits are the production ones; only the `signin` scenario then measures the limiter.

## Results, 20 Nov 2026 (the API gateway on, 43 modules)

The same laptop and settings as 5 Nov below, one API process, 50 users, 20 s, 4 generator processes, the sign-in
limits raised as in step 1:

| Scenario, 50 users | 5 Nov (24 modules) | 20 Nov, run 1 | 20 Nov, run 2 |
|---|---|---|---|
| dashboard | 41 rps, p95 9.0 s | 18.7 rps, p95 19.0 s | 15.0 rps, p95 22.6 s |
| management (new) | | 14.9 rps, p95 22.4 s | 14.6 rps, p95 22.5 s |

The API process ran at a median 120 % CPU (one process's ceiling) during run 2: it is CPU-bound. One request at a
time, each GET took 21 to 45 ms (`/billing/plans`, one SQL statement, 21 ms). A profile of the GIL-holding thread
under sequential requests (py-spy) put the CPU in: the gateway's lookups (`gateway._entitlement` on feature-module
requests, `_organisation_status` on platform ones) about 21 %; `eos_core.db._set_tenant`, two `set_config` statements
per transaction, 11.7 %; FastAPI matching the route across every module's router about 10 %; and FastAPI rebuilding
every dependency of every request about 9 %, because `app.dependency_overrides` is not empty (FastAPI 0.142,
`solve_dependencies`; the host's one override is `faculty_directory`, `apps/backend/src/eos_backend/directories.py`).
The application's own logic is a few percent. A larger connection pool (40 + 10) raised `management` to 20.1 rps
and left `dashboard` at 17.6 rps, within the runs' spread; a larger thread pool (100) made both worse: the process is out of CPU, not
connections.

## Results and capacity note (5 Nov 2026)

A laptop, Docker Desktop with 12 CPUs and 8 GB for its Linux VM; the API stack from `main` (24 modules enabled), 50
seeded organisations, 20 s per scenario and stage, 4 generator processes. These are **indicative**: the generator, the
API and Postgres share one machine, and the numbers moved by ±20 % between runs. The server's own figure for a single
dashboard GET (`duration_ms` in its request log) was 10 to 15 ms at the median, under 40 ms at p95.

Requests per second, and p95 response time in ms:

| Scenario | Users | A: 1 API process (as deployed) | B: 4 API workers | C: 4 workers through PgBouncer |
|---|---|---|---|---|
| dashboard | 10 | 45 rps, 1757 | 78 rps, 1059 | 63 rps, 1168 |
| dashboard | 25 | 42 rps, 4540 | 69 rps, 3131 | 84 rps, 2422 |
| dashboard | 50 | 41 rps, 9030 | 73 rps, 5234 | 63 rps, 6872 |
| signin | 10 | 31 rps, 417 | 34 rps, 402 | 35 rps, 374 |
| signin | 25 | 35 rps, 955 | 41 rps, 973 | 45 rps, 816 |
| signin | 50 | 32 rps, 2432 | 46 rps, 1720 | 39 rps, 2598 |
| registration | 10 | 11 rps, 1097 | 22 rps, 618 | 22 rps, 716 |
| registration | 25 | 12 rps, 3359 | 24 rps, 1759 | 24 rps, 1504 |
| registration | 50 | 12 rps, 7453 | 25 rps, 5901 | 25 rps, 2884 |

No request failed in B or C. In A one dashboard request in about 900 was dropped on the client side inside Docker (no
5xx and no error in the API's log).

**What it means**

- **One API process is the limit today**: about 40 dashboard requests a second (some six dashboards opened per second)
  and about 30 sign-ins a second, whatever the load; beyond that, requests queue and the response time grows with the
  number of users. A person who opens a dashboard every half minute makes about 0.2 requests a second, so one process
  serves roughly 150 to 200 people working at the same moment on this machine. A real server can differ either way:
  run the test there before relying on the figure.
- **Four worker processes give about 1.7 times the throughput**, not four: on this laptop the API, Postgres and the
  generator compete for the same CPUs. Workers are the next step when the server has the cores (`uvicorn --workers`,
  a change to `infra/docker/api.Dockerfile`, with the lead's agreement).
- **PgBouncer changes neither speed nor errors at this scale.** Its value is a bounded number of Postgres connections
  once there are several worker processes or hosts: four workers alone held 23 connections; Postgres allows 100.
- **The proposed objectives are not met at 50 non-stop users**, in any configuration. They are met at 10 for sign-in
  and registration. Either the objectives assume fewer simultaneous users, or the API needs the next step below.
- **Next step for speed**: each dashboard GET costs 10 to 15 ms of server time, but one process completes only about 40
  a second, so time goes into the request path around the endpoints (two `BaseHTTPMiddleware` layers, the thread
  pool). Profiling that path is a follow-up worth more than extra hardware.
