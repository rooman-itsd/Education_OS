# infra/autodeploy

Push to `main` → GitHub Actions builds and tests → the build lands on the `web-dist` branch →
the nginx container pulls it within a minute and reloads. Nothing on the server holds a
secret, and no GitHub runner runs on the server (the repo is public, so a self-hosted runner
would let strangers' pull requests execute code there).

| File | Where it runs |
|---|---|
| `../../.github/workflows/web.yml` | GitHub. Typecheck, test, build; publish `apps/frontend/dist` to `web-dist` on `main`, to `web-release` on the highest `vX.Y.Z` tag |
| `eos-web-autodeploy.sh` | Container, every minute. Fetch `web-dist`; if changed, swap `/var/www/education-os` and reload nginx. With a site name (`eos-web-autodeploy production`) it reads that site's branch and web root from `/etc/eos/web-autodeploy-<site>.env` |
| `eos-web-autodeploy.{service,timer}` | Container, systemd units for the staging site |
| `eos-web-autodeploy@.{service,timer}` | Container, systemd units for another site, e.g. `eos-web-autodeploy@production.timer` |
| `install.sh` | Container, once. Installs the script, the units and the vhost, starts the timer. With `EOS_WEB_INSTANCE` it installs another site instead (see "Environments"). Re-run it after changing `eos-web-autodeploy.sh`; the script itself is not auto-updated |
| `eos-api-autodeploy.sh` | The education-os API container, every two minutes. Fetch what it follows (`main`, or the highest release tag); if changed, rebuild the API image, run the platform migration chains, restart with Docker Compose |
| `eos-api-autodeploy.{service,timer}` | API container, systemd units for the above |
| `install-api.sh` | API container, once. Installs the three API files and starts the timer. `tools/scripts/deploy-api-lxc.sh` runs it for you |

Install once, as root inside the nginx container:

```
bash <(curl -fsSL https://raw.githubusercontent.com/rooman-itsd/Education_OS/main/infra/autodeploy/install.sh)
```

Check: `journalctl -t eos-web-autodeploy`, `systemctl list-timers eos-web*`, and `/VERSION` on the site
shows the short commit sha that is live. Rollback: revert the commit on `main`; the next build
deploys itself. The previous release also stays at `/var/www/education-os.old`.

`tools/scripts/deploy-web-static.sh` remains for a manual push from a laptop.

## API

The API and its Postgres run in the dedicated `education-os` LXC container, created and deployed by
`tools/scripts/deploy-api-lxc.sh` from a laptop on the office LAN (see `../docker/README.md`,
section "API"). The container does not wait for a GitHub build: it pulls `main` itself every two
minutes, rebuilds the image, runs the Alembic chains and restarts. Nothing on the server holds a
GitHub credential; the repo is public.

Check: `journalctl -t eos-api-autodeploy` inside the container, `systemctl list-timers eos-api*`,
and `curl -s https://educationos.futureacad.ae/api/v1/health`. Rollback: revert the commit on `main`;
the next check deploys it. A failed migration is logged and the API is still restarted on the new
code, so fix forward quickly or revert.

## Environments

| | Staging | Production |
|---|---|---|
| Gets new code | every merge to `main` | only a release: the highest `vX.Y.Z` tag |
| Web build branch | `web-dist` | `web-release` |
| Web timer | `eos-web-autodeploy.timer` | `eos-web-autodeploy@production.timer` |
| API follows | `main` (the default) | `EOS_DEPLOY_REF=latest-tag` |
| Database and backups | its own | its own |

Every default above is staging, so a host is production only once it is set up as one. Releases count
only plain `vX.Y.Z` tags, compared as versions (`v0.10.0` is above `v0.9.0`). A pre-release such as
`v1.0.0-rc1`, or a tag below the highest, is built and tested but never deployed, and the web and API
always follow the same tag.

### Releasing

Releases come only from `main`: a tag whose commit is not on `main` is refused by the publish job (it
fails, `web-release` stays as it was) and by the production API (it logs the refusal and stays on the
previous release). Only the lead creates release tags; a repository ruleset on `v*` enforces it.

From an up-to-date `main` that staging has run without problems:

```
git switch main && git pull
git tag v0.1.0
git push origin v0.1.0
```

GitHub builds and tests that commit and publishes it to `web-release`; production's web timer serves it
within a minute and its API timer deploys the same tag within two. `/VERSION` on the production site then
reads `v0.1.0 (<sha>)`.

### Rolling back production

Tag the last good commit with the next patch number, so it becomes the highest release:

```
git tag v0.1.1 <last-good-commit>
git push origin v0.1.1
```

Never delete or move a published tag: hosts that already fetched it would keep it. The one exception is
a tag that was refused (not on `main`): nothing deployed it, so delete it
(`git push origin :refs/tags/<tag>`) and tag the right commit on `main` instead.

### Setting up production (once, with Proxmox access)

1. An API container with its own database: `tools/scripts/deploy-api-lxc.sh` with a new `CTID` and
   `CT_IP` (`../docker/README.md`, section "API"). Then, inside it, make it follow releases:
   `mkdir -p /etc/eos && echo EOS_DEPLOY_REF=latest-tag > /etc/eos/api-autodeploy.env` (and `FORCE=1 eos-api-autodeploy`
   to deploy the current release at once).
2. The web site, in the nginx container:
   `EOS_WEB_INSTANCE=production EOS_WEB_BRANCH=web-release EOS_WEB_ROOT=/var/www/education-os-production bash <(curl -fsSL https://raw.githubusercontent.com/rooman-itsd/Education_OS/main/infra/autodeploy/install.sh)`
3. A vhost for the production hostname whose `root` is that web root and whose `/api/` proxies to the
   production API container, modelled on `../docker/nginx.static-vhost.conf` and
   `../docker/nginx.public-vhost.conf`, then `certbot --nginx -d <production-hostname>`.

Check: `journalctl -t eos-web-autodeploy@production` in the nginx container and
`journalctl -t eos-api-autodeploy` in the production API container.

### The current host becomes production

The plan for Education OS: `educationos.futureacad.ae` stays the public, production name and staging moves
to `staging.educationos.futureacad.ae`. Until the first `vX.Y.Z` tag exists nothing changes: the current
site keeps following `main`.

1. **Staging host, before the first release.** An A record for `staging.educationos.futureacad.ae`, then
   in the nginx container a vhost for it that serves `/var/www/education-os` (the staging web root,
   `web-dist`) with `/api/` proxied to the staging API container (the `location /api/` block from
   `../docker/nginx.public-vhost.conf`), and `certbot --nginx -d staging.educationos.futureacad.ae`. The
   staging API container keeps following `main`. Edit this vhost by hand: once two vhosts carry an
   `/api/` location, `../docker/wire-api-proxy.sh` rewrites the first one it finds, whichever name it has.
2. **Production API.** `tools/scripts/deploy-api-lxc.sh` with a new `CTID` and `CT_IP`, then
   `EOS_DEPLOY_REF=latest-tag` inside it as in step 1 of "Setting up production" above. Production runs
   with `EOS_DEV_MODE=false`, always; staging may run with `true` until email is delivered.
3. **Production web.** The `production` web instance as in step 2 above (`web-release` into
   `/var/www/education-os-production`).
4. **The switch, once the first release is published.** In the existing `educationos.futureacad.ae`
   vhost, point `root` at `/var/www/education-os-production` and `/api/` at the production API container,
   then `nginx -t && nginx -s reload`. Check `https://educationos.futureacad.ae/VERSION` reads the release
   tag, and `https://staging.educationos.futureacad.ae/VERSION` a short commit sha.
5. **Smoke check both.** `E2E_BASE_URL=https://educationos.futureacad.ae pnpm --filter e2e e2e`, and the
   same with the staging URL (`../../tests/e2e/README.md`).
