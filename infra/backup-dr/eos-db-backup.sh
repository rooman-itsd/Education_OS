#!/usr/bin/env bash
# Nightly Postgres backup on the API host (infra/docker/docker-compose.api.yml). Run by
# eos-db-backup.timer; settings in /etc/eos/db-backup.env (see eos-db-backup.env.example).
#
# Writes a compressed pg_dump archive, proves it is readable, keeps KEEP_DAILY nightly and KEEP_WEEKLY
# Sunday copies, optionally mirrors them to a second location (same retention there), and records the last
# success.
# When Keycloak runs (ADR-0006: the `oidc` compose profile, its own Postgres in service kc-db), its
# database is dumped the same way beside the API's, as keycloak-<time>.dump.
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
# Most dumps one run may delete at the second location: a normal night rotates out one daily and one weekly,
# for the API and for Keycloak. More than that means the local folder lost dumps, and is refused.
OFFSITE_MAX_PRUNE="${EOS_BACKUP_OFFSITE_MAX_PRUNE:-4}"
LOCK="${EOS_BACKUP_LOCK:-/run/lock/eos-db-backup.lock}"
DB_USER=eos
DB_NAME=eos

log() {
  echo "$*"
  # Under systemd the line above already reaches the journal; send it once more only for a manual run.
  if [ -z "${INVOCATION_ID:-}" ] && command -v logger >/dev/null; then logger -t eos-db-backup "$*"; fi
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

# Keycloak's database, whenever the `oidc` profile is on (COMPOSE_PROFILES in .env.api) or kc-db runs. With
# the profile on, kc-db not running is a failure, not a skip: the API's dump is still kept, pruned and copied,
# then the run ends "FAILED" and last-success is not updated, so the staleness check notices too.
kc_file=""
kc_error=""
kc_running="$(compose ps -q --status running kc-db 2>/dev/null || true)"
if [ -n "$kc_running" ] || compose config --services 2>/dev/null | grep -qx kc-db; then
  if [ -z "$kc_running" ]; then
    kc_error="the oidc profile is on but kc-db is not running, so the keycloak database was not dumped"
  else
    kc_file="$BACKUP_DIR/daily/keycloak-$stamp.dump"
    kc_tmp="$kc_file.partial"
    trap 'rm -f "$tmp" "$kc_tmp"' EXIT
    if ! compose exec -T kc-db pg_dump -U keycloak -d keycloak --format=custom --compress=6 >"$kc_tmp"; then
      kc_error="pg_dump of the keycloak database returned an error"
    elif [ ! -s "$kc_tmp" ]; then
      kc_error="pg_dump of the keycloak database wrote nothing"
    elif ! compose exec -T kc-db pg_restore --list <"$kc_tmp" >/dev/null; then
      kc_error="the keycloak dump is not a readable archive"
    else
      mv "$kc_tmp" "$kc_file"
      chmod 600 "$kc_file"
      (cd "$(dirname "$kc_file")" && sha256sum "$(basename "$kc_file")" >"$(basename "$kc_file").sha256")
    fi
    if [ -n "$kc_error" ]; then
      rm -f "$kc_tmp"
      kc_file=""
    fi
  fi
fi

# Sunday's dump is also kept as the weekly copy (a hard link: no extra space).
if [ "$(date -u +%u)" = 7 ]; then
  for f in "$file" $kc_file; do
    ln -f "$f" "$BACKUP_DIR/weekly/$(basename "$f")"
    ln -f "$f.sha256" "$BACKUP_DIR/weekly/$(basename "$f").sha256"
  done
fi

prune() { # keep the newest $3 dumps named $2-* in folder $1; names sort by time
  find "$1" -maxdepth 1 -name "$2-*.dump" -printf '%f\n' | sort -r | tail -n +"$(($3 + 1))" |
    while read -r old; do rm -f "$1/$old" "$1/$old.sha256"; done
}
for name in eos keycloak; do
  prune "$BACKUP_DIR/daily" "$name" "$KEEP_DAILY"
  prune "$BACKUP_DIR/weekly" "$name" "$KEEP_WEEKLY"
done

size="$(du -h "$file" | cut -f1)"
[ -n "$kc_error" ] || echo "$stamp $size $(basename "$file")" >"$BACKUP_DIR/last-success"

offsite_error=""
if [ -n "$OFFSITE" ]; then
  # The second location keeps what the local folders keep, so a dump pruned here (and the data of an
  # organisation purged since, DPDP) is gone there too. Deleting is limited twice: only our own dump files
  # (P protects everything else at the destination), and only as many as a normal night rotates out, so a
  # wiped or emptied local folder can never wipe the second copy with it.
  sync=(rsync -a --filter='R eos-*.dump' --filter='R eos-*.dump.sha256' --filter='R keycloak-*.dump'
    --filter='R keycloak-*.dump.sha256' --filter='P *')
  plan="$("${sync[@]}" --delete --dry-run --itemize-changes "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly" "$OFFSITE")" ||
    fail "local backup ok ($file), but $OFFSITE could not be read${kc_error:+; also: $kc_error}"
  doomed="$(printf '%s\n' "$plan" | grep -c '^\*deleting .*\.dump$' || true)"
  delete=(--delete)
  if [ "$doomed" -gt "$OFFSITE_MAX_PRUNE" ] && [ "${EOS_BACKUP_OFFSITE_FORCE_PRUNE:-}" != 1 ]; then
    delete=()
    offsite_error="$OFFSITE holds $doomed dump(s) the local folders no longer have (more than $OFFSITE_MAX_PRUNE): kept, nothing deleted there. If the retention was lowered on purpose, run once with EOS_BACKUP_OFFSITE_FORCE_PRUNE=1; otherwise check $BACKUP_DIR"
  fi
  "${sync[@]}" "${delete[@]}" "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly" "$BACKUP_DIR/last-success" "$OFFSITE" ||
    fail "local backup ok ($file), but the copy to $OFFSITE failed${kc_error:+; also: $kc_error}"
fi
[ -z "$offsite_error" ] || fail "$offsite_error${kc_error:+; also: $kc_error}"
[ -z "$kc_error" ] || fail "$kc_error (the API's $(basename "$file") is kept${OFFSITE:+ and copied to $OFFSITE})"
if [ -n "$OFFSITE" ]; then
  log "ok: $(basename "$file") ($size)${kc_file:+ + $(basename "$kc_file")}, copied to $OFFSITE"
else
  log "ok: $(basename "$file") ($size)${kc_file:+ + $(basename "$kc_file")}. Local copy only: set EOS_BACKUP_OFFSITE for a second location"
fi
