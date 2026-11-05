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

## Rollback
Both the API host (`EOS_DEPLOY_REF=latest-tag`) and `web-release` follow the **highest** `vX.Y.Z` tag,
and a tag is never deleted or moved. To roll back, tag the last good commit with the next patch version
(for example `v1.0.1` on the commit `v1.0.0` replaced) and push the tag: the API auto-deploy and the web
publish pick it up within two minutes. The database is not rolled back (migrations are forward-only);
restore from the last backup only for data loss, following `infra/backup-dr/README.md`.
