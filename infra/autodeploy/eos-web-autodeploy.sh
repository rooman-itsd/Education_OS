#!/usr/bin/env bash
# Runs every minute on the nginx container (systemd timer). Pulls the `web-dist` branch,
# which GitHub Actions rebuilds on every push to main, and swaps it into the web root
# whenever the built VERSION differs from the one being served.
set -euo pipefail

REPO="${EOS_REPO:-https://github.com/rooman-itsd/Education_OS.git}"
SRC=/opt/eos-web-dist
WWW=/var/www/education-os

# Never run two copies at once (timer vs manual run).
exec 9>/run/lock/eos-web-autodeploy.lock
flock -n 9 || exit 0

if [ ! -d "$SRC/.git" ]; then
  rm -rf "$SRC"
  git clone -q --branch web-dist --single-branch --depth 1 "$REPO" "$SRC"
fi
cd "$SRC"
git fetch -q --depth 1 origin web-dist
git reset -q --hard origin/web-dist

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
logger -t eos-web-autodeploy "deployed $want (was ${have:-none})"
