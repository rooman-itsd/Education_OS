#!/usr/bin/env bash
# Runs every two minutes in the education-os API container (systemd timer). When the code it follows has
# moved, checks it out, runs the platform migration chains, and rebuilds and restarts the API with Docker
# Compose. Postgres keeps its volume; .env.api is untracked and survives `git reset --hard`.
#
# What it follows, from EOS_DEPLOY_REF in /etc/eos/api-autodeploy.env (optional):
#   main (default)  staging: every merge to main
#   latest-tag      production: the highest vX.Y.Z release tag (v0.10.0 is above v0.9.0; pre-releases
#                   such as v1.0.0-rc1 never count), the same one .github/workflows/web.yml publishes to
#                   `web-release`. A tag whose commit is not on main is refused.
set -euo pipefail

CONFIG="${EOS_AUTODEPLOY_CONFIG:-/etc/eos/api-autodeploy.env}"
# shellcheck source=/dev/null
[ -f "$CONFIG" ] && . "$CONFIG"

APP="${EOS_APP_DIR:-/opt/education-os}"
REF="${EOS_DEPLOY_REF:-main}"
COMPOSE="docker compose -f $APP/infra/docker/docker-compose.api.yml --env-file $APP/infra/docker/.env.api"

# Never run two copies at once (timer vs manual run).
exec 9>"${EOS_AUTODEPLOY_LOCK:-/run/lock/eos-api-autodeploy.lock}"
flock -n 9 || exit 0

cd "$APP"
if [ "$REF" = latest-tag ]; then
  git fetch -q --force --prune --prune-tags --tags origin
  label="$(git tag -l 'v*' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1 || true)"
  if [ -z "$label" ]; then
    logger -t eos-api-autodeploy "no v* release tag yet; nothing deployed"
    exit 0
  fi
  target="refs/tags/$label"
  # Releases come only from main. A tag on any other commit is refused, as web.yml refuses to publish
  # it, so the web and the API both stay on the previous release.
  git fetch -q origin main
  if ! git merge-base --is-ancestor "$target^{commit}" origin/main; then
    logger -t eos-api-autodeploy "$label is not on main; refused, staying on $(git rev-parse --short HEAD)"
    exit 0
  fi
else
  git fetch -q origin "$REF"
  label="$REF"
  target="origin/$REF"
fi
want="$(git rev-parse --short "$target^{commit}")"
have="$(git rev-parse --short HEAD)"
if [ "$want" = "$have" ] && [ "${FORCE:-}" != "1" ]; then
  exit 0
fi
git reset -q --hard "$target"

$COMPOSE build --quiet api
# Schema first, against the running database: every Alembic chain apps/backend/config/modules.enabled.yaml
# enables (platform services, then modules and integrations). stamp-chains.py first records chains whose
# tables the API already created at start-up, so a module enabled since the last deploy is upgraded, not
# created twice.
$COMPOSE run --rm --no-deps -T -v "$APP/infra/docker/stamp-chains.py:/repo/stamp-chains.py" api sh -c \
  'python /repo/stamp-chains.py && for d in $(python tools/scripts/enabled-modules.py chains); do (cd "$d" && alembic upgrade head) || exit 1; done' \
  || logger -t eos-api-autodeploy "migrations failed at $want; API not restarted"
$COMPOSE up -d --quiet-pull
docker image prune -f >/dev/null
logger -t eos-api-autodeploy "deployed $label $want (was $have)"
