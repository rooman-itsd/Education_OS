# On-call and alert routing

## Who

| Role | Person | What they do |
|---|---|---|
| Primary | Srujan (owner of `infra/`) | Takes the alert, follows the runbook, fixes or escalates |
| Backup | Himanshu (code owner of `infra/`, #429) | Takes over when the primary does not answer in 15 minutes |
| Escalation | Faizan (lead) | Decides on suspending a tenant, rolling back a release, or telling customers |

The rota for each week, with the names on call and the on-call phone, is kept in the team's password manager, not
in git. **Proposed for v1.0 (the lead confirms):** one primary and one backup per week, handover on Monday at
10:00 standup, and the on-call phones are in the alert group below.

## How an alert reaches you

1. `eos-monitor` runs on the API host every minute (`../monitoring/README.md`). When a check starts failing it
   sends one message, repeats it every 60 minutes while it keeps failing, and sends one more when it recovers.
2. The message goes to the journal (`journalctl -t eos-monitor -g ALERT`) and, once `EOS_MONITOR_WEBHOOK_URL`
   is set in `/etc/eos/monitor.env`, to the **Telegram group** the on-call phones have joined. Each message starts
   with `[<label>]` (`staging` or `production`), so you know which host it is.
3. Backend errors also go to Sentry (backend only, from v1.0) when `EOS_SENTRY_DSN` is set; Sentry is for finding
   the cause, the Telegram group is for being woken up.
4. A recovery message with no action from you means it fixed itself: still read the journal the next morning.

If the alert group is silent for a day, that is not proof that all is well: `eos-monitor` runs on the host it
watches, so a host that is down sends nothing. A free external uptime check on the public URL covers that and is
on the list for after launch.

## What to do first

Open the host, then find the alert's check below.

```
cd /opt/education-os
C="docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api"
$C ps
journalctl -t eos-monitor --since "1 hour ago" --no-pager | tail -30
```

| Check | Means | First action |
|---|---|---|
| `health` | The API does not answer `ok` on `127.0.0.1:8000` | `$C logs --tail 100 api`. If it started failing right after a deploy (`journalctl -t eos-api-autodeploy -n 20`), [roll back](roll-back-a-deploy.md). Otherwise `$C restart api` and watch the next minute's check |
| `containers` | One of `db api relay scheduler` is not running, or Docker is not answering | `$C ps -a`, then `$C up -d`. If `db` keeps stopping, check the disk first (below), then `$C logs --tail 100 db` |
| `errors` | More than 5 answers with status 5xx in 5 minutes | `$C logs --since 10m api \| tail -60` and Sentry. A single failing route with one cause is a bug to report; everything failing is a [rollback](roll-back-a-deploy.md) or [restore](restore.md) |
| `slow` | More than 10 requests slower than 2 s in 5 minutes | [scale-the-api.md](scale-the-api.md): look at `docker stats --no-stream` before changing anything |
| `backup` | The last successful backup is missing or over 26 hours old | `journalctl -u eos-db-backup.service -n 30 --no-pager`, then `systemctl start eos-db-backup.service`. A failure that names the offsite copy means the second location is unreachable; the local dump is still made. Check the disk |
| `disk` | `/` is 85 % full or more | `df -h /` and `docker system df`. Free the build cache with `docker builder prune -af` (auto-deploy already does this after each deploy, #392). If the dumps fill it, see `../backup-dr/README.md` |
| `config` | The webhook URL in `/etc/eos/monitor.env` did not load | Put the value in double quotes, `EOS_MONITOR_WEBHOOK_URL="https://...?...&..."`, then `systemctl start eos-monitor.service` |

## Severity and who to call

| Severity | Example | Act within | Tell |
|---|---|---|---|
| 1 | Site or sign-in down, data loss, a leaked secret, a tenant seeing another tenant's data | Now, any hour | Faizan at once, then the team channel |
| 2 | One module failing, errors above the alert level, a failed backup | The same working day | Team channel |
| 3 | Disk warning, one slow route, a failed retry that recovered | Next working day | A ticket |

A suspected data leak between organisations is always severity 1: [suspend the tenant](suspend-a-tenant.md) if one
organisation is the source, and tell Faizan before anything else.

## After an incident

Within two working days write what happened, the times, what fixed it, and what would have caught it earlier, as an
issue labelled `incident`. If a runbook was missing or wrong, fix it in the same pull request.
