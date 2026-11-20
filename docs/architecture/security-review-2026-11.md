# Security review, November 2026 (v1.0 launch update)

Update of the [October review](security-review-2026-10.md) for the launch checklist item "Security review
filed; open findings assigned" (issue #314). It covers what merged after the October review (its last commit,
30 October 2026, #353) up to `origin/main` at 72ce9d2f (20 November 2026, #665), plus the open pull request
#554 (platform/integration-hub backend, branch `feat/integration-hub/backend` at e227770b).

Reviewer: Claude Code for Faizan, 20 November 2026. Status: in progress; each area is committed as it is reviewed.

## 1. Scope

Security-relevant code new or changed since 30 October, by area:

1. platform/integration-hub (#554, open): OAuth state, callback verification, the secret store and key rotation,
   the reject limit, SSRF in provider requests, tenant resolution.
2. platform/api-gateway (#363) and its deployment (`infra/`, `tools/scripts/deploy-api-lxc.sh`): rate limits,
   security headers, trusted proxies (`EOS_TRUSTED_PROXIES`, `EOS_FORWARDED_ALLOW_IPS`).
3. Authentication: Keycloak/OIDC (#365), impersonation (#655), `eos_core.security` and `eos_core.oidc`.
4. Tenancy and row-level security: every migration added since October, platform-scope consumers, terms
   acceptance (#665), export and purge (#354, #366).
5. The republish endpoints: `POST /account-links/republish` (student-information, #606),
   `POST /offerings/republish` (academic-management, #651), `POST /registrations/republish`
   (enrolment-registration, #652, open).
6. `eos_core.workflow.submit` (#654).
7. Platform services: documents (#408, #437, #645), notification (#360, #649, #659), workflow (#407, #430, #646),
   billing GST invoices (#541), audit, reporting, search, scheduler, event-bus.
8. Integrations: payment-sbiepay, messaging-providers, digilocker, nad, government-portals,
   external-university-portals, video-conferencing, wearables.
9. Secrets and configuration: `.env` examples, development defaults, `EOS_DEV_MODE` guards.

## 2. Method

Code read at the commits above. A suspected bug is confirmed with a test against that code before it is called a
finding; the table says which findings were confirmed by a test and which by reading only. Severity: critical
(exploitable now, cross-tenant or platform takeover), high (exploitable now within a tenant, or cross-tenant once a
written but unmounted component is mounted), medium, low. "Live" means mounted by
`apps/backend/config/modules.enabled.yaml` on `main`; "latent" means written but not mounted, or behind a setting
the deployment does not use. Every finding names an owner from `.github/CODEOWNERS` (Faizan for cross-cutting
ones). Medium and above have an issue.

## 3. Findings

| ID | Severity | Component | Description | Evidence | Verified | Status | Owner | Fix |
|---|---|---|---|---|---|---|---|---|

## 4. Reviewed, no findings
