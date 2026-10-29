# Sprint v1.0: 29 October to 6 November 2026

Everything on the board ships in nine days. One page, read it once.

## Dates

| When | What |
|---|---|
| Wed 29 Oct | Sprint issues on the board; first API deployment (Srujan with Faizan); every open PR reviewed and merged by its reviewer |
| Mon 3 Nov | **Tier 1 done**: the 13 common dashboards show real data on the live site, with the modules behind them. Blocks the release |
| Wed 5 Nov | **Tier 2 done**: every academy dashboard (waves B to D) and the remaining modules |
| Thu 6 Nov | Release v1.0: tag, launch checklist, no new code. Fixes only |

## How work is organised

- Every person has **one sprint issue** (`[S01]` to `[S10]`) and its **batches** (`[S01.1]`, `[S01.2]`, …), each batch merging three to six of the old issues. The old issues are closed with a pointer to their batch; nothing was dropped. The board (https://github.com/users/faizanrooman/projects/1) lists the sprint issues first; each shows its batches' progress.
- A batch is done when every box is ticked, the last PR says `Closes #batch`, and the result is visible on https://educationos.futureacad.ae.
- **Widgets are built by the module's owner** for every dashboard that shows them (one backend, one widget, many layouts). A dashboard owner wires the layout, checks the data and writes the Playwright journey.
- Tier 1 first, always. A tier 2 PR waits in the queue behind any tier 1 PR.
- After launch (not in the sprint): OpenSearch search, DigiLocker, NAD, government portals, video conferencing, wearables, external university portals, DPDP legal pass, external penetration test.

## Reviews and approvals: nobody waits for the lead

Every path in `.github/CODEOWNERS` has an owner and a backup. The backup approves the owner's PRs; the owner approves the backup's. Faizan approves only platform core (`platform/identity`, `tenancy`, `billing`, `api-gateway`), `packages/`, `docs/architecture/` and `docs/team/`; Srujan and Himanshu are his backups there, so even those do not wait.

| Person | Area | PRs approved by | Approves PRs of |
|---|---|---|---|
| Faizan (@faizanrooman) | architecture-platform | @srujanrooman, @himanshu-rooman | Srujan's apps, infra and tests PRs; every platform core change |
| Himanshu (@himanshu-rooman) | platform-services | @faizanrooman, @srujanrooman | Akshata's sports PRs; platform core with Faizan |
| Praveen (@praveen-rooman) | student-lifecycle | @shivanisinghrooman-09 | Shivani's academics PRs |
| Shivani (@shivanisinghrooman-09) | academics | @praveen-rooman | Praveen's student-lifecycle PRs |
| Akshata (@akshatatrathodrooman) | sports | @himanshu-rooman, @Ashritharooman | Himanshu's platform-services PRs |
| Ashritha (@Ashritharooman) | facilities | @gokulalakshmirooman-source | Gokula Lakshmi's finance PRs; Akshata's sports PRs with Himanshu |
| Gokula Lakshmi (@gokulalakshmirooman-source) | finance-operations | @Ashritharooman | Ashritha's facilities PRs |
| Tejaswini (@tejaswini-rooman) | campus-life | @madhumitha-rooman | Madhumita's governance and support PRs |
| Madhumita (@madhumitha-rooman) | governance-support | @tejaswini-rooman | Tejaswini's campus-life PRs |
| Srujan (@srujanrooman) | apps-infra-qa | @faizanrooman | Faizan's platform core PRs; .github and tools with Faizan |

- Review within **4 working hours**; say in the PR if you cannot. The author fixes comments the same day.
- A red PR is fixed before anything else; a PR that is red at the end of the day is closed and reopened green.
- Contract changes that another module consumes: the consumer's owner is a second reviewer. No other change needs two approvals.
- The merge button is the reviewer's. Squash merge, conventional title, `Part of #batch` or `Closes #batch` in the body.

## Every day

- 10:00: ten-minute standup on the board. Each person: merged yesterday, merges today, blocked by. Blocked means a named person and a named PR or question.
- Before 17:00: every slice that works is a PR. Nothing sits on a laptop overnight.
- Faizan reads `docs/team/STATUS.md` (team-status branch, every 6 hours) and the board, nothing else.

## Batches by person

### [S01] Faizan

| Batch | Due | Merges |
|---|---|---|
| `[S01.1]` Management dashboard and the v1.0 launch checklist | Mon 3 Nov | #12, #149 |
| `[S01.2]` Platform hardening: Keycloak/OIDC, rate limiting, data export, security review | Wed 5 Nov | #76, #77, #78, #147 |
| `[S01.3]` Research university dashboards | Wed 5 Nov | #20, #35, #50 |

### [S02] Himanshu

| Batch | Due | Merges |
|---|---|---|
| `[S02.1]` Notification, messaging adapter, event relay and scheduler | Mon 3 Nov | #79, #80, #83, #82 |
| `[S02.2]` Audit, workflow, documents and reporting services | Mon 3 Nov | #81, #85, #84, #86 |
| `[S02.3]` Department Admin dashboard and the productions module | Mon 3 Nov | #2, #115 |
| `[S02.4]` Theatre academy dashboards | Wed 5 Nov | #23, #38, #54 |
| `[S02.5]` Film and media dashboards | Wed 5 Nov | #27, #42, #58 |

### [S03] Praveen

| Batch | Due | Merges |
|---|---|---|
| `[S03.1]` Admissions, enrolment and the Applicant dashboard | Mon 3 Nov | #104, #105, #3 |
| `[S03.2]` Portfolio and selection-process modules | Wed 5 Nov | #116, #117, #106 |
| `[S03.3]` Arts academy dashboards | Wed 5 Nov | #14, #29, #44 |
| `[S03.4]` Design and fashion dashboards, user documentation | Wed 5 Nov | #26, #41, #57, #154 |

### [S04] Shivani

| Batch | Due | Merges |
|---|---|---|
| `[S04.1]` Timetable-attendance and examinations backends and widgets | Mon 3 Nov | #101, #102 |
| `[S04.2]` LMS, academic-management faculty load and the Faculty dashboard | Mon 3 Nov | #103, #100, #4 |
| `[S04.3]` Teacher education dashboards and the accessibility pass | Wed 5 Nov | #22, #37, #53, #156 |

### [S05] Akshata

| Batch | Due | Merges |
|---|---|---|
| `[S05.1]` Examination Staff dashboard | Mon 3 Nov | #5 |
| `[S05.2]` Sports modules: athlete performance, nutrition and health, video analysis, tournaments, skill progress | Wed 5 Nov | #121, #122, #124, #123, #120 |
| `[S05.3]` Sports college dashboards | Wed 5 Nov | #21, #36, #51, #52 |

### [S06] Ashritha

| Batch | Due | Merges |
|---|---|---|
| `[S06.1]` Facility Staff dashboard, facility-booking widgets and sports-facilities | Mon 3 Nov | #6, #125 |
| `[S06.2]` Music academy dashboards | Wed 5 Nov | #19, #34, #49 |
| `[S06.3]` Dance academy dashboards | Wed 5 Nov | #25, #40, #56 |
| `[S06.4]` Hospitality dashboards | Wed 5 Nov | #28, #43, #59 |

### [S07] Gokula Lakshmi

| Batch | Due | Merges |
|---|---|---|
| `[S07.1]` Procurement, payment reconciliation and the Finance Staff dashboard | Mon 3 Nov | #129, #7 |
| `[S07.2]` HR-payroll, e-office and the HR Staff dashboard | Mon 3 Nov | #130, #131, #13 |
| `[S07.3]` Placement, alumni, management institute dashboards and GST invoices | Wed 5 Nov | #132, #133, #17, #32, #47, #155 |

### [S08] Tejaswini

| Batch | Due | Merges |
|---|---|---|
| `[S08.1]` Student dashboard, transport and library | Mon 3 Nov | #8, #111, #112 |
| `[S08.2]` Field-training and projects modules | Wed 5 Nov | #119, #118 |
| `[S08.3]` Medical college dashboards | Wed 5 Nov | #18, #33, #48 |
| `[S08.4]` Agriculture dashboards | Wed 5 Nov | #24, #39, #55 |

### [S09] Madhumita

| Batch | Due | Merges |
|---|---|---|
| `[S09.1]` Support Staff dashboard: SLA, incidents, knowledge base, AMC | Mon 3 Nov | #9, #114, #139, #138, #140 |
| `[S09.2]` Governance dashboard: grievance, RTI, IQAC, regulatory reports | Mon 3 Nov | #11, #134, #135, #136, #137 |
| `[S09.3]` Law college dashboards | Wed 5 Nov | #16, #31, #46 |

### [S10] Srujan

| Batch | Due | Merges |
|---|---|---|
| `[S10.1]` Production environment: education-os container, staging, backups, restore drill, observability | Mon 3 Nov | #89, #90, #91, #151 |
| `[S10.2]` Super Admin dashboard, super admin screens, Playwright suite for the 13 common dashboards | Mon 3 Nov | #10, #95, #94, #93 |
| `[S10.3]` Engineering college dashboards | Wed 5 Nov | #15, #30, #45 |
| `[S10.4]` Launch hardening: PgBouncer, load test and SLOs, runbooks, PWA | Wed 5 Nov | #96, #152, #150, #153 |

Moves inside the sprint: `facilities/sports-facilities` goes to Ashritha (same booking pattern as facility-booking); `campus-life/placement-career` and `alumni` go to Gokula Lakshmi (the Placement Officer dashboard is hers); the Super Admin widgets (tenancy, billing) are built by Srujan with Faizan reviewing; the pool dashboards are assigned: Governance to Madhumita, HR Staff to Gokula Lakshmi, Management to Faizan, film to Himanshu, design to Praveen, dance and hospitality to Ashritha, agriculture to Tejaswini.

## Done, per batch

Contracts reviewed by the reviewer · own tables with `organisation_id` and RLS · backend with tests that pass alone and the cross-tenant leak test · every widget of the module in `frontend/src/widgets/` with tests · module listed in both `modules.enabled.yaml` files · Playwright journey per dashboard in `tests/e2e/dashboards/` · README, CHANGELOG, `config/env.example` · visible on the live site.
