# infra/autodeploy

Push to `main` → GitHub Actions builds and tests → the build lands on the `web-dist` branch →
the nginx container pulls it within a minute and reloads. Nothing on the server holds a
secret, and no GitHub runner runs on the server (the repo is public, so a self-hosted runner
would let strangers' pull requests execute code there).

| File | Where it runs |
|---|---|
| `../../.github/workflows/web.yml` | GitHub. Typecheck, test, build, publish `apps/frontend/dist` to `web-dist` |
| `eos-web-autodeploy.sh` | Container, every minute. Fetch `web-dist`; if changed, swap `/var/www/education-os` and reload nginx |
| `eos-web-autodeploy.{service,timer}` | Container, systemd units for the above |
| `install.sh` | Container, once. Installs the three files and the vhost, starts the timer. Re-run it after changing `eos-web-autodeploy.sh`; the script itself is not auto-updated |
| `eos-api-autodeploy.sh` | The education-os API container, every two minutes. Fetch `main`; if changed, rebuild the API image, run the platform migration chains, restart with Docker Compose |
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
