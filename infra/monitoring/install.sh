#!/usr/bin/env bash
# One-time install of the host check on the API host, after the API is deployed. Run as root from the checkout:
#   bash /opt/education-os/infra/monitoring/install.sh
# Re-run after changing eos-monitor.sh; the copy in /usr/local/bin is not auto-updated. Settings are kept.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

[ "$(id -u)" = 0 ] || { echo "error: run as root" >&2; exit 1; }
command -v docker >/dev/null || { echo "error: docker not found; deploy the API first" >&2; exit 1; }
command -v curl >/dev/null || { apt-get update -q && apt-get install -y -q curl; }

install -m 755 "$HERE/eos-monitor.sh" /usr/local/bin/eos-monitor
install -m 644 "$HERE/eos-monitor.service" /etc/systemd/system/eos-monitor.service
install -m 644 "$HERE/eos-monitor.timer" /etc/systemd/system/eos-monitor.timer
install -d -m 700 /etc/eos
[ -f /etc/eos/monitor.env ] || install -m 600 "$HERE/eos-monitor.env.example" /etc/eos/monitor.env

systemctl daemon-reload
systemctl enable --now eos-monitor.timer
# A first check now, through systemd; it exits non-zero when a check fails, which is reported below.
systemctl start eos-monitor.service || true
journalctl -t eos-monitor -n 10 --no-pager -o cat
echo "installed. logs: journalctl -t eos-monitor    settings: /etc/eos/monitor.env"
