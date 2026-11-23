# Launch checklist: v1.0

Issue #149, batch #313. Target Thursday 12 November 2026; v1.0 goes live when every box below is ticked, decided by
Faizan with Srujan and recorded in [ADR-0007](../architecture/adr/0007-go-live-v1.md) (5 November 2026).
A box is ticked only with evidence (a link, a
command output pasted in the issue, or a screenshot).

## Code and scope
- [ ] Every module in `modules/` has its backend, migrations, tests and widgets merged, and is listed in both
  `apps/backend/config/modules.enabled.yaml` and `apps/frontend/config/modules.enabled.yaml` — Faizan
- [ ] Every sprint batch closed, tier 1 and tier 2 (#313 to #348); none carried to v1.1 — Faizan
- [ ] Every academy journey in `tests/e2e/dashboards/` passes with all modules enabled — Srujan
- [ ] Search (`platform/search`, OpenSearch, #87) answers on the live site — Himanshu
- [ ] The six integrations (#141 to #146) pass their tests against each provider's sandbox or recorded mock;
  DigiLocker, NAD and government portals switch to live credentials when the agency approves (not a launch blocker) — Himanshu
- [ ] `main` green on the last commit; no open PR labelled `sprint:v1.0` — Srujan
- [ ] Release tag `v1.0.0` on `main`; the API host runs with `EOS_DEPLOY_REF=latest-tag` and `web.yml` publishes the tag to `web-release`, so both follow the highest release tag — Srujan

## Environment
- [ ] API runs in the `education-os` container as `eos_app`; the public `/api/` proxy is wired and `/api/v1/health` answers `{"status":"ok"}` from https://educationos.futureacad.ae — Srujan
- [ ] Staging auto-deploy healthy (last run deployed `main` within two minutes of the merge) — Srujan
- [ ] Compose passes the mail settings through (`NOTIFICATION_*`, `MESSAGING_PROVIDERS_*`) and the event-bus relay and scheduler services run — Srujan, Himanshu
- [ ] TLS certificate valid and renewal timer active on the proxy — Srujan
- [ ] `.env.api` on the server: `EOS_DEV_MODE=false`, `EOS_JWT_SECRET` not the development default, `EOS_CORS_ORIGINS` = the public URL only, `BILLING_PAYMENT_ADAPTER` set — Srujan, verified by Faizan
- [ ] Security headers and rate limits answer on the public URL (`curl -I`, 429 after the login burst) — Faizan
- [ ] Nightly backup ran last night, `eos-db-restore --check` passed on the latest dump, and the offsite copy is current — Srujan
- [ ] Disaster-recovery drill done once and timed: rebuild the API host from the repository and the offsite backup, not only a restore on staging — Srujan (#345)
- [ ] Logs collected and an uptime alert configured (`infra/monitoring`); the on-call phone known to the team — Srujan
- [ ] Proxmox root password rotated; SSH keys only — Srujan

## Product
- [ ] The 13 common dashboards pass their Playwright journeys on the local stack checked out at the release-candidate tag (`pnpm --filter e2e exec playwright test dashboards/`; journeys need dev mode, so they do not run against the deployed site, whose smoke test runs instead) — Srujan
- [ ] A new organisation can register, verify, be approved and sign in on the public URL (smoke journey) — Faizan
- [ ] Emails send from the server (verification, approval, trial) — Himanshu
- [ ] The first paying organisation's plan and invoice are correct in billing — Gokula Lakshmi, Faizan
- [ ] Super admin screens: approval queue, organisations, subscriptions — Srujan

## Governance
- [ ] Security review filed (`docs/architecture/security-review-2026-10.md`); open findings assigned — Faizan
- [ ] Runbooks reviewed: deploy, rollback (below), restore, rotate secrets — Srujan (#348)
- [ ] Privacy notice and terms published on the public site; the DPDP pass (#148) done — Praveen, Faizan
- [ ] Go-live decision recorded in ADR-0007 with the date, the tag and who decided — Faizan

## Known issues at launch
Recorded so the release is honest about them. They are not hidden by loosening an objective.

- **The API misses the load-test objectives** (#152, [tests/performance](../../tests/performance/README.md)).
  The objective is p95 under 500 ms and p99 under 1500 ms at 50 concurrent users. Faizan decided on 23 Nov 2026 to
  profile for two days, fix the biggest cause, and tag with the real numbers here instead of changing
  `tests/performance/slo.yaml`. Measured on 23 Nov 2026 on a laptop's Docker, with one API process, 50 users and
  20 s per scenario:

  | Code | Dashboard rps | Dashboard p95 | Management rps | Management p95 |
  |---|---|---|---|---|
  | `main` at 3eced13 | 24.1 | 17.2 s | 17.7 | 23.7 s |
  | with #696, #697 and #698 (gate cache off) | 27.8 | 14.8 s | 23.5 | 19.7 s |

  Cause: the API is CPU-bound in a single process. The profile (tests/performance/README.md, "Results, 20 Nov 2026")
  ranks the gateway's per-request lookups first, then the tenant settings, route matching and the dependency
  overrides; #696 to #698 address those. The entitlement gate cache (`EOS_GATE_CACHE_SECONDS`, #698) stays `0` in
  production: 5 s added little in the same test, and with 0 a suspension or disabled user takes effect on the next
  request. Not yet measured, for v1.1: more API processes behind the pooler
  ([scale-the-api](../../infra/runbooks/scale-the-api.md)), and dispatching routes by module prefix. Numbers on the
  production host replace these once it runs. — Srujan

## Rollback
Both the API host (`EOS_DEPLOY_REF=latest-tag`) and `web-release` follow the **highest** `vX.Y.Z` tag,
and a tag is never deleted or moved. To roll back, tag the last good commit with the next patch version
(for example `v1.0.1` on the commit `v1.0.0` replaced) and push the tag: the API auto-deploy and the web
publish pick it up within two minutes. The database is not rolled back (migrations are forward-only);
restore from the last backup only for data loss, following `infra/backup-dr/README.md`.
