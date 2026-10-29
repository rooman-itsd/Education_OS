# Security review, October 2026 (v1.0 launch)

Internal review before the 6 November 2026 release (issue #147, batch #314). Scope: the platform core
(identity, tenancy, billing, the host and its entitlement gate), the registration flow, the row-level
security model, and every module merged in October. The external penetration test is after launch.

Reviewer: Faizan, with the review findings of the sprint's pull requests. Date: 29 October 2026.

## 1. Threat model

| Asset | Threat | Where it is stopped |
|---|---|---|
| One organisation's data | Another organisation's user reads or writes it | Postgres row-level security on every tenant table (`eos_core.rls.POLICY`, `FORCE`), the API connecting as the non-superuser `eos_app` (#272), `app.organisation_id` set per transaction from the verified token (#274), and `eos_core.db.scoped` / explicit filters in every module; foreign rows answer 404 |
| Platform data (organisations, plans, invoices) | An organisation user reaches super-admin routes | Catalogue permission keys on every platform route (`require("platform:…")`, enforced by `apps/backend/tests/test_platform_permissions.py`); `platform:*` keys are granted only to `super-admin` |
| Modules an organisation has not paid for | Calls to a module outside the entitlement | The entitlement gate in the host (`apps/backend/src/eos_backend/gateway.py`): feature modules need an organisation user whose organisation is active and entitled |
| User accounts | Credential stuffing, weak passwords, token theft | PBKDF2-HMAC-SHA256, 200 000 iterations, 16-byte salt; passwords at least 8 characters; HS256 tokens with a 12-hour life; a login rate limit (#77); OIDC through Keycloak for institutions (#76) |
| Sign-up | Fake organisations, slug squatting, email bombing | Email verification before an organisation exists for anyone, super-admin approval before it goes live, one registration token per email, a registration rate limit (#77) |
| Roles | A person holding a machine role | The `service` role can be held by no person (#299) and never appears in a minted token |
| Secrets | Secrets in git or in logs | `.env*` ignored, `*.example` templates only, secrets generated on the server by `deploy-api-lxc.sh`; nothing personal is logged (ids only) |

## 2. Checks performed

**Row-level security.** Every table of every merged module carries `organisation_id` and the policy
(`tools/scripts/check-migrations.py` in CI; `apps/backend/tests/test_rls_role.py` on Postgres). Found
and fixed: identity's pre-auth lookup left `app.bypass_rls` on for the rest of the request, which made
the policies inert for every authenticated request on Postgres (#274). The API now runs as `eos_app`,
which cannot bypass the policies at all (#272).

**Permissions.** Every platform route names a catalogue key. Found and fixed: a module whose catalogue
listed no roles was unreachable in production while its tests passed through a forged `perms` claim
(student-information, #278); a module whose only writing role exists in no academy profile
(enrolment-registration, #291); a legacy row holding `service` logged in with a token carrying it
(#299). Rule recorded in `docs/team/pr-review` notes: tests mint tokens with roles only.

**Approval workflows.** Self-approval is refused on every decision route reviewed (procurement indents,
orders and invoices, budget-grants, asset disposals). Found and fixed: an order's creator could approve
it after someone else submitted (#295).

**Money and dates.** Decimal end to end, two-decimal rounding, no floats; currency mismatch refused.
Found and fixed: an acquisition patch reset an asset's cost to zero and could drive the book value
negative; future depreciation periods and disposal dates were accepted (#277); a lapsed admissions
offer left the application stuck (#290); a naive clock stand-in was read as local time (#293).

**Input handling.** `extra="forbid"` on every request schema reviewed; explicit `null` in a PATCH is
refused on non-nullable fields; `q` search parameters escape `%`, `_` and `\`; CMS bodies are stored
as text and rendered as text (no HTML injection, #302).

**Registration and public routes.** Verification token, then approval. Public admissions routes
(when the gateway follow-up exposes them) must take the organisation from the slug only, never from a
token or request state; the module already refuses otherwise. Open: a known-reference/wrong-email
answer of 403 on attach/accept/decline lets a caller enumerate reference numbers; `track` already
collapses both to 404 (#290, owner Praveen).

**Dependencies.** Python and Node dependencies are pinned (`pnpm-lock.yaml`, `uv`-style pins in each
`pyproject.toml`) and limited to `docs/architecture/approved-stack.yaml` (`check-stack.py` in CI).
Versions in use on 29 October: FastAPI 0.142, Starlette 1.7, SQLAlchemy 2.1, Pydantic 2.13, PyJWT
2.15, httpx 0.28. No advisory was open against them on the date of the review; a scheduled
`pip-audit` / `pnpm audit` job is a follow-up for Srujan (#345).

**Secrets.** `git grep` over the history for key-like literals outside tests and examples: none. The
Proxmox host is reached by SSH key; the root password of the host was shared in a chat once during
setup and must be rotated (Srujan, before go-live).

## 3. Findings

| # | Severity | Finding | Status |
|---|---|---|---|
| S1 | High | RLS inert for authenticated requests (bypass left on) | Fixed, #274 |
| S2 | High | API connected as the Postgres superuser, which ignores RLS | Fixed, #272 |
| S3 | High | A module unreachable in production hid by a forged test claim; roles not granted | Fixed, #278, #291 |
| S4 | Medium | `service` role on a person's row reached feature modules through the token | Fixed, #299 |
| S5 | Medium | No rate limit on login or registration; no security headers from the API | Fixed, #77 (this batch) |
| S6 | Medium | Self-approval of a purchase order by its creator | Fixed, #295 |
| S7 | Medium | `EOS_DEV_MODE` defaults to true and the JWT secret has a development default | Mitigated: `deploy-api-lxc.sh` writes `EOS_DEV_MODE=false` and a random secret; the launch checklist verifies both on the server. Follow-up: refuse to start with the default secret when not in dev mode (Faizan) |
| S8 | Low | Tokens live 12 hours with no revocation | Accepted for v1.0; OIDC sessions through Keycloak supersede this for institutions (#76) |
| S9 | Low | Reference-number enumeration on public admissions routes | Open, Praveen (#321) |
| S10 | Low | Public admissions submit/attach have no per-application cap | Mitigated by the gateway rate limit (#77); cap is a follow-up (Praveen) |
| S11 | Low | Database port 8000 of the API container is bound on the LAN, not only to the proxy | Open, Srujan (#345): bind to the proxy's address or firewall the container |

## 4. What the external test should cover

Registration and approval abuse, token handling across the OIDC migration, the entitlement gate for a
suspended organisation, RLS from a module that forgets `scoped`, file uploads once platform/documents
exists, and the super-admin screens. Scheduled after launch (issue #147 stays open for the report).
