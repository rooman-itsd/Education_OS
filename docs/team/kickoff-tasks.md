# Kickoff tasks, by person

> Superseded on 29 Oct 2026 by the v1.0 sprint: [sprint-v1.0.md](sprint-v1.0.md) has every person's batches, dates and reviewer. This page stays as the record of weeks 1 and 2.

Kickoff 7 Oct 2026. Week 1 is 7 to 10 Oct. Your tasks are GitHub issues on the board
(https://github.com/users/faizanrooman/projects/1): one "Week 1: <name>" issue and your dashboards. Everyone's week 1 ends with `docs/prd.md` and reviewed
`contracts/*.yaml` for every module they own. Code starts in week 2. The live tracker with tick
boxes is the "Kickoff tasks" tab of the Dashboard Assignment Plan doc; this file is the copy next
to the code. Module standard: [docs/architecture/module-standard.md](../architecture/module-standard.md).
Starter prompt for your Claude Code chat: [prompts/](prompts/).

| Name | Area | Week 1 | Then |
|---|---|---|---|
| Faizan | Architecture & platform lead: identity, api-gateway, tenancy, billing, packages | CODEOWNERS handles; review every contract; Alembic chains with RLS for identity, tenancy, billing; permission check from the role catalogue in every platform router; ADR-0006 OIDC provider; pair with Srujan on API deploy | Organisation Admin dashboard; package change screen; research university dashboards |
| Himanshu | Platform services & integrations: event-bus, notification, documents, workflow, audit, search, scheduler, reporting, integration-hub, productions, 7 adapters | Contracts for notification, audit, scheduler, event-bus; messaging-providers adapter (email first); outbox relay design; audit contract | notification backend (verification, approval, trial mails); audit; scheduler trial expiry and reminders; event relay; workflow, reporting; Department Admin dashboard; productions; theatre dashboards |
| Praveen | Student lifecycle: web-portal-cms, admissions, student-information, enrolment-registration, portfolio, selection-process | Contracts for admissions, student-information (Person system of record), web-portal-cms incl. sign-up page; portfolio and selection-process as generic patterns | student-information first, then admissions, enrolment; Applicant dashboard; portfolio and selection backends; arts dashboards |
| Shivani | Academics: academic-management, lms, examinations, timetable-attendance | Contracts for all four; agree the events Student, Exam Staff and Department Admin consume; review Akshata's exam widget list | academic-management and timetable first, then examinations, lms; Faculty dashboard; teacher education dashboards |
| Akshata | Sports: athlete-performance, training-video-analysis, sports-nutrition-health, tournament-events, sports-facilities, skill-progress | Contracts for the sports modules; skill-progress as a generic pattern; split exam widgets with Shivani | Examination Staff dashboard; sports backends; Athlete, Coach, Medical Staff dashboards; skill-progress |
| Ashritha | Facilities: facility-booking, inventory-equipment, asset-management, maintenance | facility-booking as the generic resource-booking pattern; inventory-equipment as the generic inventory pattern; maintenance and asset contracts | facility-booking backend (27 dashboards), inventory; Facility staff dashboard; music academy dashboards |
| Gokula Lakshmi | Finance & operations: fees-accounts, budget-grants, procurement, hr-payroll, e-office, payment-sbiepay | payment-sbiepay adapter contract (billing upgrade and fee payment); fees-accounts contract; hr-payroll, budget, procurement, e-office contracts | payment adapter wired to billing webhook; fees-accounts backend and widgets; Finance Staff dashboard; HR Staff from the pool; management institute dashboards |
| Tejaswini | Campus life: hostel, transport, library, placement-career, alumni, field-training, projects | Contracts for hostel, transport, library; field-training and projects as generic patterns; agree Student widgets with Shivani and Gokula Lakshmi | Student dashboard; field-training and projects backends (35 dashboards); medical college dashboards |
| Madhumita | Governance & support: grievance, rti, iqac-accreditation, regulatory-reports, helpdesk, sla-management, knowledge-base, incident-management, amc-vendor-support | Contracts for helpdesk and sla-management; incident, knowledge base, AMC; grievance, RTI, IQAC, regulatory | helpdesk and SLA backends; Support Staff dashboard; Governance from the pool; law college dashboards |
| Srujan | Apps, infra & QA: apps/frontend incl. super admin screens, apps/backend, packages/testing, infra, CI | Deploy the API with Postgres and proxy `/api/` (live site leaves preview mode); nightly backup; CI boundary lint, manifest check, migration check for `organisation_id`; platform stubs in packages/testing; Playwright e2e skeleton | Super admin screens (approval queue first); Super Admin dashboard; engineering college dashboards |

Everyone, every week: one PR touches one module unless it is a contract change plus its consumers;
status updated on merge; a blocked contract is raised at standup and the module owner's review
comes first.
