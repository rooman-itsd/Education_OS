#!/usr/bin/env bash
# One-time install of the auto-deploy timer inside the nginx container. Run as root there:
#   bash <(curl -fsSL https://raw.githubusercontent.com/rooman-itsd/Education_OS/main/infra/autodeploy/install.sh)
#
# That installs the staging site (`web-dist` into /var/www/education-os) with its vhost. A second site,
# such as production, is an instance with its own branch and web root; its vhost is set up by hand:
#   EOS_WEB_INSTANCE=production EOS_WEB_BRANCH=web-release EOS_WEB_ROOT=/var/www/education-os-production \
#     bash <(curl -fsSL https://raw.githubusercontent.com/rooman-itsd/Education_OS/main/infra/autodeploy/install.sh)
set -euo pipefail
RAW="https://raw.githubusercontent.com/rooman-itsd/Education_OS/main"
INSTANCE="${EOS_WEB_INSTANCE:-}"

# Guard: this belongs inside the nginx container, not on the Proxmox host.
if ! command -v nginx >/dev/null || [ ! -d /etc/nginx/sites-available ]; then
  echo "error: nginx not found. Run this inside the nginx reverse-proxy container, e.g." >&2
  echo "  pct exec <ctid> -- bash -c \"bash <(curl -fsSL $RAW/infra/autodeploy/install.sh)\"" >&2
  exit 1
fi

command -v git >/dev/null || { apt-get update -q && apt-get install -y -q git; }

curl -fsSL "$RAW/infra/autodeploy/eos-web-autodeploy.sh" -o /usr/local/bin/eos-web-autodeploy
chmod +x /usr/local/bin/eos-web-autodeploy

if [ -n "$INSTANCE" ]; then
  : "${EOS_WEB_BRANCH:?set EOS_WEB_BRANCH for instance $INSTANCE, e.g. web-release}"
  : "${EOS_WEB_ROOT:?set EOS_WEB_ROOT for instance $INSTANCE, e.g. /var/www/education-os-$INSTANCE}"
  curl -fsSL "$RAW/infra/autodeploy/eos-web-autodeploy@.service" -o /etc/systemd/system/eos-web-autodeploy@.service
  curl -fsSL "$RAW/infra/autodeploy/eos-web-autodeploy@.timer" -o /etc/systemd/system/eos-web-autodeploy@.timer
  install -d -m 755 /etc/eos
  printf 'EOS_WEB_BRANCH=%s\nEOS_WEB_ROOT=%s\n' "$EOS_WEB_BRANCH" "$EOS_WEB_ROOT" >"/etc/eos/web-autodeploy-$INSTANCE.env"
  systemctl daemon-reload
  systemctl enable --now "eos-web-autodeploy@$INSTANCE.timer"
  systemctl start "eos-web-autodeploy@$INSTANCE.service"
  echo "installed $INSTANCE: $EOS_WEB_BRANCH -> $EOS_WEB_ROOT, serving $(cat "$EOS_WEB_ROOT/VERSION")"
  echo "point its vhost's root at $EOS_WEB_ROOT; logs: journalctl -t eos-web-autodeploy@$INSTANCE"
  exit 0
fi

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
