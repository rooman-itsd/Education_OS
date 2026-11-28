# infra/monitoring

Metrics, logs, traces, dashboards and alert rules (#91). Phase 1: a check on the API host every minute that
alerts when something breaks and when it recovers. The API's own logs and Sentry are described in
`apps/backend/README.md` ("Logs and errors").

## eos-monitor: what it checks

`eos-monitor.sh`, run every minute by `eos-monitor.timer` on the API host.

| Check | Fails when (defaults; all in `/etc/eos/monitor.env`) |
|---|---|
| `config` | `EOS_MONITOR_WEBHOOK_URL` is in the settings file but did not load (an unquoted URL with `&`) |
| `deploy` | the API auto-deploy rolled back (`/var/lib/eos/api-autodeploy.failed`), its last run failed (a migration), or a deploy has run for 30 minutes |
| `health` | `http://127.0.0.1:8000/api/v1/health` does not answer `ok` within 5 s, twice 10 s apart |
| `containers` | one of the compose services `db api relay scheduler` is not running (asked twice, 10 s apart), or Docker does not answer in 20 s |
| `backup` | `/var/backups/eos/last-success` (written by `eos-db-backup` on success) is missing or 26 h old |
| `errors` | more than 5 API answers with status 5xx in the last 5 minutes, or the API's logs cannot be read |
| `slow` | more than 10 API requests slower than 2000 ms in the last 5 minutes |
| `disk` | `/` is 85 % full or more |

`errors` and `slow` count the API's JSON `request` lines (`EOS_LOG_FORMAT=json`, the default; #379); before
those are deployed, or with the console format, they always pass.

**During an auto-deploy** (`/run/eos/api-deploying` exists, written by `../autodeploy/eos-api-autodeploy.sh` for
the whole deploy, build included), `health`, `containers`, `errors` and `slow` are logged as `failing <check>
during the deploy`, not alerted: the API restarts for about a minute, and Docker answers slowly while the image
builds. `config`, `deploy`, `backup` and `disk` alert as always. After 30 minutes (`EOS_MONITOR_DEPLOY_MAX_MIN`)
nothing is held any more and `deploy` fails. Before 25 Nov every merge sent four alerts per host (FAILING and
RECOVERED, `health` and `containers`); a single `not running: db` on staging, with `db` up since October, came
from one incomplete answer of a busy Docker daemon, which is why `containers` asks twice.

**What it cannot see.** `/api/v1/health` is static: it answers `ok` while the API process runs, without asking
the database (the `containers` and `errors` checks cover that). And this runs **on** the API host, so when the
whole host is down, nothing alerts: that needs a check from outside (phase 2, or a free external uptime check
on the public URL).

## Alerts

- An alert is sent when a check **starts failing**, again **every 60 minutes** while it keeps failing, and once
  when it **recovers**; never every minute. `/var/lib/eos-monitor/<check>` holds when it last alerted. An
  alert the webhook did not take is sent again the next minute, recoveries included.
- Alerts always go to the journal: `journalctl -t eos-monitor`. Each starts with `ALERT: [<label>]`.
- With `EOS_MONITOR_WEBHOOK_URL` set, each alert is also posted as `{"text": "..."}`. Slack, Mattermost and
  Google Chat incoming webhooks take that as is; for a Telegram bot use
  `https://api.telegram.org/bot<token>/sendMessage?chat_id=<chat id>`. The URL is a secret: it stays in
  `/etc/eos/monitor.env` (mode 600), never in git, and is passed to curl on stdin, not on its command line.
  **Put it in double quotes**, `EOS_MONITOR_WEBHOOK_URL="https://...?key=K&token=T"`: the file is read as
  shell, and without quotes the `&` cuts the line (the `config` check then fails).
- Alerts carry counts, service names and paths only, never log lines, so nothing personal leaves the host.
- Every alert is one line of plain text: a tool's error output (Docker's, curl's) has its newlines, tabs and other
  control characters removed, so the journal keeps it whole and the webhook's JSON stays valid. A numeric setting
  that is not a whole number falls back to its default, with a line in the journal saying so.

## Install (once per API host, as root)

```
cd /opt/education-os && git pull
bash infra/monitoring/install.sh
```

Re-run `install.sh` after `eos-monitor.sh` changes (the copy in `/usr/local/bin` is not auto-updated); the
settings in `/etc/eos/monitor.env` are kept. Automated container deployments (`tools/scripts/deploy-api-lxc.sh`)
install and enable `eos-monitor.timer` automatically in step 5c.

To set the webhook or a label:

```
nano /etc/eos/monitor.env          # EOS_MONITOR_WEBHOOK_URL="...", EOS_MONITOR_LABEL=staging
systemctl start eos-monitor.service; journalctl -t eos-monitor -n 20 --no-pager
```

## Configuring Telegram alerts

The on-call group receives alerts through a Telegram bot (Bot API `sendMessage`). The token and the chat id are
secrets: they live in the password manager and in `/etc/eos/monitor.env` (mode 600), never in git or chat.

1. **Create the bot:** in Telegram, message `@BotFather`, send `/newbot`, name it (e.g. `EOS Alerts`) and keep
   the token it returns.
2. **Create the group:** a group (e.g. `EOS On-call`) with the on-call people, and add the bot. A group needs no
   admin rights for the bot to post; a channel does.
3. **Find the chat id:** in the group send `/start@<bot username>` (with privacy mode on, the default, a bot does
   not see ordinary messages), then open `https://api.telegram.org/bot<token>/getUpdates` and read
   `"chat":{"id":-100…}`, minus sign included.
4. **Configure `/etc/eos/monitor.env`**, keeping the double quotes, and label the host it runs on (`staging` on
   the staging container, `production` only on the production one):
   ```bash
   EOS_MONITOR_WEBHOOK_URL="https://api.telegram.org/bot<token>/sendMessage?chat_id=<chat_id>"
   EOS_MONITOR_LABEL=staging
   ```
5. **Test it:** a message must reach the group (`200`), then the monitor must run without a `config` problem:
   ```bash
   ( . /etc/eos/monitor.env; curl -s -o /dev/null -w "%{http_code}\n" -H 'Content-Type: application/json' \
     -d '{"text":"EOS: alert test"}' "$EOS_MONITOR_WEBHOOK_URL" )
   systemctl start eos-monitor.service; journalctl -t eos-monitor -n 20 --no-pager
   ```

## Sentry error tracking

`eos-monitor` watches the host; the API's unhandled errors go to Sentry (backend only in v1.0, sentry.io free
plan), started by `init_sentry` in `apps/backend/src/eos_backend/observability.py` when a DSN is set.

In `/opt/education-os/infra/docker/.env.api` (the DSN is a secret: password manager and this file only), with the
environment naming the host (`staging` on the staging container, `production` only on the production one; unset
means `staging`):

```bash
EOS_SENTRY_DSN=https://<public-key>@o<org-id>.ingest.sentry.io/<project-id>
EOS_ENVIRONMENT=staging
```

Then, from `/opt/education-os`, restart the API and send a test event; it must appear under Issues in the Sentry
project, tagged with that environment:

```bash
C="docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api"
$C up -d api relay scheduler
$C exec -T api python -c "from eos_backend.observability import init_sentry; import sentry_sdk
print('sentry on:', init_sentry()); sentry_sdk.capture_message('EOS: Sentry test'); sentry_sdk.flush(10)"
```

Nothing personal is sent (DPDP): no request body, cookies, query string, local variables or user, and of the
headers only user agent, content type, content length and accept; email addresses in messages and breadcrumbs become `[email]`. Each event is
tagged with `request_id` and `organisation_id`, so `$C logs api | grep <request_id>` finds its log lines.

What to do when an alert or a Sentry issue arrives is in [the on-call runbook](../runbooks/on-call.md).

## Day to day

```
systemctl list-timers eos-monitor.timer      # when it runs next
journalctl -t eos-monitor --since today      # every result and alert today
journalctl -t eos-monitor -g ALERT           # alerts only
ls /var/lib/eos-monitor                      # checks failing right now
```

**Test an alert:** stop the scheduler (no other service depends on it), wait a minute, start it again:

```
cd /opt/education-os
docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api stop scheduler
sleep 70; journalctl -t eos-monitor -g ALERT -n 5 --no-pager      # FAILING containers: not running: scheduler
docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api start scheduler
sleep 70; journalctl -t eos-monitor -g ALERT -n 5 --no-pager      # RECOVERED containers
```

**Silence a check** for planned work: raise its threshold in `/etc/eos/monitor.env` (e.g.
`EOS_MONITOR_BACKUP_MAX_AGE_H=0` turns the backup check off), or stop the timer:
`systemctl stop eos-monitor.timer`, and `systemctl start eos-monitor.timer` afterwards.

## Tests

`tools/scripts/tests/test_monitor.py` runs the script against a fake `docker` and `curl` (Linux; CI's
governance job runs it).

## Next (phase 2)

Metrics and dashboards (Prometheus, Grafana, Loki or a hosted service) need a decision on where they run; they
are not on `docs/architecture/approved-stack.yaml` yet.
