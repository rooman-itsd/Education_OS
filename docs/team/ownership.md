# Module ownership

Ten people. Every module has exactly one owner and at least one backup. Owners approve
PRs to their module and maintain its contracts and docs. Mirrored in `.github/CODEOWNERS`: the backup approves the owner's PRs, so no PR waits for the lead. Sprint plan: [sprint-v1.0.md](sprint-v1.0.md).

## Suggested split (edit freely)

Widget counts come from the 59 role layouts in `platform/identity/config/dashboards/` (110 widgets in
all). The six generic `practice` modules are spread across four members. Full split, build order and
per-widget checklist: the "Dashboard Assignment Plan" doc.

| # | Area | Owner | Backup | Modules | Widgets |
|---|---|---|---|---|---|
| 1 | Architecture & platform lead | Faizan (@faizanrooman) | Srujan, Himanshu | `platform/identity`, `api-gateway`, `tenancy`, `billing`, `packages/*` | 10 |
| 2 | Platform services & integrations | Himanshu (@himanshu-rooman) | Faizan, Srujan | `platform/event-bus`, `notification`, `documents`, `workflow`, `audit`, `search`, `scheduler`, `reporting`, `integration-hub`, `modules/practice/productions`, `integrations/*` except payment | 10 |
| 3 | Student lifecycle | Praveen (@praveen-rooman) | Shivani | `modules/student-lifecycle/*`, `modules/practice/portfolio`, `modules/practice/selection-process` | 11 |
| 4 | Academics | Shivani (@shivanisinghrooman-09) | Praveen | `modules/academics/*` | 15 |
| 5 | Sports | Akshata (@akshatatrathodrooman) | Himanshu, Ashritha | `modules/sports/*`, `modules/practice/skill-progress` | 17 |
| 6 | Facilities | Ashritha (@Ashritharooman) | Gokula Lakshmi | `modules/facilities/*` (sports-facilities since 29 Oct 2026) | 8 |
| 7 | Finance & operations | Gokula Lakshmi (@gokulalakshmirooman-source) | Ashritha | `modules/finance-operations/*`, `integrations/payment-sbiepay`, `modules/campus-life/placement-career`, `modules/campus-life/alumni` (since 29 Oct 2026) | 13 |
| 8 | Campus life | Tejaswini (@tejaswini-rooman) | Madhumita | `modules/campus-life/*` except placement-career and alumni, `modules/practice/field-training`, `modules/practice/projects` | 15 |
| 9 | Governance & support | Madhumita (@madhumitha-rooman) | Tejaswini | `modules/governance/*`, `modules/support/*` | 11 |
| 10 | Apps, infra & QA | Srujan (@srujanrooman) | Faizan | `apps/*` (web incl. admin screens, api, mobile), `infra/*`, `packages/testing`, CI | 0 |

Institution profiles (`platform/identity/config/profiles/`) and dashboard layouts belong to the Architecture & platform lead.
A specialized suite for a new field gets its own owner row when the field has a customer.

## Dashboard owners (one person, one dashboard, end to end)

One application for every academy. A dashboard owner builds everything their dashboard needs,
across every module it touches, and takes the next only when theirs is Done. Module owners (table
above) review every PR into their modules. All academies are built together: wave A = the 13
common dashboards, then every academy's learner (B), instructor (C) and field staff (D) dashboards.
Each person keeps one academy through B to D. The names-to-areas mapping follows the order the
names were given and can be swapped before kickoff; GitHub handles still need filling in. Live tracker: the "Dashboard Assignment Plan" doc.

| Name (area) | Wave A (common) | Academy for waves B to D |
|---|---|---|
| Faizan (Architecture & platform lead) | Organisation Admin | Research university |
| Himanshu (Platform services & integrations) | Department Admin / HoD | Theatre academy |
| Praveen (Student lifecycle) | Applicant | Arts academy |
| Shivani (Academics) | Faculty / Instructor | Teacher education |
| Akshata (Sports) | Examination Staff | Sports college |
| Ashritha (Facilities) | Facility / Inventory Staff | Music academy |
| Gokula Lakshmi (Finance & operations) | Finance Staff | Management institute |
| Tejaswini (Campus life) | Student | Medical college |
| Madhumita (Governance & support) | Support Staff | Law college |
| Srujan (Apps, infra & QA) | Super Admin | Engineering college |
| pool, assigned 29 Oct 2026 | Governance: Madhumita · Management: Faizan · HR Staff: Gokula Lakshmi | Film: Himanshu · Dance and Hospitality: Ashritha · Design: Praveen · Agriculture: Tejaswini |

Per-person week 1 tasks: [kickoff-tasks.md](kickoff-tasks.md).
## Full module list

Status on 29 Oct 2026. The widgets of a module are built by its owner for every dashboard that shows them.

| Module | Owner | Backup | Status |
|---|---|---|---|
| `modules/academics/academic-management` | Shivani | Praveen | backend merged |
| `modules/academics/examinations` | Shivani | Praveen | sprint v1.0 |
| `modules/academics/lms` | Shivani | Praveen | sprint v1.0 |
| `modules/academics/timetable-attendance` | Shivani | Praveen | sprint v1.0 |
| `modules/campus-life/alumni` | Gokula Lakshmi | Tejaswini | sprint v1.0 |
| `modules/campus-life/hostel` | Tejaswini | Madhumita | backend merged |
| `modules/campus-life/library` | Tejaswini | Madhumita | sprint v1.0 |
| `modules/campus-life/placement-career` | Gokula Lakshmi | Tejaswini | sprint v1.0 |
| `modules/campus-life/transport` | Tejaswini | Madhumita | sprint v1.0 |
| `modules/facilities/asset-management` | Ashritha | Gokula Lakshmi | backend merged |
| `modules/facilities/facility-booking` | Ashritha | Gokula Lakshmi | backend merged |
| `modules/facilities/inventory-equipment` | Ashritha | Gokula Lakshmi | backend merged |
| `modules/facilities/maintenance` | Ashritha | Gokula Lakshmi | backend merged |
| `modules/facilities/sports-facilities` | Ashritha | Akshata | sprint v1.0 |
| `modules/finance-operations/budget-grants` | Gokula Lakshmi | Ashritha | backend merged |
| `modules/finance-operations/e-office` | Gokula Lakshmi | Ashritha | sprint v1.0 |
| `modules/finance-operations/fees-accounts` | Gokula Lakshmi | Ashritha | backend merged |
| `modules/finance-operations/hr-payroll` | Gokula Lakshmi | Ashritha | sprint v1.0 |
| `modules/finance-operations/procurement` | Gokula Lakshmi | Ashritha | in PR #294-#298 |
| `modules/governance/grievance` | Madhumita | Tejaswini | sprint v1.0 |
| `modules/governance/iqac-accreditation` | Madhumita | Tejaswini | sprint v1.0 |
| `modules/governance/regulatory-reports` | Madhumita | Tejaswini | sprint v1.0 |
| `modules/governance/rti` | Madhumita | Tejaswini | sprint v1.0 |
| `modules/practice/field-training` | Tejaswini | Madhumita | sprint v1.0 |
| `modules/practice/portfolio` | Praveen | Shivani | sprint v1.0 |
| `modules/practice/productions` | Himanshu | Akshata | sprint v1.0 |
| `modules/practice/projects` | Tejaswini | Madhumita | sprint v1.0 |
| `modules/practice/selection-process` | Praveen | Shivani | sprint v1.0 |
| `modules/practice/skill-progress` | Akshata | Himanshu, Ashritha | sprint v1.0 |
| `modules/sports/athlete-performance` | Akshata | Himanshu, Ashritha | sprint v1.0 |
| `modules/sports/sports-nutrition-health` | Akshata | Himanshu, Ashritha | sprint v1.0 |
| `modules/sports/tournament-events` | Akshata | Himanshu, Ashritha | sprint v1.0 |
| `modules/sports/training-video-analysis` | Akshata | Himanshu, Ashritha | sprint v1.0 |
| `modules/student-lifecycle/admissions` | Praveen | Shivani | in PR #290 |
| `modules/student-lifecycle/enrolment-registration` | Praveen | Shivani | in PR #291 |
| `modules/student-lifecycle/student-information` | Praveen | Shivani | backend merged |
| `modules/student-lifecycle/web-portal-cms` | Praveen | Shivani | frontend merged |
| `modules/support/amc-vendor-support` | Madhumita | Tejaswini | sprint v1.0 |
| `modules/support/helpdesk` | Madhumita | Tejaswini | backend merged |
| `modules/support/incident-management` | Madhumita | Tejaswini | sprint v1.0 |
| `modules/support/knowledge-base` | Madhumita | Tejaswini | sprint v1.0 |
| `modules/support/sla-management` | Madhumita | Tejaswini | sprint v1.0 |
| `integrations/README.md` | Himanshu | Faizan, Akshata | sprint v1.0 |
| `integrations/digilocker` | Himanshu | Faizan, Akshata | after launch |
| `integrations/external-university-portals` | Himanshu | Faizan, Akshata | after launch |
| `integrations/government-portals` | Himanshu | Faizan, Akshata | after launch |
| `integrations/messaging-providers` | Himanshu | Faizan, Akshata | sprint v1.0 |
| `integrations/nad` | Himanshu | Faizan, Akshata | after launch |
| `integrations/payment-sbiepay` | Gokula Lakshmi | Ashritha, Faizan | adapter merged |
| `integrations/video-conferencing` | Himanshu | Faizan, Akshata | after launch |
| `integrations/wearables` | Himanshu | Faizan, Akshata | after launch |
| `platform/api-gateway` | Faizan | Himanshu, Srujan | sprint v1.0 |
| `platform/audit` | Himanshu | Faizan, Srujan | sprint v1.0 |
| `platform/billing` | Faizan | Himanshu, Srujan | backend merged |
| `platform/documents` | Himanshu | Faizan, Srujan | sprint v1.0 |
| `platform/event-bus` | Himanshu | Faizan, Srujan | sprint v1.0 |
| `platform/identity` | Faizan | Himanshu, Srujan | backend merged |
| `platform/integration-hub` | Himanshu | Faizan, Srujan | sprint v1.0 |
| `platform/notification` | Himanshu | Faizan, Srujan | backend merged |
| `platform/reporting` | Himanshu | Faizan, Srujan | sprint v1.0 |
| `platform/scheduler` | Himanshu | Faizan, Srujan | sprint v1.0 |
| `platform/search` | Himanshu | Faizan, Srujan | after launch |
| `platform/tenancy` | Faizan | Himanshu, Srujan | backend merged |
| `platform/workflow` | Himanshu | Faizan, Srujan | sprint v1.0 |
