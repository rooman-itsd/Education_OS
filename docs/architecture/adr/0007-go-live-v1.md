# ADR-0007: Go-live decision for v1.0

- **Status:** proposed (decided on 6 November 2026 at 16:00 IST)
- **Date:** 2026-10-29
- **Deciders:** Faizan (lead), Srujan (infrastructure)

## Context
The v1.0 sprint (29 October to 6 November 2026, `docs/team/sprint-v1.0.md`) ends with the 13 common
dashboards live with real data, the modules behind them, and the production environment in the
`education-os` container. The launch checklist (`docs/team/launch-checklist-v1.0.md`) lists what must be
true, with evidence, before the release is declared.

## Decision
Go-live is declared when every box of the launch checklist is ticked with evidence, or when the lead
records here which boxes are open, why that is acceptable, and the date by which each is closed. The
release is the tag `v1.0.0`; the API and the web app follow tags from that moment (`EOS_DEPLOY_REF=latest-tag`),
so a later merge to `main` reaches production only through a new tag.

Record at decision time:

| | |
|---|---|
| Decided on | |
| Tag | |
| Open checklist items | |
| Decided by | |

## Consequences
- Production changes only through tags from 6 November; `main` keeps deploying to staging.
- Tier 2 work not finished by 5 November continues as v1.1 on the same board.
- The external penetration test (#147) and the DPDP legal pass (#148) are scheduled after launch.
