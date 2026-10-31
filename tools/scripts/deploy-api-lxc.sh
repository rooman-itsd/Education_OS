#!/usr/bin/env bash
# Create the dedicated "education-os" API container on the Proxmox host, deploy the API and Postgres
# into it with Docker, install the auto-deploy timer, and point the public nginx vhost's /api/ at it.
# Safe to re-run: every step is skipped or refreshed when already done.
#
#   PVE_HOST=root@<proxmox-ip> CTID=<new container id> CT_IP=<free LAN ip> \
#   EOS_SUPER_ADMIN_EMAIL=<email> EOS_SUPER_ADMIN_PASSWORD=<password> \
#   tools/scripts/deploy-api-lxc.sh
#
# Optional: PROXY_CTID (nginx container, default 101), GATEWAY (default: the host's default gateway),
# ROOTFS_STORAGE (default local-lvm), BRIDGE (default vmbr0), CORES/MEMORY_MB/DISK_GB,
# PUBLIC_URL (default https://educationos.futureacad.ae), SSH_PUBKEY (default ~/.ssh/id_*.pub),
# REPO_REF (branch deployed by this run, default main; the timer resets the container to main later).
# The super admin email and password are only needed the first time (.env.api is created once and kept).
set -euo pipefail

PVE="${PVE_HOST:?set PVE_HOST, e.g. root@<proxmox-ip>}"
CTID="${CTID:?set CTID, the id of the education-os container}"
CT_IP="${CT_IP:?set CT_IP, a free static LAN ip for the container}"
PROXY_CTID="${PROXY_CTID:-101}"
BRIDGE="${BRIDGE:-vmbr0}"
ROOTFS_STORAGE="${ROOTFS_STORAGE:-local-lvm}"
CORES="${CORES:-2}"
MEMORY_MB="${MEMORY_MB:-4096}"
DISK_GB="${DISK_GB:-16}"
PUBLIC_URL="${PUBLIC_URL:-https://educationos.futureacad.ae}"
REPO_URL="${REPO_URL:-https://github.com/rooman-itsd/Education_OS.git}"
REPO_REF="${REPO_REF:-main}"   # branch to deploy first; the auto-deploy timer follows main afterwards
APP=/opt/education-os
COMPOSE="docker compose -f $APP/infra/docker/docker-compose.api.yml --env-file $APP/infra/docker/.env.api"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

pve() { ssh -o BatchMode=yes "$PVE" "$@"; }
in_ct() { pve "pct exec $CTID -- bash -c $(printf %q "$1")"; }

echo "==> checking $PVE"
pve 'pveversion >/dev/null && echo "   host ok: $(hostname)"'

# ---------- 1. container ----------
if pve "pct status $CTID" >/dev/null 2>&1; then
  echo "==> container $CTID exists: $(pve "pct config $CTID | grep ^hostname")"
else
  echo "==> creating container $CTID (education-os) at $CT_IP"
  key="${SSH_PUBKEY:-$(ls "$HOME"/.ssh/id_ed25519.pub "$HOME"/.ssh/id_rsa.pub 2>/dev/null | head -1)}"
  [ -n "$key" ] || { echo "no SSH public key found; set SSH_PUBKEY" >&2; exit 1; }
  scp -q "$key" "$PVE:/root/eos-deploy.pub"
  gw="${GATEWAY:-$(pve "ip -4 route show default | awk '{print \$3; exit}'")}"
  tmpl="$(pve "pveam list local | awk '/debian-12-standard/{print \$1}' | sort | tail -1")"
  if [ -z "$tmpl" ]; then
    echo "   downloading the Debian 12 template"
    pve 'pveam update >/dev/null && pveam download local "$(pveam available --section system | awk "/debian-12-standard/{print \$2}" | sort | tail -1)"'
    tmpl="$(pve "pveam list local | awk '/debian-12-standard/{print \$1}' | sort | tail -1")"
  fi
  pve "pct create $CTID $tmpl \
    --hostname education-os --ostype debian --unprivileged 1 --features nesting=1,keyctl=1 \
    --cores $CORES --memory $MEMORY_MB --swap 512 --rootfs $ROOTFS_STORAGE:$DISK_GB --onboot 1 \
    --net0 name=eth0,bridge=$BRIDGE,firewall=1,gw=$gw,ip=$CT_IP/24 \
    --ssh-public-keys /root/eos-deploy.pub"
fi
pve "pct status $CTID | grep -q running || pct start $CTID"
in_ct 'for i in $(seq 1 30); do ping -c1 -W1 deb.debian.org >/dev/null 2>&1 && exit 0; sleep 2; done; echo "no network in the container" >&2; exit 1'

# ---------- 2. docker ----------
if ! in_ct 'command -v docker >/dev/null'; then
  echo "==> installing Docker"
  in_ct 'export DEBIAN_FRONTEND=noninteractive; apt-get update -q && apt-get install -y -q ca-certificates curl git openssl && curl -fsSL https://get.docker.com | sh'
fi
in_ct 'docker run --rm hello-world 2>/dev/null | grep -q "Hello from Docker" || { echo "Docker does not work in the container (needs nesting=1,keyctl=1 and a restart)" >&2; exit 1; }'
echo "   docker ok"

# ---------- 3. repository and settings ----------
if in_ct "[ -d $APP/.git ]"; then
  in_ct "cd $APP && git fetch -q origin $REPO_REF && git reset -q --hard FETCH_HEAD"
else
  echo "==> cloning the repository ($REPO_REF)"
  in_ct "git clone -q --branch $REPO_REF $REPO_URL $APP"
fi
if ! in_ct "[ -f $APP/infra/docker/.env.api ]"; then
  echo "==> writing .env.api (secrets generated here, super admin from your environment)"
  : "${EOS_SUPER_ADMIN_EMAIL:?first run: set EOS_SUPER_ADMIN_EMAIL}"
  : "${EOS_SUPER_ADMIN_PASSWORD:?first run: set EOS_SUPER_ADMIN_PASSWORD}"
  cat > "$TMP/.env.api" <<EOF
EOS_DB_PASSWORD=$(openssl rand -hex 24)
EOS_APP_DB_PASSWORD=$(openssl rand -hex 24)
EOS_JWT_SECRET=$(openssl rand -hex 32)
EOS_SUPER_ADMIN_EMAIL=$EOS_SUPER_ADMIN_EMAIL
EOS_SUPER_ADMIN_PASSWORD=$EOS_SUPER_ADMIN_PASSWORD
EOS_DEV_MODE=false
EOS_CORS_ORIGINS=$PUBLIC_URL
BILLING_PAYMENT_ADAPTER=none
EOS_API_PORT=8000
EOF
  scp -q "$TMP/.env.api" "$PVE:/tmp/eos.env.api"
  pve "pct push $CTID /tmp/eos.env.api $APP/infra/docker/.env.api --perms 600 && rm -f /tmp/eos.env.api"
fi
# The reverse proxy (nginx container PROXY_CTID) is the only peer whose X-Forwarded-For the API believes
# (platform/api-gateway). Written when the key is missing, empty or still loopback (the old .env.api.example
# value, which behind the proxy puts every client in one bucket); a value naming another address is kept.
proxy_ip="$(pve "pct exec $PROXY_CTID -- hostname -I" 2>/dev/null | awk '{print $1}' || true)"
if [ -n "$proxy_ip" ]; then
  in_ct "f=$APP/infra/docker/.env.api; { grep -q '^EOS_TRUSTED_PROXIES=.' \$f && ! grep -qE '^EOS_TRUSTED_PROXIES=[[:space:]]*(127\.|::1|localhost)' \$f; } || { sed -i '/^EOS_TRUSTED_PROXIES=/d' \$f; printf '\nEOS_TRUSTED_PROXIES=%s\n' $proxy_ip >> \$f; }"
else
  echo "   could not read the address of container $PROXY_CTID: set EOS_TRUSTED_PROXIES in .env.api by hand" >&2
fi
# An .env.api from before the eos_app role: give the API its own database password, generated in the container.
in_ct "grep -q '^EOS_APP_DB_PASSWORD=.' $APP/infra/docker/.env.api || printf '\nEOS_APP_DB_PASSWORD=%s\n' \"\$(openssl rand -hex 24)\" >> $APP/infra/docker/.env.api"
# Keycloak (profile `oidc`) publishes its port on the container's LAN address only, where the proxy reaches it.
in_ct "grep -q '^KEYCLOAK_BIND=.' $APP/infra/docker/.env.api || { sed -i '/^KEYCLOAK_BIND=/d' $APP/infra/docker/.env.api; printf '\nKEYCLOAK_BIND=%s\n' $CT_IP >> $APP/infra/docker/.env.api; }"

# ---------- 4. build and start ----------
# `up` runs the migrate service first (eos_app role, migration chains; infra/docker/migrate.sh) and starts the
# API only when it succeeded.
echo "==> building, migrating and starting the API (first build takes a few minutes)"
in_ct "cd $APP && $COMPOSE up -d --build --quiet-pull 2>&1 | tail -3"
in_ct 'for i in $(seq 1 60); do curl -fs http://127.0.0.1:8000/api/v1/health && exit 0; sleep 3; done; echo "API did not become healthy" >&2; exit 1'
echo
in_ct "cd $APP && $COMPOSE ps --all --format 'table {{.Service}}\t{{.Status}}'"

# ---------- 5. auto-deploy timer inside the container ----------
echo "==> installing the API auto-deploy timer"
in_ct "bash $APP/infra/autodeploy/install-api.sh"

# ---------- 5b. nightly database backup ----------
# Idempotent; takes the first backup straight away (infra/backup-dr/README.md).
echo "==> installing the nightly database backup"
in_ct "bash $APP/infra/backup-dr/install.sh"

# ---------- 6. proxy ----------
echo "==> pointing /api/ on the nginx container $PROXY_CTID at $CT_IP"
scp -q "$ROOT/infra/docker/wire-api-proxy.sh" "$PVE:/tmp/wire-api-proxy.sh"
pve "pct push $PROXY_CTID /tmp/wire-api-proxy.sh /tmp/wire-api-proxy.sh && rm -f /tmp/wire-api-proxy.sh
  pct exec $PROXY_CTID -- bash /tmp/wire-api-proxy.sh $CT_IP $(printf %q "${PUBLIC_URL#https://}")
  pct exec $PROXY_CTID -- rm -f /tmp/wire-api-proxy.sh"

echo "==> verifying $PUBLIC_URL/api/v1/health"
body="$(curl -s --max-time 10 "$PUBLIC_URL/api/v1/health" || true)"
case "$body" in
  *'"status":"ok"'*) echo "   $body"; echo "done: the site now talks to the API in container $CTID ($CT_IP). Hard-refresh the browser (Ctrl+Shift+R)." ;;
  *) echo "   unexpected answer from the public URL (DNS cache or proxy); check with: curl -s $PUBLIC_URL/api/v1/health" ;;
esac
