#!/usr/bin/env bash
# One-time install of the API auto-deploy timer inside the education-os container. Run as root there,
# after the repository is cloned at /opt/education-os and the API runs (tools/scripts/deploy-api-lxc.sh
# does all of this). Re-run after changing eos-api-autodeploy.sh; the script itself is not auto-updated.
set -euo pipefail
APP="${EOS_APP_DIR:-/opt/education-os}"

if ! command -v docker >/dev/null || [ ! -d "$APP/infra/autodeploy" ]; then
  echo "error: run this inside the education-os API container with the repo at $APP" >&2
  exit 1
fi

install -m 755 "$APP/infra/autodeploy/eos-api-autodeploy.sh" /usr/local/bin/eos-api-autodeploy
install -m 644 "$APP/infra/autodeploy/eos-api-autodeploy.service" /etc/systemd/system/eos-api-autodeploy.service
install -m 644 "$APP/infra/autodeploy/eos-api-autodeploy.timer" /etc/systemd/system/eos-api-autodeploy.timer
systemctl daemon-reload
systemctl enable --now eos-api-autodeploy.timer
echo "installed. timer: $(systemctl is-active eos-api-autodeploy.timer); logs: journalctl -t eos-api-autodeploy"
