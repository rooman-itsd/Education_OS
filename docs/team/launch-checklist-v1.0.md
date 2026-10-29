# Launch checklist: v1.0, Thursday 6 November 2026

Issue #149, batch #313. Go-live is decided at 16:00 on 6 November by Faizan with Srujan, recorded in
[ADR-0007](../architecture/adr/0007-go-live-v1.md). A box is ticked only with evidence (a link, a
command output pasted in the issue, or a screenshot).

## Code and scope
- [ ] Every tier 1 batch closed (#313, #316, #317, #318, #321, #325, #326, #328, #331, #335, #336, #338, #342, #343, #345, #346) — Faizan
- [ ] Tier 2 batches closed or explicitly carried to v1.1 with the lead's note on each — Faizan
- [ ] `main` green on the last commit; no open PR labelled `sprint:v1.0` — Srujan
- [ ] Release tag `v1.0.0` on `main`; `web-release` and the API follow the tag (`EOS_DEPLOY_REF=latest-tag`) — Srujan

## Environment
- [ ] API runs in the `education-os` container as `eos_app`; `/api/v1/health` answers `{"status":"ok"}` from https://educationos.futureacad.ae — Srujan
- [ ] `.env.api` on the server: `EOS_DEV_MODE=false`, `EOS_JWT_SECRET` not the development default, `EOS_CORS_ORIGINS` = the public URL only, `BILLING_PAYMENT_ADAPTER` set — Srujan, verified by Faizan
- [ ] Security headers and rate limits answer on the public URL (`curl -I`, 429 after the login burst) — Faizan
- [ ] Nightly backup ran last night and `eos-db-restore --check` passed on the latest dump — Srujan
- [ ] Restore drill done once on staging and timed — Srujan (#345)
- [ ] Logs and uptime alert configured; the on-call phone known to the team — Srujan
- [ ] Proxmox root password rotated; SSH keys only — Srujan

## Product
- [ ] The 13 common dashboards pass their Playwright journeys against the release candidate (`pnpm --filter e2e exec playwright test dashboards/`) — Srujan
- [ ] A new organisation can register, verify, be approved and sign in on the public URL (smoke journey) — Faizan
- [ ] Emails send from the server (verification, approval, trial) — Himanshu
- [ ] The first paying organisation's plan and invoice are correct in billing — Gokula Lakshmi, Faizan
- [ ] Super admin screens: approval queue, organisations, subscriptions — Srujan

## Governance
- [ ] Security review filed (`docs/architecture/security-review-2026-10.md`); open findings assigned — Faizan
- [ ] Runbooks reviewed: deploy, rollback (`git reset` to the previous tag plus `FORCE=1` on the auto-deploy), restore, rotate secrets — Srujan (#348)
- [ ] Privacy notice and terms published on the public site; DPDP items listed for after launch (#148) — Praveen, Faizan
- [ ] Go-live decision recorded in ADR-0007 with the date, the tag and who decided — Faizan

## Rollback
If a blocking defect appears after go-live: set `EOS_DEPLOY_REF` back to the previous tag on the API
host, run the auto-deploy with `FORCE=1`, and repoint `web-release`; the database is not rolled back
(migrations are forward-only); restore from the last backup only for data loss, following
`infra/backup-dr/README.md`.
