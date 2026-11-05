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

Today the API starts one `uvicorn` process (`infra/docker/api.Dockerfile`). Starting more is a change to the
repository, not something to edit on the host (auto-deploy resets the checkout to `main`), and it should wait for
two things, because several processes mean several sets of database connections:
- the **connection pooler** (PgBouncer, #96), and
- a **load test with the numbers** (#152), so the worker count is chosen from a measurement.

This runbook is updated with the exact change when those land. Until then, scale up (section 2) and keep one process.

## The database

- Postgres connections are the next limit after CPU. See what is connected:
  `$C exec -T db psql -U eos -d eos -c "SELECT usename, count(*) FROM pg_stat_activity GROUP BY 1"`.
- Do not change Postgres settings by hand on production. A change that helps goes through a pull request, so staging
  gets it first.

## After scaling

Watch the `slow` and `errors` checks for a day. Note in the incident issue what the numbers were before and after.
