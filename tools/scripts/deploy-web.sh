#!/usr/bin/env bash
# Deploy apps/frontend to DEPLOY_HOST (a Debian box with Docker and git, e.g. the education-os LXC).
#
#   DEPLOY_HOST=root@<container-ip> tools/scripts/deploy-web.sh                    # remote build (default)
#   DEPLOY_MODE=local DEPLOY_HOST=root@<container-ip> tools/scripts/deploy-web.sh  # build here, ship image
#
# remote: the host clones/pulls the public repo at the commit you have checked out and builds there.
# local : build the image on this machine and stream it over SSH (needs Docker here).
# EOS_WEB_PORT (default 80) is the port nginx listens on inside the host.
set -euo pipefail

HOST="${DEPLOY_HOST:?set DEPLOY_HOST, e.g. root@<container-ip>}"
MODE="${DEPLOY_MODE:-remote}"
PORT="${EOS_WEB_PORT:-80}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REPO_URL="${REPO_URL:-https://github.com/rooman-itsd/Education_OS.git}"
REMOTE_DIR="/opt/education-os"
TAG="$(git -C "$ROOT" rev-parse --short HEAD)"

if [ -n "$(git -C "$ROOT" status --porcelain)" ]; then
  echo "warning: uncommitted changes here; the remote build uses commit $TAG as pushed to origin" >&2
fi

case "$MODE" in
  remote)
    echo "==> building eos-web:$TAG on $HOST"
    ssh "$HOST" "set -e
      if [ ! -d $REMOTE_DIR/.git ]; then git clone -q $REPO_URL $REMOTE_DIR; fi
      cd $REMOTE_DIR && git fetch -q origin && git checkout -q $TAG
      docker build -q -f infra/docker/web.Dockerfile -t eos-web:$TAG -t eos-web:latest .
      printf 'EOS_WEB_TAG=%s\nEOS_WEB_PORT=%s\n' '$TAG' '$PORT' > infra/docker/.env
      docker compose -f infra/docker/docker-compose.yml --env-file infra/docker/.env up -d --remove-orphans
      docker image prune -f >/dev/null"
    ;;
  local)
    echo "==> building eos-web:$TAG locally"
    docker build -q -f "$ROOT/infra/docker/web.Dockerfile" -t "eos-web:$TAG" -t eos-web:latest "$ROOT"
    echo "==> shipping image to $HOST"
    docker save "eos-web:$TAG" eos-web:latest | gzip | ssh "$HOST" 'gunzip | docker load'
    ssh "$HOST" "mkdir -p $REMOTE_DIR/infra/docker"
    scp -q "$ROOT/infra/docker/docker-compose.yml" "$HOST:$REMOTE_DIR/infra/docker/docker-compose.yml"
    ssh "$HOST" "cd $REMOTE_DIR && printf 'EOS_WEB_TAG=%s\nEOS_WEB_PORT=%s\n' '$TAG' '$PORT' > infra/docker/.env && docker compose -f infra/docker/docker-compose.yml --env-file infra/docker/.env up -d --remove-orphans && docker image prune -f >/dev/null"
    ;;
  *) echo "DEPLOY_MODE must be remote or local" >&2; exit 1 ;;
esac

echo "==> deployed eos-web:$TAG. Open http://${HOST#*@}:$PORT/?role=student"
