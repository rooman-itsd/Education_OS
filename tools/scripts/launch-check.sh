#!/usr/bin/env bash
# Launch checks against the public site, for docs/team/launch-checklist-v1.0.md. Read-only apart from the sign-in
# burst, which posts a made-up email to the sign-in route until the gateway answers 429 (no account is touched).
#
#   tools/scripts/launch-check.sh [BASE_URL]          default https://educationos.futureacad.ae
#   SKIP_RATE_LIMIT=1   skip the sign-in burst          SKIP_TLS=1   skip the certificate check (plain http)
#   LOGIN_BURST=12      sign-in attempts before a 429 is required (EOS_RATE_LIMIT_LOGIN_BURST is 10 by default)
#
# Prints one PASS/FAIL line per check and exits 1 when any check fails. Needs curl; the TLS check needs openssl.
set -uo pipefail

BASE="${1:-${BASE_URL:-https://educationos.futureacad.ae}}"
BASE="${BASE%/}"
LOGIN_BURST="${LOGIN_BURST:-12}"
HEALTH="$BASE/api/v1/health"
LOGIN="$BASE/api/v1/identity/auth/login"
failed=0
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; failed=1; }
check() { if [ "$1" = 0 ]; then pass "$2"; else fail "$2${3:+ ($3)}"; fi; }

# --- the API answers, not the web app (the /api/ proxy is wired) -----------------------------------------------
code="$(curl -sS -m 15 -D "$tmp/h" -o "$tmp/b" -w '%{http_code}' "$HEALTH" 2>"$tmp/err")" || code="000"
ctype="$(grep -i '^content-type:' "$tmp/h" 2>/dev/null | tr -d '\r' | cut -d: -f2- | tr -d ' ')"
case "$code:$ctype" in
  200:application/json*) pass "/api/v1/health answers JSON from the API" ;;
  200:text/html*) fail "/api/v1/health returns the web app's HTML: the public /api/ proxy does not reach the API" ;;
  *) fail "/api/v1/health answered $code ${ctype:-no content-type} $(head -c 200 "$tmp/err" 2>/dev/null)" ;;
esac
body="$(cat "$tmp/b" 2>/dev/null)"
grep -q '"status": *"ok"' <<<"$body"; check $? 'health: "status": "ok"'
grep -q '"database": *"postgres"' <<<"$body"; check $? 'health: the database is postgres' "$(grep -o '"database": *"[a-z]*"' <<<"$body")"
grep -q '"dev_mode": *false' <<<"$body"; check $? 'health: dev_mode is false (EOS_DEV_MODE=false in .env.api)' "$(grep -o '"dev_mode": *[a-z]*' <<<"$body")"

# --- security headers on API responses (platform/api-gateway) ----------------------------------------------------
header() { grep -i "^$1:" "$tmp/h" 2>/dev/null | tr -d '\r' | cut -d: -f2- | sed 's/^ *//'; }
[ "$(header X-Content-Type-Options)" = nosniff ]; check $? "X-Content-Type-Options: nosniff"
[ "$(header X-Frame-Options)" = DENY ]; check $? "X-Frame-Options: DENY"
[ -n "$(header Referrer-Policy)" ]; check $? "Referrer-Policy is set"
[ -n "$(header Permissions-Policy)" ]; check $? "Permissions-Policy is set"
[ -n "$(header Content-Security-Policy)" ]; check $? "Content-Security-Policy is set"
case "$(header Cache-Control)" in *no-store*) pass "Cache-Control: no-store on /api/" ;; *) fail "Cache-Control: no-store on /api/" ;; esac
if [ "${BASE#https://}" != "$BASE" ]; then
  case "$(header Strict-Transport-Security)" in
    *max-age=*) pass "Strict-Transport-Security is set (the API sees https: EOS_FORWARDED_ALLOW_IPS)" ;;
    *) fail "Strict-Transport-Security is missing: the API does not see https (EOS_FORWARDED_ALLOW_IPS)" ;;
  esac
fi

# --- CORS: a foreign origin is not allowed (EOS_CORS_ORIGINS = the public URL only) ------------------------------
acao="$(curl -sS -m 15 -D - -o /dev/null -X OPTIONS "$HEALTH" -H 'Origin: https://not-this-site.example' \
  -H 'Access-Control-Request-Method: GET' 2>/dev/null | grep -i '^access-control-allow-origin:' | tr -d '\r')"
case "$acao" in
  *not-this-site.example* | *'*'*) fail "CORS allows a foreign origin ($acao)" ;;
  *) pass "CORS refuses a foreign origin" ;;
esac

# --- the sign-in burst is rate limited ----------------------------------------------------------------------------
if [ "${SKIP_RATE_LIMIT:-0}" != 1 ]; then
  email="launch-check-$RANDOM$RANDOM@example.invalid"
  got429=""
  for _ in $(seq 1 "$LOGIN_BURST"); do
    c="$(curl -sS -m 15 -D "$tmp/lh" -o /dev/null -w '%{http_code}' -X POST "$LOGIN" \
      -H 'content-type: application/json' --data "{\"email\":\"$email\",\"password\":\"not-a-password\"}" 2>/dev/null)"
    if [ "$c" = 429 ]; then got429=1; break; fi
  done
  if [ -n "$got429" ] && grep -qi '^retry-after:' "$tmp/lh"; then
    pass "sign-in burst: 429 with Retry-After within $LOGIN_BURST attempts"
  else
    fail "sign-in burst: no 429 with Retry-After within $LOGIN_BURST attempts (last answer $c)"
  fi
fi

# --- TLS certificate --------------------------------------------------------------------------------------------
if [ "${SKIP_TLS:-0}" != 1 ] && [ "${BASE#https://}" != "$BASE" ]; then
  host="${BASE#https://}"; host="${host%%/*}"
  end="$(echo | openssl s_client -servername "$host" -connect "$host:443" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)"
  if [ -z "$end" ]; then
    fail "TLS: could not read the certificate of $host"
  else
    days=$(( ($(date -d "$end" +%s) - $(date +%s)) / 86400 ))
    [ "$days" -gt 14 ]; check $? "TLS certificate valid for more than 14 days ($days left, until $end)"
  fi
fi

exit "$failed"
