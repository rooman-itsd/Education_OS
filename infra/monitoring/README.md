# infra/monitoring

Metrics, logs, traces, dashboards and alert rules (#91). Phase 1: a check on the API host every minute that
alerts when something breaks and when it recovers. The API's own logs and Sentry are described in
`apps/backend/README.md` ("Logs and errors").

## eos-monitor: what it checks

`eos-monitor.sh`, run every minute by `eos-monitor.timer` on the API host.

| Check | Fails when (defaults; all in `/etc/eos/monitor.env`) |
|---|---|
| `health` | `http://127.0.0.1:8000/api/v1/health` does not answer `ok` within 5 s, twice 10 s apart |
| `containers` | one of the compose services `db api relay scheduler` is not running |
| `backup` | `/var/backups/eos/last-success` (written by `eos-db-backup` on success) is missing or 26 h old |
| `errors` | more than 5 API answers with status 5xx in the last 5 minutes, or the API's logs cannot be read |
| `slow` | more than 10 API requests slower than 2000 ms in the last 5 minutes |
| `disk` | `/` is 85 % full or more |

`errors` and `slow` count the API's JSON `request` lines (`EOS_LOG_FORMAT=json`, the default); with the console
format they see nothing.

## Alerts

- An alert is sent when a check **starts failing**, again **every 60 minutes** while it keeps failing, and once
  when it **recovers**; never every minute. `/var/lib/eos-monitor/<check>` holds when it last alerted.
- Alerts always go to the journal: `journalctl -t eos-monitor`. Each starts with `ALERT: [<label>]`.
- With `EOS_MONITOR_WEBHOOK_URL` set, each alert is also posted as `{"text": "..."}`. Slack, Mattermost and
  Google Chat incoming webhooks take that as is; for a Telegram bot use
  `https://api.telegram.org/bot<token>/sendMessage?chat_id=<chat id>`. The URL is a secret: it stays in
  `/etc/eos/monitor.env` (mode 600), never in git, and is passed to curl on stdin, not on its command line.
- Alerts carry counts, service names and paths only, never log lines, so nothing personal leaves the host.

## Install (once per API host, as root)

```
cd /opt/education-os && git pull
bash infra/monitoring/install.sh
```

Re-run `install.sh` after `eos-monitor.sh` changes (the copy in `/usr/local/bin` is not auto-updated); the
settings in `/etc/eos/monitor.env` are kept. To set the webhook or a label:

```
nano /etc/eos/monitor.env          # EOS_MONITOR_WEBHOOK_URL=..., EOS_MONITOR_LABEL=staging
systemctl start eos-monitor.service; journalctl -t eos-monitor -n 20 --no-pager
```

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
