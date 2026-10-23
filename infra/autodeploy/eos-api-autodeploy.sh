#!/usr/bin/env bash
# Runs every two minutes in the education-os API container (systemd timer). When `main` has moved,
# pulls it, runs the platform migration chains, and rebuilds and restarts the API with Docker Compose.
# Postgres keeps its volume; .env.api is untracked and survives `git reset --hard`.
set -euo pipefail

APP="${EOS_APP_DIR:-/opt/education-os}"
COMPOSE="docker compose -f $APP/infra/docker/docker-compose.api.yml --env-file $APP/infra/docker/.env.api"

# Never run two copies at once (timer vs manual run).
exec 9>/run/lock/eos-api-autodeploy.lock
flock -n 9 || exit 0

cd "$APP"
git fetch -q origin main
want="$(git rev-parse --short origin/main)"
have="$(git rev-parse --short HEAD)"
if [ "$want" = "$have" ] && [ "${FORCE:-}" != "1" ]; then
  exit 0
fi
git reset -q --hard origin/main

$COMPOSE build --quiet api
# Schema first: each platform service's Alembic chain, against the running database.
$COMPOSE run --rm --no-deps -T api sh -c 'for s in identity tenancy billing; do (cd platform/$s/db && alembic upgrade head); done' \
  || logger -t eos-api-autodeploy "migrations failed at $want; API not restarted"
$COMPOSE up -d --quiet-pull
docker image prune -f >/dev/null
logger -t eos-api-autodeploy "deployed $want (was $have)"
