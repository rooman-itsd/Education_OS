# infra/docker

Dockerfiles and compose files for local and deployment.

| File | Purpose |
|---|---|
| `web.Dockerfile` | Builds `apps/frontend` with pnpm and serves the static output with nginx |
| `nginx.web.conf` | SPA fallback, asset caching, placeholder for the API proxy |
| `api.Dockerfile`, `docker-compose.api.yml`, `.env.api.example` | The API host and Postgres on a Docker host, plus Keycloak behind the `oidc` profile. See "API" and "Keycloak" below |
| `wire-api-proxy.sh` | Run inside the nginx container: points the public vhost's `/api/` at the API and `/auth/` at Keycloak |
| `nginx.static-vhost.conf` | Vhost for serving the build as static files from an existing nginx container on port 8080 |
| `docker-compose.yml` | Runs the `eos-web` image on the deployment host. `.env` beside it is written by the deploy script and git-ignored |

## Deployment target

A Proxmox VE host on the office LAN. The app does not run on the Proxmox host itself. It runs
in a dedicated Debian 12 LXC container (unprivileged, nesting and keyctl on, Docker inside), the same
shape as the other app containers on that host. Host names, IPs and container ids are kept
out of this public repo; ask the platform lead.

### One-time: create the app container

On the Proxmox host as root, with your SSH public key saved at `/root/eos-deploy.pub`.
Pick a free VMID and a free static IP on the LAN first.

```
pct create <vmid> local:vztmpl/debian-12-standard_12.12-1_amd64.tar.zst \
  --hostname education-os --ostype debian --unprivileged 1 --features nesting=1,keyctl=1 \
  --cores 2 --memory 4096 --swap 512 --rootfs local-lvm:16 --onboot 1 \
  --net0 name=eth0,bridge=vmbr0,firewall=1,gw=<gateway>,ip=<container-ip>/24 \
  --ssh-public-keys /root/eos-deploy.pub
pct start <vmid>
pct exec <vmid> -- bash -c 'apt-get update && apt-get install -y curl git ca-certificates && curl -fsSL https://get.docker.com | sh'
pct exec <vmid> -- docker run --rm hello-world
```

Docker in an unprivileged container needs both `nesting=1` and `keyctl=1`. Only `root@pam` can set
`keyctl` (other Proxmox users get "changing feature flags (except nesting) is only allowed for
root@pam"); restart the container after changing features. `hello-world` printing "Hello from
Docker!" proves it works.

### Option A: static files in the existing nginx reverse-proxy container (current)

No Docker on the target. Builds locally, pushes the `dist` folder into the container with
`pct push`, installs `nginx.static-vhost.conf` on port 8080, tests and reloads nginx.

```
PVE_HOST=root@<proxmox-ip> CTID=<nginx container id> tools/scripts/deploy-web-static.sh
```

Site: `http://<container-ip>:8080/?role=student`. Previous release is kept at
`/var/www/education-os.old` for a quick rollback (`mv` it back and `nginx -s reload`).

### Option B: Docker in a dedicated container

From your laptop, on the office LAN, with the commit you want deployed pushed to `main`:

```
DEPLOY_HOST=root@<container-ip> tools/scripts/deploy-web.sh
```

The container pulls the repo at your checked-out commit, builds the image, and restarts the
compose stack. The site is then at `http://<container-ip>/?role=student`.
`DEPLOY_MODE=local` builds on your machine instead and streams the image over SSH.

### Public hostname

`educationos.futureacad.ae`, an A record to the same public IP as the other futureacad.ae
sites. `nginx.public-vhost.conf` is the vhost for the reverse-proxy container; it proxies to
the static vhost on port 8080. After DNS resolves, inside the container:

```
curl -fsSL https://raw.githubusercontent.com/rooman-itsd/Education_OS/main/infra/docker/nginx.public-vhost.conf \
  -o /etc/nginx/sites-available/educationos.futureacad.ae
ln -sfn /etc/nginx/sites-available/educationos.futureacad.ae /etc/nginx/sites-enabled/
nginx -t && nginx -s reload
certbot --nginx -d educationos.futureacad.ae
```

### API

The API needs Docker and Postgres, so it does not run in the nginx container. It runs in its own
LXC container named `education-os` (the Debian 12 container from option B, with nesting on), reachable
from the proxy. One script creates that container, deploys the API and Postgres into it with Docker
Compose, installs the auto-deploy timer and points the public vhost's `/api/` at it. Run it from a
laptop on the office LAN, with root SSH access to the Proxmox host:

```
PVE_HOST=root@<proxmox-ip> CTID=<free container id> CT_IP=<free LAN ip> \
EOS_SUPER_ADMIN_EMAIL=<a real address with a dot after @> EOS_SUPER_ADMIN_PASSWORD='<password>' \
tools/scripts/deploy-api-lxc.sh
```

It is safe to re-run: an existing container, Docker install, clone or `.env.api` is kept and refreshed.
The super admin values are read only the first time, when `.env.api` is created (database password and
JWT secret are generated then). The last line of the script fetches
`https://educationos.futureacad.ae/api/v1/health` through the public proxy; `{"status":"ok","database":"postgres",...}`
means the site has left preview mode (hard refresh with Ctrl+Shift+R once). From then on every push to
`main` reaches the container within two minutes (`../autodeploy/README.md`, section "API"), and the
database is backed up nightly with the first backup taken during the run (`../backup-dr/README.md`).

To move the API to another container later, run the same script with the new `CTID` and `CT_IP`; it
repoints the proxy. Stop the old one with `pct stop <old id>` once the health check answers from the new one.

By hand, the same steps are: on the Docker host as root,

```
apt-get update && apt-get install -y ca-certificates curl git openssl nano
git clone https://github.com/rooman-itsd/Education_OS.git /opt/education-os && cd /opt/education-os
cd infra/docker && cp .env.api.example .env.api && chmod 600 .env.api
sed -i "s|^EOS_DB_PASSWORD=.*|EOS_DB_PASSWORD=$(openssl rand -hex 24)|" .env.api
sed -i "s|^EOS_APP_DB_PASSWORD=.*|EOS_APP_DB_PASSWORD=$(openssl rand -hex 24)|" .env.api
sed -i "s|^EOS_JWT_SECRET=.*|EOS_JWT_SECRET=$(openssl rand -hex 32)|" .env.api
nano .env.api   # set EOS_SUPER_ADMIN_EMAIL (a real address with a dot after @) and EOS_SUPER_ADMIN_PASSWORD,
                # and EOS_TRUSTED_PROXIES to the nginx container's LAN address (rate limits, below)
cd /opt/education-os
docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api up -d --build
docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api ps
curl -s http://127.0.0.1:8000/api/v1/health
bash infra/autodeploy/install-api.sh
bash infra/backup-dr/install.sh
```

then in the nginx container, with the API container's LAN IP in place of `<api-host-ip>`:

```
V=$(grep -rl '<api-host>' /etc/nginx/sites-enabled/ /etc/nginx/sites-available/ | head -1); echo "$V"
sed -i 's|http://<api-host>:8000/api/|http://<api-host-ip>:8000/api/|' "$V"
nginx -t && nginx -s reload
curl -s https://educationos.futureacad.ae/api/v1/health
```

If the first line prints nothing, the live vhost has no `/api/` location yet: copy the
`location /api/` block from `nginx.public-vhost.conf` into the server block for
`educationos.futureacad.ae` and run the rest.

**Two database logins.** Postgres is owned by `eos` (`EOS_DB_PASSWORD`), which only the `migrate`
service uses. The API connects as `eos_app` (`EOS_APP_DB_PASSWORD`): it can read and write rows but not
change the schema, and it is neither a superuser nor `BYPASSRLS`, so every `tenant_isolation` policy
applies to it (a superuser would skip them all). `up` runs `migrate` first and starts the API only when it
succeeded; it does, in order (`migrate.sh`):

1. `db-roles.py`: creates or updates `eos_app`, with row access on every table and on tables `eos` creates later
2. `stamp-chains.py`: only for a database whose tables the API created before migrations existed
3. `alembic upgrade head` for every chain `apps/backend/config/modules.enabled.yaml` enables
4. `init_db()` for `outbox_event`, the one table without a chain yet

The auto-deploy runs the same service. By hand:

```
docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api run --rm migrate
```

**Settings applied only once.** Editing `.env.api` and running `up -d` changes most settings
(`EOS_DEV_MODE`, `EOS_JWT_SECRET`, which signs everyone out). Two do not:

- `EOS_DB_PASSWORD` is read by Postgres only when it first creates its volume. Changing it later
  locks `migrate` out; change the password inside Postgres (`ALTER USER eos PASSWORD ...`) first.
  `EOS_APP_DB_PASSWORD` is different: `migrate` sets it on `eos_app` at every run, so a new value
  applies on the next `up -d`.
- The super admin is created at the first start and never updated: a new `EOS_SUPER_ADMIN_PASSWORD`
  is ignored, and a new `EOS_SUPER_ADMIN_EMAIL` adds a second super admin beside the first.

**Rate limits and the emergency switch.** The API rate-limits requests and sets security headers
(`platform/api-gateway`, whose README explains the limits). Compose passes every setting from `.env.api`
(`EOS_RATE_LIMIT_*`, `EOS_SECURITY_HEADERS`, `EOS_HSTS_MAX_AGE`, `EOS_TRUSTED_PROXIES`, `EOS_REDIS_URL`), with
the defaults in `.env.api.example`. Two matter on the server:

- `EOS_TRUSTED_PROXIES` must be the nginx container's address as the API container sees it, so the API
  believes the proxy's `X-Forwarded-For`. Left at loopback, every visitor counts as the proxy and shares
  one bucket. `tools/scripts/deploy-api-lxc.sh` writes it (the `PROXY_CTID` container's address).
- If the limits refuse legitimate traffic, switch them off without a code change: set
  `EOS_RATE_LIMIT_ENABLED=false` in `.env.api`, then
  `docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api up -d`
  (recreates the API container, no rebuild). Raise the limit that was hit (the log says `rate limited
  scope=...`) and set it back to `true` the same way.

Before any real organisation has registered, the clean way to change either is to start over:
`docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api down -v`
(this **deletes the database**), fix `.env.api`, then `up -d --build` again. Never do that once real
organisations exist.

Postgres tables get row-level-security policies automatically at startup (`eos_core.rls`). Nightly
backups and restores: [infra/backup-dr](../backup-dr/README.md).

#### Check the live site after the proxy change

```
curl -s https://<public-hostname>/api/v1/health
```

It must print the JSON above. An HTML page (`<!doctype html>...`) means `/api/` still goes to the web
vhost, which answers every path with `index.html`: the `proxy_pass` line is missing or nginx was not
reloaded. Then open the site in a browser: the "Preview mode" banner is gone and the sign-in page shows.

#### Dev mode on or off

Until `platform/notification` sends email, the verification token is only written to the API log, so
with `EOS_DEV_MODE=false` nobody can finish registering. `true` returns the token to the sign-up page
instead. Every new organisation still waits for a super admin's approval, so nothing goes live unseen;
turn it off once email works. The platform lead decides which applies on a shared host.

```
cd /opt/education-os
sed -i 's/^EOS_DEV_MODE=.*/EOS_DEV_MODE=true/' infra/docker/.env.api    # or =false
docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api up -d
curl -s http://127.0.0.1:8000/api/v1/health                             # shows the new dev_mode
```

`up -d` recreates only the `api` container; the database keeps running and keeps its data.

#### Allow port 8000 only from the proxy

Docker publishes the API on every interface, so anyone on the LAN can call it directly and skip the
proxy. Restrict it with the Proxmox firewall on the API container. It filters on the Proxmox host,
outside the container, so Docker's own iptables rules cannot open a way around it (a firewall inside
the container could be bypassed that way). Proxmox applies container rules only while the firewall is
enabled at Datacenter level; turning that on is the platform lead's call, since it also filters the host.

In the order below, so SSH is allowed before anything is blocked. In the web UI, on the API container:

1. **Firewall → Add**: direction `in`, action `ACCEPT`, protocol `tcp`, dest. port `22`,
   source `<office-subnet>` (or the admins' addresses). Enable it.
2. **Firewall → Add**: direction `in`, action `ACCEPT`, protocol `tcp`, dest. port `8000`,
   source `<nginx-container-ip>`. Enable it.
3. **Network → net0 → Edit**: tick **Firewall**.
4. **Firewall → Options**: `Input Policy` `DROP`, then `Firewall` `Yes`.

Check: the live site's `/api/v1/health` still answers, SSH still works, and from a laptop
`curl -m 5 http://<container-ip>:8000/api/v1/health` now times out. If SSH is lost, set
`Firewall` back to `No` under Firewall → Options in the Proxmox UI.

### Keycloak (ADR-0006)

The OpenID Connect provider runs on the same Docker host as two more services in `docker-compose.api.yml`,
`keycloak` (`quay.io/keycloak/keycloak`, the official image; `KEYCLOAK_VERSION` pins it, default `26.0`)
and `kc-db` (its own Postgres 16, volume `eos-kcdata`). Both carry the Compose profile `oidc`, so a host
whose `.env.api` predates them keeps running the API alone; nothing starts until the settings are filled in.
With the profile on and a setting still empty, `keycloak` exits at once and `docker compose ... logs keycloak`
says which.
The public proxy serves it under `https://educationos.futureacad.ae/auth/` (`KC_HTTP_RELATIVE_PATH=/auth`);
realm issuers are `<that URL>/realms/<organisation slug>`.

Switch it on, on the API host:

```
cd /opt/education-os/infra/docker
sed -i "s|^KEYCLOAK_DB_PASSWORD=.*|KEYCLOAK_DB_PASSWORD=$(openssl rand -hex 24)|" .env.api
nano .env.api   # COMPOSE_PROFILES=oidc, KEYCLOAK_ADMIN_PASSWORD, KC_HOSTNAME=https://educationos.futureacad.ae/auth,
                # EOS_OIDC_ISSUER_BASE=https://educationos.futureacad.ae/auth (the same value), EOS_OIDC_REALMS=<pilot slug>
cd /opt/education-os
docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api up -d
docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api ps   # keycloak healthy after ~1 min
curl -s http://$(grep ^KEYCLOAK_BIND= infra/docker/.env.api | cut -d= -f2):8080/auth/realms/master | head -c 120
```

Keycloak's port is published on `KEYCLOAK_BIND` only (the container's LAN address, which
`deploy-api-lxc.sh` writes into `.env.api`; unset, `127.0.0.1`), never on all interfaces. The container is
capped at 1 GB (`mem_limit`) with a 512 MB Java heap (`JAVA_OPTS_KC_HEAP`), so it cannot starve the API and
the databases beside it. On the host itself, check it at `http://$KEYCLOAK_BIND:8080/auth/realms/master`.

Then in the nginx container re-run `wire-api-proxy.sh <api-host-ip>` (it now adds the `/auth/` location
beside `/api/`; `tools/scripts/deploy-api-lxc.sh` does this), and check
`curl -s https://educationos.futureacad.ae/auth/realms/pilot | head -c 120` for a realm you created. The
proxy answers `/auth/admin/` (admin console and Admin API) and `/auth/realms/master/` (where administrators
sign in) only from LAN addresses (127.0.0.1, 10/8, 172.16/12, 192.168/16) and 404 for everyone else, so
from outside the office the master realm and console are not reachable. The admin console is at
`/auth/admin/` on the office network with `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD`; those two are read
only at the first start (change the password in the console afterwards). `KEYCLOAK_DB_PASSWORD`, like
`EOS_DB_PASSWORD`, is read by Postgres only when it creates its volume.

Create an organisation's realm with `tools/scripts/keycloak-realm.sh <slug>` from the office network, or
on the API host with `KEYCLOAK_URL=http://<KEYCLOAK_BIND>:8080/auth` (platform/identity's README explains
what it sets up), add the slug to `EOS_OIDC_REALMS` and `up -d` again. The nightly backup dumps
the Keycloak database beside the API's when the service runs (`../backup-dr/README.md`). Allow port 8080
only from the proxy, as for port 8000 above (a second rule, dest. port `8080`, source `<nginx-container-ip>`);
it is only ever reached through `/auth/`.

### Local check

```
docker build -f infra/docker/web.Dockerfile -t eos-web .
docker run --rm -p 8080:80 eos-web
```
