#!/usr/bin/env bash
# Restore a backup made by eos-db-backup. Run on the API host as root.
#
#   eos-db-restore --check <file.dump>   restore into a throwaway database, count the rows in every
#                                        table, drop it again. Live data is not touched. Do this monthly.
#   eos-db-restore <file.dump>           REPLACE the live database with the backup. Takes a safety backup
#                                        first, stops the API while restoring, starts it again.
set -euo pipefail

CONFIG="${EOS_BACKUP_CONFIG:-/etc/eos/db-backup.env}"
# shellcheck source=/dev/null
[ -f "$CONFIG" ] && . "$CONFIG"

APP_DIR="${EOS_APP_DIR:-/opt/education-os}"
COMPOSE_FILE="${EOS_COMPOSE_FILE:-$APP_DIR/infra/docker/docker-compose.api.yml}"
ENV_FILE="${EOS_ENV_FILE:-$APP_DIR/infra/docker/.env.api}"
DB_USER=eos
DB_NAME=eos
CHECK_DB=eos_restore_check

compose() { docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"; }
psql_in() { compose exec -T db psql -U "$DB_USER" -v ON_ERROR_STOP=1 -q "$@"; }
usage() {
  echo "usage: $(basename "$0") [--check] <backup.dump>" >&2
  exit 2
}

check=false
if [ "${1:-}" = "--check" ]; then
  check=true
  shift
fi
[ $# -eq 1 ] || usage
file="$1"
[ -s "$file" ] || { echo "error: $file not found or empty" >&2; exit 1; }

if [ -f "$file.sha256" ]; then
  (cd "$(dirname "$file")" && sha256sum --quiet -c "$(basename "$file").sha256") ||
    { echo "error: $file does not match its checksum; it is damaged" >&2; exit 1; }
fi

count_rows() { # one line per table: schema.table rows
  psql_in -d "$1" -At <<'SQL'
SELECT format('SELECT %L || '' '' || count(*) FROM %I.%I', table_schema || '.' || table_name, table_schema, table_name)
FROM information_schema.tables
WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name
\gexec
SQL
}

if $check; then
  psql_in -d postgres -c "DROP DATABASE IF EXISTS $CHECK_DB WITH (FORCE)" -c "CREATE DATABASE $CHECK_DB"
  trap 'psql_in -d postgres -c "DROP DATABASE IF EXISTS $CHECK_DB WITH (FORCE)" >/dev/null' EXIT
  compose exec -T db pg_restore -U "$DB_USER" -d "$CHECK_DB" --exit-on-error <"$file"
  echo "Restored $(basename "$file") into $CHECK_DB. Rows per table:"
  count_rows "$CHECK_DB" | sed 's/^/  /'
  tables="$(count_rows "$CHECK_DB" | grep -c . || true)"
  [ "$tables" -gt 0 ] || { echo "error: the backup restored no tables" >&2; exit 1; }
  echo "restore check ok: $tables tables. $CHECK_DB has been dropped; live data untouched."
  exit 0
fi

echo "This REPLACES the live '$DB_NAME' database with $(basename "$file")."
echo "Every change made since that backup will be lost. The API is stopped while it runs."
read -r -p "Type 'restore $DB_NAME' to continue: " answer
[ "$answer" = "restore $DB_NAME" ] || { echo "cancelled"; exit 1; }

# Restore from a private copy, so nothing that happens next (the safety backup, pruning) can change it.
work="$(mktemp -d)"
cp "$file" "$work/restore.dump"
file="$work/restore.dump"
trap 'rm -rf "$work"' EXIT

echo "Safety backup of the current database first:"
backup="$(command -v eos-db-backup || echo "$(dirname "$(readlink -f "$0")")/eos-db-backup.sh")"
"$backup" || { echo "error: the safety backup failed; nothing was changed" >&2; exit 1; }

# Stop the API only if it is running, and then start it again however the restore ends.
if [ -n "$(compose ps --status running -q api)" ]; then
  compose stop api
  trap 'echo "Starting the API again."; compose start api; rm -rf "$work"' EXIT
fi
psql_in -d postgres -c "DROP DATABASE $DB_NAME WITH (FORCE)" -c "CREATE DATABASE $DB_NAME OWNER $DB_USER"
compose exec -T db pg_restore -U "$DB_USER" -d "$DB_NAME" --exit-on-error <"$file"
echo "Restored. Rows per table:"
count_rows "$DB_NAME" | sed 's/^/  /'
logger -t eos-db-backup "restored $(basename "$file") into the live database" 2>/dev/null || true
