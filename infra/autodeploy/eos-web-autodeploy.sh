#!/usr/bin/env bash
# Runs every minute on the nginx container (systemd timer). Pulls a build branch that GitHub Actions
# publishes (.github/workflows/web.yml) and swaps it into the web root whenever the built VERSION differs
# from the one being served.
#
#   eos-web-autodeploy              staging: `web-dist`, rebuilt on every push to main, into
#                                   /var/www/education-os (settings: /etc/eos/web-autodeploy.env, optional)
#   eos-web-autodeploy production   another site: settings from /etc/eos/web-autodeploy-production.env,
#                                   e.g. EOS_WEB_BRANCH=web-release (the highest release tag) and its own
#                                   EOS_WEB_ROOT. Run by eos-web-autodeploy@production.timer.
set -euo pipefail

INSTANCE="${1:-}"
CONFIG="${EOS_CONFIG_DIR:-/etc/eos}/web-autodeploy${INSTANCE:+-$INSTANCE}.env"
if [ -n "$INSTANCE" ] && [ ! -f "$CONFIG" ]; then
  echo "error: $CONFIG not found" >&2
  exit 1
fi
# shellcheck source=/dev/null
[ -f "$CONFIG" ] && . "$CONFIG"

REPO="${EOS_REPO:-https://github.com/rooman-itsd/Education_OS.git}"
BRANCH="${EOS_WEB_BRANCH:-web-dist}"
SRC="${EOS_WEB_SRC:-/opt/eos-$BRANCH}"
WWW="${EOS_WEB_ROOT:-/var/www/education-os}"
TAG="eos-web-autodeploy${INSTANCE:+@$INSTANCE}"

# Never run two copies of one site at once (timer vs manual run).
exec 9>"${EOS_LOCK_DIR:-/run/lock}/eos-web-autodeploy${INSTANCE:+-$INSTANCE}.lock"
flock -n 9 || exit 0

if [ ! -d "$SRC/.git" ]; then
  rm -rf "$SRC"
  git clone -q --branch "$BRANCH" --single-branch --depth 1 "$REPO" "$SRC"
fi
cd "$SRC"
git fetch -q --depth 1 origin "$BRANCH"
git reset -q --hard "origin/$BRANCH"

want="$(cat "$SRC/VERSION" 2>/dev/null || echo unknown)"
have="$(cat "$WWW/VERSION" 2>/dev/null || true)"
if [ "$want" = "$have" ]; then
  exit 0
fi

rm -rf "$WWW.new"
mkdir -p "$WWW.new"
tar -C "$SRC" --exclude=.git -cf - . | tar -C "$WWW.new" -xf -
rm -rf "$WWW.old"
[ -d "$WWW" ] && mv "$WWW" "$WWW.old"
mv "$WWW.new" "$WWW"

nginx -t -q && nginx -s reload
logger -t "$TAG" "deployed $want (was ${have:-none})"
