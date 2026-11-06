# ADR-0007: Go-live decision for v1.0

- **Status:** accepted on 5 November 2026: no launch on 6 November; v1.0 goes live only when it is complete
- **Date:** 2026-10-29
- **Deciders:** Faizan (lead), Srujan (infrastructure)

## Context
The v1.0 sprint (29 October to 6 November 2026, `docs/team/sprint-v1.0.md`) ends with the 13 common
dashboards live with real data, the modules behind them, and the production environment in the
`education-os` container. The launch checklist (`docs/team/launch-checklist-v1.0.md`) lists what must be
true, with evidence, before the release is declared.

## Decision
Go-live is declared only when every box of the launch checklist is ticked with evidence. There is no fixed
date and no partial launch: the lead decided on 5 November 2026 not to release on 6 November and not to
launch with open boxes. The checklist's scope section requires every module in `modules/` to be built,
reviewed, merged and enabled, and the API to answer on the public URL. The
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
- Production changes only through tags from go-live; until then `main` keeps deploying to staging.
- Tier 2 is not deferred to v1.1: every batch stays on the v1.0 board until it is closed.
- Target date 12 November 2026 (lead, 5 November): the whole application, including search (#87), the six
  integrations against sandboxes (#141 to #146) and the DPDP pass (#148). Only the external penetration test
  (#147) is scheduled after launch.
