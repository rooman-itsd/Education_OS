#!/usr/bin/env bash
# One-time install of the auto-deploy timer inside the nginx container. Run as root there:
#   bash <(curl -fsSL https://raw.githubusercontent.com/rooman-itsd/Education_OS/main/infra/autodeploy/install.sh)
set -euo pipefail
RAW="https://raw.githubusercontent.com/rooman-itsd/Education_OS/main"

# Guard: this belongs inside the nginx container, not on the Proxmox host.
if ! command -v nginx >/dev/null || [ ! -d /etc/nginx/sites-available ]; then
  echo "error: nginx not found. Run this inside the nginx reverse-proxy container, e.g." >&2
  echo "  pct exec <ctid> -- bash -c \"bash <(curl -fsSL $RAW/infra/autodeploy/install.sh)\"" >&2
  exit 1
fi

command -v git >/dev/null || { apt-get update -q && apt-get install -y -q git; }

curl -fsSL "$RAW/infra/autodeploy/eos-web-autodeploy.sh" -o /usr/local/bin/eos-web-autodeploy
chmod +x /usr/local/bin/eos-web-autodeploy
curl -fsSL "$RAW/infra/autodeploy/eos-web-autodeploy.service" -o /etc/systemd/system/eos-web-autodeploy.service
curl -fsSL "$RAW/infra/autodeploy/eos-web-autodeploy.timer" -o /etc/systemd/system/eos-web-autodeploy.timer

if [ ! -f /etc/nginx/sites-available/education-os.conf ]; then
  curl -fsSL "$RAW/infra/docker/nginx.static-vhost.conf" -o /etc/nginx/sites-available/education-os.conf
  ln -sfn /etc/nginx/sites-available/education-os.conf /etc/nginx/sites-enabled/education-os.conf
fi

systemctl daemon-reload
systemctl enable --now eos-web-autodeploy.timer
# Run once now through systemd so it cannot collide with a timer-triggered run.
systemctl start eos-web-autodeploy.service
echo "installed. version now serving: $(cat /var/www/education-os/VERSION)"
echo "timer: $(systemctl is-active eos-web-autodeploy.timer); logs: journalctl -t eos-web-autodeploy"
