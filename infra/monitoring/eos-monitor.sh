#!/usr/bin/env bash
# Checks the API host every minute (eos-monitor.timer) and alerts when something breaks and when it recovers.
# Settings in /etc/eos/monitor.env (see eos-monitor.env.example); every one has a default.
#
# Checks: the API answers /api/v1/health; the compose services run; the last database backup is recent; the
# API's 5xx answers and slow requests over the last few minutes, counted from its JSON `request` log lines
# (apps/backend observability.py); the disk is not nearly full.
#
# An alert is sent when a check starts failing, again every EOS_MONITOR_REMIND_MIN while it keeps failing,
# and once when it recovers; never every minute. Alerts always go to the journal (journalctl -t eos-monitor),
# and also to EOS_MONITOR_WEBHOOK_URL when it is set: a POST of {"text": "..."}, which Slack, Mattermost,
# Google Chat and a Telegram bot (.../sendMessage?chat_id=<id>) all accept. Alerts carry counts and names
# only, never log lines, so nothing personal leaves the host.
set -uo pipefail

CONFIG="${EOS_MONITOR_CONFIG:-/etc/eos/monitor.env}"
# shellcheck source=/dev/null
[ -f "$CONFIG" ] && . "$CONFIG"

APP_DIR="${EOS_APP_DIR:-/opt/education-os}"
COMPOSE_FILE="${EOS_COMPOSE_FILE:-$APP_DIR/infra/docker/docker-compose.api.yml}"
ENV_FILE="${EOS_ENV_FILE:-$APP_DIR/infra/docker/.env.api}"
STATE_DIR="${EOS_MONITOR_STATE_DIR:-/var/lib/eos-monitor}"
LABEL="${EOS_MONITOR_LABEL:-$(hostname)}"
WEBHOOK="${EOS_MONITOR_WEBHOOK_URL:-}"
REMIND_MIN="${EOS_MONITOR_REMIND_MIN:-60}"
HEALTH_URL="${EOS_MONITOR_HEALTH_URL:-http://127.0.0.1:8000/api/v1/health}"
HEALTH_RETRY_S="${EOS_MONITOR_HEALTH_RETRY_S:-10}"
SERVICES="${EOS_MONITOR_SERVICES:-db api relay scheduler}"
BACKUP_MARK="${EOS_MONITOR_BACKUP_MARK:-/var/backups/eos/last-success}"
BACKUP_MAX_AGE_H="${EOS_MONITOR_BACKUP_MAX_AGE_H:-26}"
WINDOW="${EOS_MONITOR_WINDOW:-5m}"
MAX_5XX="${EOS_MONITOR_MAX_5XX:-5}"
SLOW_MS="${EOS_MONITOR_SLOW_MS:-2000}"
MAX_SLOW="${EOS_MONITOR_MAX_SLOW:-10}"
DISK_PATH="${EOS_MONITOR_DISK_PATH:-/}"
DISK_MAX_PCT="${EOS_MONITOR_DISK_MAX_PCT:-85}"
DOCKER_TIMEOUT_S="${EOS_MONITOR_DOCKER_TIMEOUT_S:-20}"

log() {
  echo "$*"
  # Under systemd the line above already reaches the journal; send it once more only for a manual run.
  if [ -z "${INVOCATION_ID:-}" ] && command -v logger >/dev/null; then logger -t eos-monitor "$*"; fi
}
# Bounded, so a hung Docker daemon fails the check instead of the whole run being killed by systemd.
compose() { timeout "$DOCKER_TIMEOUT_S" docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"; }

# Returns non-zero when the webhook did not take the alert, so the caller keeps its state and retries next run.
alert() {
  local text="[$LABEL] $*"
  log "ALERT: $text"
  [ -n "$WEBHOOK" ] || return 0
  local escaped
  escaped="$(printf '%s' "$text" | sed 's/\\/\\\\/g; s/"/\\"/g')"
  # The URL goes through stdin, not the command line: it holds the webhook's secret, and `ps` shows arguments.
  curl -fsS -m 10 -o /dev/null -H 'Content-Type: application/json' -d "{\"text\": \"$escaped\"}" -K - \
    <<<"url = \"$WEBHOOK\"" && return 0
  log "the alert could not be posted to the webhook (it is in the journal above); retrying next run"
  return 1
}

# One check's result: "" when it passes, else what is wrong. Remembers when it last alerted (a file per
# check in STATE_DIR), so an alert goes out on a change and as a reminder, not every minute. The state changes
# only once the alert was delivered.
failing=0
report() {
  local name="$1" problem="$2" mark="$STATE_DIR/$1" now last
  now="$(date +%s)"
  if [ -n "$problem" ]; then
    failing=$((failing + 1))
    if [ ! -f "$mark" ]; then
      alert "FAILING $name: $problem" && echo "$now" >"$mark"
      return
    fi
    # An empty or damaged mark (a full disk can leave one) counts as "alerted long ago", not as an error.
    last="$(cat "$mark" 2>/dev/null)"
    case "$last" in '' | *[!0-9]*) last=0 ;; esac
    if [ $((now - last)) -ge $((REMIND_MIN * 60)) ]; then
      alert "STILL FAILING $name: $problem" && echo "$now" >"$mark"
    else
      log "failing $name: $problem (alerted already)"
    fi
  elif [ -f "$mark" ]; then
    alert "RECOVERED $name" && rm -f "$mark"
  fi
}

mkdir -p "$STATE_DIR"

# The settings file is read as shell, so an unquoted webhook URL with `&` in it (Google Chat's has two) runs
# in the background and leaves the setting empty. Never silently: that is a failing check of its own.
problem=""
if [ -z "$WEBHOOK" ] && [ -f "$CONFIG" ] &&
  grep -Eq '^EOS_MONITOR_WEBHOOK_URL=([^"[:space:]]|"[^"])' "$CONFIG"; then
  problem="EOS_MONITOR_WEBHOOK_URL in $CONFIG did not load, so alerts reach the journal only: put the URL in double quotes"
fi
report config "$problem"

# The API answers. Asked twice before failing: an auto-deploy restarts it for a few seconds.
health() {
  local body
  body="$(curl -fsS -m 5 "$HEALTH_URL" 2>&1)" || { echo "$HEALTH_URL does not answer: ${body:0:120}"; return; }
  printf '%s' "$body" | grep -q '"status": *"ok"' || echo "$HEALTH_URL does not say ok"
}
problem="$(health)"
[ -z "$problem" ] || { sleep "$HEALTH_RETRY_S"; problem="$(health)"; }
report health "$problem"

# Every service runs (a stopped relay means no event is acted on, a stopped scheduler no job runs).
problem=""
running="$(compose ps --status running --services 2>&1)"
rc=$?
if [ "$rc" = 0 ]; then
  missing=""
  for s in $SERVICES; do printf '%s\n' "$running" | grep -qx "$s" || missing="$missing $s"; done
  [ -z "$missing" ] || problem="not running:$missing"
elif [ "$rc" = 124 ]; then
  problem="docker did not answer within ${DOCKER_TIMEOUT_S}s"
else
  problem="docker compose ps failed: ${running:0:120}"
fi
report containers "$problem"

# The nightly backup succeeded recently (eos-db-backup writes the mark only on success).
problem=""
if [ "$BACKUP_MAX_AGE_H" -gt 0 ]; then
  if [ ! -f "$BACKUP_MARK" ]; then
    problem="no successful backup recorded ($BACKUP_MARK is missing)"
  else
    age_h=$((($(date +%s) - $(stat -c %Y "$BACKUP_MARK")) / 3600))
    [ "$age_h" -lt "$BACKUP_MAX_AGE_H" ] || problem="the last successful backup is ${age_h}h old: journalctl -t eos-db-backup"
  fi
fi
report backup "$problem"

# 5xx answers and slow requests, from the API's `request` lines (one JSON object each).
errors_problem=""
slow_problem=""
if logs="$(compose logs --no-log-prefix --since "$WINDOW" api 2>/dev/null)"; then
  read -r n5xx nslow < <(printf '%s\n' "$logs" | awk -v slow="$SLOW_MS" '
    /"event": *"request"/ {
      if (match($0, /"status": *[0-9]+/)) { s = substr($0, RSTART, RLENGTH); sub(/.*: */, "", s); if (s + 0 >= 500) e++ }
      if (match($0, /"duration_ms": *[0-9.]+/)) { d = substr($0, RSTART, RLENGTH); sub(/.*: */, "", d); if (d + 0 > slow) w++ }
    }
    END { print e + 0, w + 0 }')
  [ "$n5xx" -le "$MAX_5XX" ] ||
    errors_problem="$n5xx answers with status 5xx in the last $WINDOW (more than $MAX_5XX): docker compose logs --since $WINDOW api"
  [ "$nslow" -le "$MAX_SLOW" ] ||
    slow_problem="$nslow requests slower than ${SLOW_MS} ms in the last $WINDOW (more than $MAX_SLOW)"
else
  errors_problem="the api logs could not be read"
fi
report errors "$errors_problem"
report slow "$slow_problem"

# The disk the databases and backups live on.
problem=""
used="$(df -P "$DISK_PATH" | awk 'NR == 2 { sub(/%/, "", $5); print $5 }')"
[ -z "$used" ] || [ "$used" -lt "$DISK_MAX_PCT" ] || problem="$DISK_PATH is ${used}% full (alert at $DISK_MAX_PCT%)"
report disk "$problem"

if [ "$failing" -gt 0 ]; then
  exit 1
fi
log "ok"
