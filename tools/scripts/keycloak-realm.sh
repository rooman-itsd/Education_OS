#!/usr/bin/env bash
# Create (or bring up to date) one organisation's Keycloak realm through the Admin REST API (ADR-0006).
# A pilot organisation gets its realm by hand with this until the integrations/keycloak adapter lets
# platform/tenancy create it at approval. Safe to re-run: an existing realm, client or mapper is updated,
# never duplicated. Nothing is written to disk; the admin password comes from the environment or a prompt.
#
#   KEYCLOAK_ADMIN_PASSWORD=... tools/scripts/keycloak-realm.sh <slug> [redirect-uri ...]
#
# Environment:
#   KEYCLOAK_URL             the public base, default https://educationos.futureacad.ae/auth
#   KEYCLOAK_ADMIN           master-realm admin user, default admin
#   KEYCLOAK_ADMIN_PASSWORD  its password; prompted for when unset
#   EOS_OIDC_CLIENT_ID       the public client every realm holds, default education-os-web
#   EOS_WEB_ORIGIN           the web shell's origin, default derived from KEYCLOAK_URL; its /* is the
#                            default redirect URI when none is given
#   REALM_DISPLAY_NAME       shown on the sign-in page, default the slug
#
# What it sets up, per docs in platform/identity/README.md ("Signing in through Keycloak"):
#   realm <slug>             enabled; email is the login; no self-registration; password reset by email
#   client <client id>       public (no secret), authorization code flow only, PKCE S256 required,
#                            the given redirect URIs, web origin +, default scopes basic email profile
#                            (basic carries `sub` into access tokens since Keycloak 25)
#   audience mapper          puts the client id in the access token's aud, so the API accepts it
# Needs curl and python3 (for JSON). Run it from a laptop or the API host.
set -euo pipefail

SLUG="${1:?usage: keycloak-realm.sh <slug> [redirect-uri ...]}"
shift || true
[[ "$SLUG" =~ ^[a-z0-9][a-z0-9-]{0,39}$ ]] || { echo "error: slug must be lower-case letters, digits and dashes" >&2; exit 2; }

URL="${KEYCLOAK_URL:-https://educationos.futureacad.ae/auth}"
URL="${URL%/}"
ADMIN="${KEYCLOAK_ADMIN:-admin}"
CLIENT_ID="${EOS_OIDC_CLIENT_ID:-education-os-web}"
ORIGIN="${EOS_WEB_ORIGIN:-$(python3 -c 'import sys,urllib.parse as u;p=u.urlsplit(sys.argv[1]);print(f"{p.scheme}://{p.netloc}")' "$URL")}"
DISPLAY="${REALM_DISPLAY_NAME:-$SLUG}"
if [ $# -gt 0 ]; then REDIRECTS=("$@"); else REDIRECTS=("$ORIGIN/*"); fi
command -v curl >/dev/null || { echo "error: curl not found" >&2; exit 1; }
command -v python3 >/dev/null || { echo "error: python3 not found" >&2; exit 1; }

if [ -z "${KEYCLOAK_ADMIN_PASSWORD:-}" ]; then
  read -rsp "Keycloak admin password for $ADMIN at $URL: " KEYCLOAK_ADMIN_PASSWORD
  echo
fi

# ---- helpers -------------------------------------------------------------------------------------------
json() { python3 -c 'import json,sys; print(json.dumps(json.loads(sys.stdin.read())))'; }
jget() { python3 -c 'import json,sys; d=json.load(sys.stdin); v=d
for k in sys.argv[1].split("."):
    v = v[int(k)] if isinstance(v, list) else v.get(k)
    if v is None: break
print("" if v is None else v)' "$1"; }
jlist() { python3 -c 'import json,sys; print(json.dumps([json.loads(a) for a in sys.argv[1:]]))' "$@"; }

TOKEN="$(curl -fsS -X POST "$URL/realms/master/protocol/openid-connect/token" \
  -d grant_type=password -d client_id=admin-cli -d "username=$ADMIN" --data-urlencode "password=$KEYCLOAK_ADMIN_PASSWORD" |
  jget access_token)"
unset KEYCLOAK_ADMIN_PASSWORD
[ -n "$TOKEN" ] || { echo "error: no admin token (wrong user or password?)" >&2; exit 1; }
api() { # api <method> <path> [json body]  -> body; status in $STATUS
  local method="$1" path="$2" body="${3:-}" out
  if [ -n "$body" ]; then
    out="$(curl -sS -o /dev/stdout -w '\n%{http_code}' -X "$method" "$URL/admin/realms$path" \
      -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" --data "$body")"
  else
    out="$(curl -sS -o /dev/stdout -w '\n%{http_code}' -X "$method" "$URL/admin/realms$path" -H "Authorization: Bearer $TOKEN")"
  fi
  STATUS="${out##*$'\n'}"
  printf '%s' "${out%$'\n'*}"
}
expect() { # expect <ok-codes-regex> <what>
  [[ "$STATUS" =~ ^($1)$ ]] || { echo "error: $2 answered HTTP $STATUS" >&2; exit 1; }
}

# ---- realm ---------------------------------------------------------------------------------------------
REALM_BODY="$(cat <<EOF | json
{
  "realm": "$SLUG",
  "displayName": "$DISPLAY",
  "enabled": true,
  "registrationAllowed": false,
  "loginWithEmailAllowed": true,
  "registrationEmailAsUsername": true,
  "duplicateEmailsAllowed": false,
  "resetPasswordAllowed": true,
  "verifyEmail": true,
  "bruteForceProtected": true,
  "sslRequired": "external"
}
EOF
)"
api GET "/$SLUG" >/dev/null
if [ "$STATUS" = 404 ]; then
  api POST "" "$REALM_BODY" >/dev/null; expect "201" "creating realm $SLUG"
  echo "realm $SLUG: created"
else
  expect "200" "reading realm $SLUG"
  api PUT "/$SLUG" "$REALM_BODY" >/dev/null; expect "204" "updating realm $SLUG"
  echo "realm $SLUG: exists, settings refreshed"
fi

# ---- the web shell's public client ----------------------------------------------------------------------
redirects="$(printf '"%s" ' "${REDIRECTS[@]}" | sed 's/ $//; s/" "/", "/g')"
CLIENT_BODY="$(cat <<EOF | json
{
  "clientId": "$CLIENT_ID",
  "name": "Education OS web shell",
  "protocol": "openid-connect",
  "enabled": true,
  "publicClient": true,
  "standardFlowEnabled": true,
  "implicitFlowEnabled": false,
  "directAccessGrantsEnabled": false,
  "serviceAccountsEnabled": false,
  "fullScopeAllowed": false,
  "redirectUris": [$redirects],
  "webOrigins": ["+"],
  "defaultClientScopes": ["basic", "email", "profile", "web-origins"],
  "optionalClientScopes": [],
  "attributes": {
    "pkce.code.challenge.method": "S256",
    "post.logout.redirect.uris": "+"
  }
}
EOF
)"
existing="$(api GET "/$SLUG/clients?clientId=$CLIENT_ID")"; expect "200" "listing clients"
client_uuid="$(printf '%s' "$existing" | jget 0.id)"
if [ -z "$client_uuid" ]; then
  api POST "/$SLUG/clients" "$CLIENT_BODY" >/dev/null; expect "201" "creating client $CLIENT_ID"
  client_uuid="$(api GET "/$SLUG/clients?clientId=$CLIENT_ID" | jget 0.id)"
  echo "client $CLIENT_ID: created"
else
  api PUT "/$SLUG/clients/$client_uuid" "$CLIENT_BODY" >/dev/null; expect "204" "updating client $CLIENT_ID"
  echo "client $CLIENT_ID: exists, settings refreshed"
fi

# ---- audience mapper: access tokens carry aud = client id, which the API checks --------------------------
MAPPER_NAME="education-os-audience"
MAPPER_BODY="$(cat <<EOF | json
{
  "name": "$MAPPER_NAME",
  "protocol": "openid-connect",
  "protocolMapper": "oidc-audience-mapper",
  "consentRequired": false,
  "config": {
    "included.client.audience": "$CLIENT_ID",
    "id.token.claim": "false",
    "access.token.claim": "true",
    "introspection.token.claim": "true"
  }
}
EOF
)"
mappers="$(api GET "/$SLUG/clients/$client_uuid/protocol-mappers/models")"; expect "200" "listing mappers"
if printf '%s' "$mappers" | python3 -c 'import json,sys; sys.exit(0 if any(m.get("name")==sys.argv[1] for m in json.load(sys.stdin)) else 1)' "$MAPPER_NAME"; then
  echo "audience mapper: exists"
else
  api POST "/$SLUG/clients/$client_uuid/protocol-mappers/models" "$MAPPER_BODY" >/dev/null; expect "201" "creating the audience mapper"
  echo "audience mapper: created"
fi

cat <<EOF

done. Issuer: $URL/realms/$SLUG
  sign-in page:   $URL/realms/$SLUG/account
  admin console:  $URL/admin/$SLUG/console  (users, identity providers for Google / Microsoft / SAML)
On the API host, add "$SLUG" to EOS_OIDC_REALMS in infra/docker/.env.api (comma-separated) and
\`docker compose ... up -d\` the api service. Users must exist in platform/identity with the same email
before their first sign-in (ADR-0006 decision 4): the realm authenticates, identity decides who has an account.
EOF
