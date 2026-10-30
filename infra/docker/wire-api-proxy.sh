#!/usr/bin/env bash
# Point the public vhost's /api/ at the API container and /auth/ at Keycloak on the same host
# (ADR-0006). Runs as root inside the nginx reverse-proxy container; tools/scripts/deploy-api-lxc.sh
# pushes and runs it. Adds each location block when the live vhost has none (the first deploy
# predates the API), otherwise rewrites the IP in place.
#   bash wire-api-proxy.sh <api-host-ip> [server-name]
set -euo pipefail
IP="${1:?api host ip}"
NAME="${2:-educationos.futureacad.ae}"
DIRS="/etc/nginx/sites-enabled /etc/nginx/sites-available"

# shellcheck disable=SC2086
V="$(grep -rlE 'proxy_pass http://(<api-host>|[0-9.]+):8000/api/' $DIRS 2>/dev/null | head -1 || true)"
if [ -n "$V" ]; then
  sed -i -E "s#proxy_pass http://(<api-host>|[0-9.]+):8000/api/#proxy_pass http://$IP:8000/api/#" "$V"
else
  # shellcheck disable=SC2086
  V="$(grep -rl "server_name $NAME;" $DIRS 2>/dev/null | head -1 || true)"
  [ -n "$V" ] || { echo "no vhost for $NAME under $DIRS" >&2; exit 1; }
  awk -v ip="$IP" '
    /^[ \t]*location \/ \{/ && !done {
      print "    # API host (apps/backend); set by infra/docker/wire-api-proxy.sh"
      print "    location /api/ {"
      print "        proxy_pass http://" ip ":8000/api/;"
      print "        proxy_http_version 1.1;"
      print "        proxy_set_header Host              $host;"
      print "        proxy_set_header X-Real-IP         $remote_addr;"
      print "        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;"
      print "        proxy_set_header X-Forwarded-Proto $scheme;"
      print "        proxy_read_timeout 60s;"
      print "    }"
      print ""
      done = 1
    }
    { print }' "$V" > "$V.new"
  mv "$V.new" "$V"
fi

# Keycloak (docker-compose.api.yml `keycloak`, port 8080, KC_HTTP_RELATIVE_PATH=/auth). The X-Forwarded-*
# headers are what KC_PROXY_HEADERS=xforwarded trusts to build its public URLs; the buffer sizes fit its
# larger headers; the body size allows realm imports in the admin console.
if grep -qE 'proxy_pass http://[0-9.]+:8080/auth/' "$V"; then
  sed -i -E "s#proxy_pass http://[0-9.]+:8080/auth/#proxy_pass http://$IP:8080/auth/#" "$V"
else
  awk -v ip="$IP" '
    /^[ \t]*location \/ \{/ && !done {
      print "    # Keycloak, the OIDC provider (ADR-0006); set by infra/docker/wire-api-proxy.sh"
      print "    location /auth/ {"
      print "        proxy_pass http://" ip ":8080/auth/;"
      print "        proxy_http_version 1.1;"
      print "        proxy_set_header Host              $host;"
      print "        proxy_set_header X-Real-IP         $remote_addr;"
      print "        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;"
      print "        proxy_set_header X-Forwarded-Proto $scheme;"
      print "        proxy_set_header X-Forwarded-Host  $host;"
      print "        proxy_set_header X-Forwarded-Port  $server_port;"
      print "        proxy_buffer_size 16k;"
      print "        proxy_buffers 4 32k;"
      print "        client_max_body_size 10m;"
      print "        proxy_read_timeout 60s;"
      print "    }"
      print ""
      done = 1
    }
    { print }' "$V" > "$V.new"
  mv "$V.new" "$V"
fi
grep -n "proxy_pass" "$V"
nginx -t -q && nginx -s reload
echo "proxy ok: /api/ -> $IP:8000, /auth/ -> $IP:8080 in $V"
