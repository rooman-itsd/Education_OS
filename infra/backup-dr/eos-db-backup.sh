#!/usr/bin/env bash
# Nightly Postgres backup on the API host (infra/docker/docker-compose.api.yml). Run by
# eos-db-backup.timer; settings in /etc/eos/db-backup.env (see eos-db-backup.env.example).
#
# Writes a compressed pg_dump archive, proves it is readable, keeps KEEP_DAILY nightly and KEEP_WEEKLY
# Sunday copies, optionally copies them to a second location, and records the last success.
set -euo pipefail

CONFIG="${EOS_BACKUP_CONFIG:-/etc/eos/db-backup.env}"
# shellcheck source=/dev/null
[ -f "$CONFIG" ] && . "$CONFIG"

APP_DIR="${EOS_APP_DIR:-/opt/education-os}"
COMPOSE_FILE="${EOS_COMPOSE_FILE:-$APP_DIR/infra/docker/docker-compose.api.yml}"
ENV_FILE="${EOS_ENV_FILE:-$APP_DIR/infra/docker/.env.api}"
BACKUP_DIR="${EOS_BACKUP_DIR:-/var/backups/eos}"
KEEP_DAILY="${EOS_BACKUP_KEEP_DAILY:-14}"
KEEP_WEEKLY="${EOS_BACKUP_KEEP_WEEKLY:-8}"
OFFSITE="${EOS_BACKUP_OFFSITE:-}"
LOCK="${EOS_BACKUP_LOCK:-/run/lock/eos-db-backup.lock}"
DB_USER=eos
DB_NAME=eos

log() {
  echo "$*"
  if command -v logger >/dev/null; then logger -t eos-db-backup "$*"; fi
}
fail() {
  log "FAILED: $*"
  exit 1
}
compose() { docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"; }

# Never two at once (timer and a manual run).
exec 9>"$LOCK"
flock -n 9 || { log "another backup is running; skipping"; exit 0; }

mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"
chmod 700 "$BACKUP_DIR"

stamp="$(date -u +%Y-%m-%dT%H%M%SZ)"
file="$BACKUP_DIR/daily/eos-$stamp.dump"
tmp="$file.partial"
# Never replace an existing backup, whatever the clock says.
[ ! -e "$file" ] || fail "$file already exists"
trap 'rm -f "$tmp"' EXIT

# Custom format: compressed, and pg_restore can restore all of it or single tables.
compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" --format=custom --compress=6 >"$tmp" ||
  fail "pg_dump returned an error"
[ -s "$tmp" ] || fail "pg_dump wrote nothing"
# A dump that cannot list its own contents is not a backup.
compose exec -T db pg_restore --list <"$tmp" >/dev/null || fail "the dump is not a readable archive"

mv "$tmp" "$file"
chmod 600 "$file"
(cd "$(dirname "$file")" && sha256sum "$(basename "$file")" >"$(basename "$file").sha256")

# Sunday's dump is also kept as the weekly copy (a hard link: no extra space).
if [ "$(date -u +%u)" = 7 ]; then
  ln -f "$file" "$BACKUP_DIR/weekly/$(basename "$file")"
  ln -f "$file.sha256" "$BACKUP_DIR/weekly/$(basename "$file").sha256"
fi

prune() { # keep the newest $2 dumps in folder $1; names sort by time
  find "$1" -maxdepth 1 -name 'eos-*.dump' -printf '%f\n' | sort -r | tail -n +"$(($2 + 1))" |
    while read -r old; do rm -f "$1/$old" "$1/$old.sha256"; done
}
prune "$BACKUP_DIR/daily" "$KEEP_DAILY"
prune "$BACKUP_DIR/weekly" "$KEEP_WEEKLY"

size="$(du -h "$file" | cut -f1)"
echo "$stamp $size $(basename "$file")" >"$BACKUP_DIR/last-success"

if [ -n "$OFFSITE" ]; then
  # No --delete: a wiped local disk must never wipe the second copy. Prune the destination there.
  rsync -a "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly" "$BACKUP_DIR/last-success" "$OFFSITE" ||
    fail "local backup ok ($file), but the copy to $OFFSITE failed"
  log "ok: $(basename "$file") ($size), copied to $OFFSITE"
else
  log "ok: $(basename "$file") ($size). Local copy only: set EOS_BACKUP_OFFSITE for a second location"
fi
