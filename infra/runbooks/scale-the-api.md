# Scale the API

Use this when the `slow` or `errors` alert fires and the cause is load, not a bug: many requests slower than 2 s,
the API container near its memory limit, or the host's CPU at 100 %. First find out which, then change one thing.

**Who decides:** the host owner (Srujan). Tell the lead before changing a production container's size.

## What runs, and what can be scaled

| Part | Count | Scale it by |
|---|---|---|
| API (`api`, one `uvicorn` process) | 1 | Give the host more CPU and memory. More processes are a code change, see below |
| Event-bus relay (`relay`) | 1 | One is enough; do not start a second by hand |
| Scheduler (`scheduler`) | 1 | One per deployment; do not start a second by hand |
| Postgres (`db`) | 1 | More memory for the host; see "The database" below |

## 1. Look before you change anything

```
cd /opt/education-os
C="docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api"
docker stats --no-stream
free -m; df -h /; uptime
$C logs --since 10m api | tail -60
journalctl -t eos-monitor --since "1 hour ago" --no-pager | tail -20
```

| You see | Likely cause | Do |
|---|---|---|
| `api` CPU near 100 % of one core while the host has spare cores | One process is the limit | Section 2 does not help; ask for more worker processes (section 3) |
| The host's CPU or load at its limit | The container is too small | Section 2 |
| Memory near the limit, `db` or `api` restarting | Out of memory | Section 2 (memory first), then check for a leak: does memory fall after `$C restart api`? |
| Slow only for one route or one organisation | A heavy query, not load | Find it in the logs (the `request` lines carry `organisation_id`) and report it; do not scale |
| Slow right after a deploy | A regression | [roll-back-a-deploy.md](roll-back-a-deploy.md) |

## 2. Give the container more CPU and memory

In the Proxmox web interface: the container → **Resources** → **Cores** and **Memory** → **Edit**. Both apply to a
running container without a restart. Raise memory before CPU, in steps (for example from 4 GB to 6 GB), then watch
`docker stats` for ten minutes. Check the node itself has the capacity: Proxmox → the node's **Summary**.

Write the old and new sizes in the team channel so the next person knows.

## 3. More worker processes

Today the API runs one `uvicorn` process (`infra/docker/api.Dockerfile` gives no `--workers`). The load test
(`tests/performance/`, #152) measured what that process can do, and what more processes add.

**What was measured** (5 Nov 2026, a laptop with Docker, 50 organisations, users with no pause between requests; the
full table is in `../../tests/performance/README.md`):

| At 50 simultaneous users | 1 process (as deployed) | 4 worker processes | 4 workers through PgBouncer |
|---|---|---|---|
| Dashboard requests per second | about 41 | about 73 | about 63 |
| Dashboard p95 | 9.0 s | 5.2 s | 6.9 s |
| Sign-ins per second | about 32 | about 46 | about 39 |
| Errors | none | none | none |

- **One process is the first limit.** It serves about 40 dashboard requests a second, whatever the load; beyond that,
  requests queue and the response time grows with the number of users. A person opens a dashboard every half minute or
  so, which is roughly 150 to 200 people working at the same moment per process on that machine. A real server
  differs: measure it there before relying on the figure (below).
- **Four workers gave about 1.7 times the throughput**, not four: on the laptop the API, Postgres and the load
  generator shared the same CPUs. On the server, workers help as far as the container has cores for them.
- **PgBouncer changed neither speed nor errors.** It matters once there are several processes: each process keeps up
  to 15 Postgres connections (SQLAlchemy's default pool), so 4 workers plus the relay and the scheduler reach about 90
  of the 100 Postgres allows, while through PgBouncer they share 20.

**When to add workers.** The `api` CPU sits near 100 % of one core under load while the container has idle cores
(`docker stats`, section 1), and section 2 has already given it the cores.

**How.** Not on the host (auto-deploy resets the checkout to `main`); it is a pull request, with the lead's agreement:

1. **Switch the pooler on first** (`../docker/README.md`, "Connection pooler"), so more processes don't exhaust
   Postgres's connections, and check it as that section says.
2. **Set the number of workers.** `uvicorn` starts `$WEB_CONCURRENCY` processes when `--workers` is not given, which
   is the case in `api.Dockerfile`. The pull request passes it to the `api` service in `docker-compose.api.yml`
   (for example `WEB_CONCURRENCY: ${EOS_API_WORKERS:-1}`, so every host keeps one process until it sets
   `EOS_API_WORKERS`). Choose no more workers than the container's cores, and start with 2.
3. **Measure before and after** on staging, with the lead's agreement (the test adds `load-…` organisations to its
   database): run `tests/performance/load/run.py` there as `../../tests/performance/README.md`, "Run it", says, once
   before the change and once after, and keep both `--out` files with the pull request.
4. Watch the `slow` and `errors` checks for a day (below). If it got worse, set `EOS_API_WORKERS` back to 1.

**What workers don't fix.** Each dashboard request takes only 10 to 15 ms inside the API, yet one process completes
about 40 a second, so most of the time goes into the path around the endpoints (the middleware and the thread pool),
not the database. Profiling that path is the bigger win, and is a code change, not an operation.

## The database

- Postgres connections are the next limit after CPU. See what is connected:
  `$C exec -T db psql -U eos -d eos -c "SELECT usename, count(*) FROM pg_stat_activity GROUP BY 1"`.
- Do not change Postgres settings by hand on production. A change that helps goes through a pull request, so staging
  gets it first.

### Is a slow query using an index under row-level security?

Every table with `organisation_id` has an index that starts with it (`apps/backend/tests/test_organisation_indexes.py`
checks this on every pull request), so a query of one organisation should use it. Check a slow query as the API sees it:
as `eos_app`, inside one organisation, with `EXPLAIN ANALYZE`. Take the organisation's id from the slow `request` log
line; the query is an example, put the slow one in its place:

```
$C exec -T db psql -U eos -d eos
SET ROLE eos_app;
BEGIN;
SELECT set_config('app.organisation_id', '<organisation id>', true);
EXPLAIN ANALYZE SELECT * FROM helpdesk_ticket WHERE status = 'open' ORDER BY created_at DESC LIMIT 20;
ROLLBACK;
```

`Index Scan` or `Bitmap Index Scan` on an `organisation_id` index is what you want. `Seq Scan` on a big table means a
missing index for that filter: report it to the module's owner with the plan. On a small table a `Seq Scan` is normal:
Postgres reads a few pages faster than it would use an index.

## After scaling

Watch the `slow` and `errors` checks for a day. Note in the incident issue what the numbers were before and after.
