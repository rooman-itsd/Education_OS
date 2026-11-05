# tests/performance

Load tests for the composed API (#152), run on demand, never in CI and **never against production**: they register
organisations. [load/run.py](load/run.py) refuses to start unless the API reports `dev_mode`, which production never
has, and names everything it creates `load-<run>-...`.

| File | What |
|---|---|
| [load/run.py](load/run.py) | Seeds organisations (register, verify, approve), then runs three scenarios at rising numbers of simultaneous users and prints, per scenario and stage: requests per second, p50/p95/p99 response time, error rate. Exit 1 when an objective is missed |
| [slo.yaml](slo.yaml) | The service level objectives the run is checked against. **Proposed; the lead confirms them** |

## Scenarios

| Scenario | What one virtual user does, in a loop with no pause |
|---|---|
| `signin` | `POST /identity/auth/login` as one of the seeded admins (a password hash check each time) |
| `dashboard` | Opens the Organisation Admin dashboard: the seven GETs it sends together (`/identity/auth/me`, `/billing/plans`, `/billing/subscription`, `/billing/invoices`, `/tenancy/organisation/entitlement`, `/identity/users`, `/audit/records?limit=5`), as that organisation, so row-level security applies to every read |
| `registration` | `POST /tenancy/register` for a new organisation |

Users never pause, so **50 simultaneous users here is far more load than 50 people**: a person opens a dashboard every
half minute or so, not continuously.

## Run it

Against a stack started for the purpose, with the load generated **inside Docker's network** (from Windows, Docker
Desktop's port forwarding is slower than the API and would be measured instead). From the repository:

```
# 1. A throwaway stack: its own project name, dev mode on (scratch.env holds EOS_DB_PASSWORD, EOS_APP_DB_PASSWORD,
#    EOS_JWT_SECRET, EOS_SUPER_ADMIN_EMAIL, EOS_SUPER_ADMIN_PASSWORD, EOS_DEV_MODE=true, EOS_API_TAG=loadtest)
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
agreement: it adds organisations to staging's database.

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
