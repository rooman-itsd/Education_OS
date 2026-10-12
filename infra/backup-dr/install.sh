#!/usr/bin/env bash
# One-time install of the nightly database backup on the API host, after the API is deployed
# (infra/docker/README.md, "API"). Run as root from the checkout:
#   bash /opt/education-os/infra/backup-dr/install.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

[ "$(id -u)" = 0 ] || { echo "error: run as root" >&2; exit 1; }
command -v docker >/dev/null || { echo "error: docker not found; deploy the API first" >&2; exit 1; }
command -v rsync >/dev/null || { apt-get update -q && apt-get install -y -q rsync; }

install -m 755 "$HERE/eos-db-backup.sh" /usr/local/bin/eos-db-backup
install -m 755 "$HERE/eos-db-restore.sh" /usr/local/bin/eos-db-restore
install -m 644 "$HERE/eos-db-backup.service" /etc/systemd/system/eos-db-backup.service
install -m 644 "$HERE/eos-db-backup.timer" /etc/systemd/system/eos-db-backup.timer
install -d -m 700 /etc/eos
[ -f /etc/eos/db-backup.env ] || install -m 600 "$HERE/eos-db-backup.env.example" /etc/eos/db-backup.env

systemctl daemon-reload
systemctl enable --now eos-db-backup.timer
# First backup now, through systemd so it cannot collide with a timer run.
systemctl start eos-db-backup.service
echo "installed. last backup: $(cat /var/backups/eos/last-success 2>/dev/null || echo none)"
echo "next run: $(systemctl list-timers eos-db-backup.timer --no-legend | awk '{print $1, $2, $3}')"
echo "logs: journalctl -t eos-db-backup    settings: /etc/eos/db-backup.env"
