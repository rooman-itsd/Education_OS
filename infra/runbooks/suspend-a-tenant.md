# Suspend a tenant (and switch it back on)

A tenant is one organisation. Suspending it blocks it at once and keeps all its data.

**Who decides:** the lead (Faizan). The one exception is a suspected leak of one organisation's data to another:
suspend first, tell the lead straight after.

**Use it for:** non-payment the lead has decided to act on, abuse, a security incident that involves one
organisation, a legal request. **Not for:** deleting an organisation (that is the deletion request, with a 30-day
hold, in `platform/tenancy`; ask the lead) or for a trial that has ended (billing moves that organisation to
read-only or suspends it by itself, per the plan's policy).

## What suspending does

- Nobody of that organisation can sign in: the answer is `organisation is suspended`.
- A person already signed in is refused too: every request to a feature module answers `403` with the code
  `organisation_inactive`, token or not. Tokens last 12 hours by default (`EOS_JWT_TTL_MINUTES`).
- Nothing is deleted. Backups, files and records stay; so does the organisation's slug.
- The change is recorded in the audit trail as a super admin action (`tenancy.organisation.suspended`, with your reason).
- Other organisations are not affected.

There is no screen for this in the admin console yet: it is one API call, made on the API host.

## Suspend

```
read -r -p "Super admin email: " E; read -r -s -p "Password: " P; echo
BASE=http://127.0.0.1:8000/api/v1
TOKEN=$(curl -s -X POST "$BASE/identity/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$E\",\"password\":\"$P\"}" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
[ -n "$TOKEN" ] && echo "signed in" || echo "sign-in failed"
unset P
```

Find the organisation. The list shows each one's `id`, `slug` and `status`; copy the `id` of the right slug:

```
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/tenancy/admin/organisations?status=active"
```

Suspend it, with the reason in plain words (it is stored in the audit trail and may be shown to the organisation's
admins: no personal data and nothing about other organisations):

```
read -r -p "Organisation id: " ORG; read -r -p "Reason: " WHY
curl -s -X PUT "$BASE/tenancy/admin/organisations/$ORG/status" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d "{\"status\":\"suspended\",\"reason\":\"$WHY\"}"
```

The answer shows `"status":"suspended"`. A reason containing a double quote breaks the call: use plain words.

**Check:** try to sign in as one of its users (or ask the lead to); the answer must be `organisation is suspended`. Then
note the time and the reason in the team channel.

## Switch it back on

Same commands, with `"status":"active"` and the reason for reactivating:

```
read -r -p "Reason: " WHY
curl -s -X PUT "$BASE/tenancy/admin/organisations/$ORG/status" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d "{\"status\":\"active\",\"reason\":\"$WHY\"}"
```

(Run the first block again if the token has expired.) The organisation's users can sign in again at once; their
data is as they left it. Unset the token when you are done: `unset TOKEN`.

## Other statuses

`PUT .../status` also takes `archived` (closed, data kept per policy). Use it only on the lead's instruction, and
never to delete: a purge is a separate, audited operation (`platform/tenancy`).
