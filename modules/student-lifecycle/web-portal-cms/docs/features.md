# Education OS — Product & Features Reference (for the public website)

**Module:** `web-portal-cms` · **Domain:** `student-lifecycle` · **Owner:** Praveen (@praveen-rooman)
**Purpose of this document:** a single, evidence-backed content reference for designing and building
the public Education OS website, and for understanding the M1 public-page and organisation sign-up
experience that `web-portal-cms` owns.

> **How to read the status labels.** Education OS is early. This document separates what the website
> may claim today from what is designed but not yet built. Every significant claim carries a
> repository path. The labels used throughout:
>
> | Label | Meaning |
> |---|---|
> | **Implemented** | Real, working code on disk (and, where noted, covered by tests). |
> | **Partially implemented** | Some real code; the feature is not end-to-end. |
> | **Specified** | Full contracts (`openapi.yaml`, `events.yaml`, `permissions.yaml`) and a PRD exist, but the backend/frontend is scaffold only. |
> | **Scaffold** | Only a manifest/README; contracts are empty placeholders. |
> | **Planned** | Named in architecture/roadmap, no module yet. |
>
> **Do not describe a Specified/Scaffold/Planned capability as available on the live site.** Marketing
> copy for unbuilt modules must be written as "designed to" / "will", not "does".

---

## A. Education OS overview

**What it is.** Education OS is **one configurable higher-education platform** delivered as a
**multi-tenant SaaS**: a single deployment serves many institutions ("organisations"), each of which
registers itself, picks its **academy type**, starts on a free trial, and upgrades for more.
Source of truth: [docs/architecture/ARCHITECTURE.md](../../../../docs/architecture/ARCHITECTURE.md),
[ADR-0005 multi-tenant SaaS](../../../../docs/architecture/adr/0005-multi-tenant-saas.md),
[ADR-0004 institution profiles](../../../../docs/architecture/adr/0004-institution-profiles.md).

**The shape of the product:**

```
platform/ (core)  →  common suites  →  specialized suites  →  academy profile  →  plan  →  organisation
```

- A **core** of shared platform services every deployment needs (identity, gateway, billing, tenancy,
  notification, documents, search, workflow, audit, reporting, scheduler, event bus, integration hub).
- **Common suites** every institution runs (admissions & students, academics, examinations, finance,
  campus life, governance, support, generic facilities, and a cross-field "practice" suite).
- **Specialized suites** for a field (sports is the first; arts, music, design, film, medical, law,
  engineering, management, research and others follow the same foundation).
- An **academy profile** that declares which suites, modules, roles, dashboards and vocabulary are on
  for one kind of institution.

**Target institutions.** Colleges, universities and academies, across 15 institution types defined in
[docs/architecture/institution-types.md](../../../../docs/architecture/institution-types.md): sports,
arts/fine arts, design/fashion, music, dance/performing arts, theatre/drama, film/media/animation,
medical/health sciences, law, engineering/technology, management/business, agriculture/veterinary,
hospitality, teacher education, and research/doctoral.

**Key problems solved (as designed):**
- One system instead of a dozen disconnected tools — admissions, academics, exams, finance, campus
  life, governance and support share identity, data ownership and events.
- **Configured per field, not rebuilt per field.** Fifteen institution types reduce to eight recurring
  patterns (resource booking, specialized inventory, portfolio, selection process, productions/events,
  projects, field training, skill progress), each built once and given field vocabulary by the profile.
- **Self-service onboarding with governed activation** — an institution signs up online, but a platform
  super admin approves its academic package before it goes live.
- **Strict multi-tenant isolation** — every table carries `organisation_id` with PostgreSQL row-level
  security; documents, search indexes, cache keys and event envelopes are organisation-scoped.

**Modular architecture & multi-tenancy.** Each feature lives in its own module
(`modules/<domain>/<module>`) with its own database schema, contracts and tests, isolated even from
other modules in the same domain. Modules talk only through published APIs (via the gateway) and
domain events (via the event bus); they never import each other's code or query each other's tables.
See [docs/architecture/module-standard.md](../../../../docs/architecture/module-standard.md).

**Value proposition (one line, from the architecture docs):**
> "One Education OS platform, configured for the way each institution teaches, trains, manages and
> supports its students."

**Current build reality (13 Oct 2026).** The platform foundation is real and tested; most feature
modules are specified but not yet coded. Specifically, only these carry **real backend code**:
`platform/identity`, `platform/tenancy`, `platform/billing`, `integrations/payment-sbiepay`, and
`modules/facilities/facility-booking` (partial). The web app (`apps/frontend`) has a working sign-up,
sign-in and role-dashboard shell plus a design-stage admin console. Everything else is Specified or
Scaffold. This matters for the website: **it can authentically sell the platform model, the onboarding
flow and the breadth of the roadmap, but it cannot yet claim most individual modules are live.**

---

## B. Product & module catalogue

Education OS groups modules into **domains** (grouping only — no shared code) mapped to **suites** in
the architecture. Below, each domain lists its modules with purpose, capabilities, users, workflows,
relationships and implementation status.

> **Catalogue-wide status note.** Of ~45 feature modules, **one** has substantive backend code
> (`facilities/facility-booking`). The large majority are **Specified** (full contracts + PRD, scaffold
> code). A handful are **Scaffold** (README only). This is consistent across the repo because every
> module was generated from `modules/_template/`. Treat the catalogue as a **product roadmap with
> finished contracts**, not a list of shipping features.

### Product categories for the website

A website-friendly grouping of the domains:

1. **Student Lifecycle** — public site & sign-up, admissions, student records, enrolment.
2. **Teaching & Learning (Academics)** — programmes/curriculum, LMS, examinations, timetable & attendance.
3. **Practice & Experiential Learning** — portfolio, projects, selection, productions, field training, skill progress.
4. **Campus Life** — hostel, library, transport, placements, alumni.
5. **Facilities & Resources** — booking, inventory/equipment, assets, maintenance, sports facilities.
6. **Finance & Operations** — fees & accounts, budgets & grants, procurement, HR & payroll, e-office.
7. **Governance & Compliance** — grievance, RTI, IQAC/accreditation, regulatory reports.
8. **Support & Service Management** — helpdesk, incidents, SLAs, knowledge base, AMC/vendor support.
9. **Specialized: Sports** (first field suite) — athlete performance, training & video, nutrition & health, tournaments.

---

### Student Lifecycle (`modules/student-lifecycle/`) — Suite A, common

| Module | Purpose | Status |
|---|---|---|
| **web-portal-cms** | Public website, CMS pages, announcements, and the public organisation **sign-up page**. | Specified (this module) |
| **admissions** | Application intake, screening, offers, acceptance. | Specified |
| **student-information** | The **Person system of record** — the canonical student/people records referenced across modules. | Specified |
| **enrolment-registration** | Enrolling admitted applicants and registering them into programmes/courses each term. | Specified |

- **web-portal-cms** — *detailed in sections D and H.* Owns public CMS pages + announcements and hosts
  the sign-up page; it **composes** billing plans and tenancy registration rather than owning them.
  Contracts: [contracts/openapi.yaml](../contracts/openapi.yaml), [permissions.yaml](../contracts/permissions.yaml).
  Backend is scaffold only; manifest `status: planned` ([module.yaml](../module.yaml)).
- **admissions** — anonymous application flow, explicitly separate from organisation sign-up; publishes
  `admissions.application.accepted` which finance consumes to raise fees (ARCHITECTURE.md example).
- **student-information** — upstream dependency for "almost every module" (owner's note,
  [docs/team/prompts/praveen.md](../../../../docs/team/prompts/praveen.md)); the Person/identity reference data.
- Users across the suite: public visitors, prospective organisations, applicants, admissions staff,
  registrars, student-records staff, and students once enrolled.

### Teaching & Learning — Academics (`modules/academics/`) — Suite B, common

All four are **Specified** (full contracts + PRD, scaffold code). `academic-management` is the
upstream source of truth for the domain.

- **academic-management** — terms/periods, programmes, curriculum versions (publish = immutable),
  course catalogue, offerings + sections, faculty assignments, teaching load. Roles: admin,
  department-head, faculty, viewer. Publishes term/programme/curriculum/course/offering/section/
  faculty-assignment events consumed (by design) by timetable-attendance, examinations, lms,
  enrolment-registration, student-information.
- **lms** — course spaces, materials, assignments + submissions, quizzes + attempts, discussions,
  grade release; uses `platform/documents`. Roles: admin, department-head, instructor, student, viewer.
- **examinations** — exam cycles & sessions, eligibility, hall tickets (issue/withhold/revoke),
  invigilation duties, results (publish/revise), transcripts. Roles: controller, department-head,
  faculty, student, viewer. Consumes (by design) attendance eligibility and fee-dues checks.
- **timetable-attendance** — timetable generation & publishing, scheduled classes, attendance sessions
  & records, exam-eligibility computation. Roles: admin, department-head, faculty, student, viewer,
  exam-eligibility.

### Practice & Experiential Learning (`modules/practice/`) — common

The cross-field suite that expresses the eight generic patterns. Every academy gets it.

- **portfolio** — learner portfolios (artworks, repertoire, showreels, designs, teaching/research
  portfolios). Specified-lite (contracts, no PRD). Roles: learner, reviewer, manager.
- **selection-process** — auditions, casting, squad selection, jury rounds, moot-court teams,
  supervisor allocation. Specified-lite. Roles: panelist, coordinator, org-admin.
- **projects** — projects with milestones, teams, reviews (capstone, film, live business, research,
  artwork). Specified. Roles: coordinator, guide, member, viewer.
- **field-training** — placements: clinical rotations, teaching practice, farm rotations, internships,
  court visits. Specified. Roles: coordinator, supervisor, trainee, viewer.
- **skill-progress** — skill frameworks, rubrics, assessments and progression over time. Specified.
  Roles: admin, evaluator, viewer.
- **productions** — performances, exhibitions, recitals, screenings, hackathons, competitions,
  conferences. **Scaffold** (README only; empty contracts).

### Campus Life (`modules/campus-life/`) — Suite F, common

- **hostel** — room allocation, mess, visitors, discipline, leave/gate-pass, fee linkage. Specified
  (most-developed spec here; contract v0.2.0). Roles: admin, warden, security, resident, student,
  viewer. *(Recent commit history shows active work on hostel gate pass & self-service, PR #212.)*
- **library** — catalogue, circulation, digital library, fines, reservations. Specified. Roles: admin,
  librarian, member, viewer.
- **transport** — routes, vehicles, passes, driver management, trip tracking. Specified. Roles: admin,
  driver, rider, viewer.
- **placement-career** — placement drives, companies, applications, offers, career services.
  **Scaffold**.
- **alumni** — alumni directory, events, donations, engagement campaigns. **Scaffold**.

### Facilities & Resources (`modules/facilities/`) — Suite D, mostly common

- **facility-booking** — **the one partially-implemented feature module.** Generic resource-booking
  pattern: bookable resources, availability/blackouts, bookings with optional approval, check-in/no-show,
  completion; field vocabulary from the profile (rooms, studios, labs, pitches, kitchens, equipment).
  **Partially implemented** — real backend (`backend/src/eos_facility_booking/`, ~2,000 LoC, with tests
  and an Alembic migration); frontend still a stub. Roles: user, approver, manager. The reference
  implementation of the module standard.
- **inventory-equipment** — generic inventory pattern: catalogue, units, store locations, stock ledger,
  low-stock, loans. Specified.
- **asset-management** — fixed-asset register: tagging, transfers, physical verification, depreciation,
  disposal. Specified.
- **maintenance** — fault tickets & work orders for assets/spaces/equipment; technician/vendor
  assignment, SLA, preventive schedules. Specified.
- **sports-facilities** — registry of grounds, courts, pools, gyms and usage (specialized, field=sports).
  Specified.

### Finance & Operations (`modules/finance-operations/`) — Suite E, common

All **Specified**.

- **fees-accounts** — fee structures, invoices, online payments, receipts, ledgers, concessions/refunds.
  Consumes `admissions.application.accepted`; upstream for examinations dues checks. Roles include
  applicant, student, finance-staff, management, org-admin.
- **budget-grants** — budget planning, grant tracking, utilisation certificates.
- **procurement** — indents, tenders, purchase orders, goods receipt, vendor management.
- **hr-payroll** — employee master, leave, payroll runs, appraisals, service records.
- **e-office** — file movement, notings, approvals, digital correspondence/dispatch.

### Governance & Compliance (`modules/governance/`) — Suite G, common

All **Specified** (rich PRDs, thin event surfaces).

- **grievance** — SGRC, anti-ragging and POSH/ICC complaint intake & resolution.
- **rti** — RTI request intake, assignment, tracking, responses.
- **iqac-accreditation** — IQAC data collection, NAAC/NBA metrics, evidence repository.
- **regulatory-reports** — UGC, AISHE, NIRF and other statutory reporting.

### Support & Service Management (`modules/support/`) — Global, common

A cohesive ITSM-style cluster, all **Specified**.

- **helpdesk** — ticketing with categories & routing for every role.
- **incident-management** — incident & problem records, RCA.
- **sla-management** — SLA definitions, timers, escalation and breach tracking (the richest event
  surface: a clock state machine).
- **knowledge-base** — articles, FAQs, how-to guides for self-service.
- **amc-vendor-support** — AMC contracts, vendor-support engagements, renewals.

### Specialized: Sports (`modules/sports/`) — Suite C, specialized (field: sports)

The first field suite. All four are **Specified** (large, detailed OpenAPI specs; scaffold code).
Enabled by the `sports` specialization in the `sports-college` profile.

- **athlete-performance** — athlete profiles, performance metrics, fitness testing, benchmarks, medical
  clearance. (Largest single spec.) Vocabulary maps its subject to "Athlete".
- **training-video-analysis** — training plans & sessions, video upload, tagging and annotation.
- **sports-nutrition-health** — diet plans, medical records, injury tracking, physio sessions.
- **tournament-events** — tournaments, fixtures, results, officials, event logistics.

---

## C. Platform capabilities (shared services)

Shared services live in `platform/*`. **Four are implemented** (identity, tenancy, billing, and the
payment adapter in `integrations/`); the rest are **Specified** (contracts, sometimes PRDs, scaffold
code). Shared runtime logic (settings, DB base with `organisation_id`, tenant context, RLS, JWT, the
entitlement rule, the event/outbox publisher, the email stub) lives in `packages/core` (`eos_core`).

### Organisation & tenant management — **Implemented** (`platform/tenancy`)

- Self-service **organisation registration** with academy type, slug, country, admin details.
- Lifecycle: `pending_verification → pending_approval → active → suspended → archived`
  ([domain/models.py](../../../../platform/tenancy/backend/src/eos_tenancy/domain/models.py)).
- Email verification via a 48-hour registration token.
- **Academic package** = the academy type (profile); changes require super-admin approval.
- Per-organisation **module toggles** and super-admin **entitlement overrides**.
- Super-admin operations: list/inspect organisations, approve, change status, set overrides, audited
  **impersonation** (60-minute token).
- The single table that is *not* tenant-scoped (it defines the tenants).

### Authentication, identity, roles & permissions — **Implemented (partial scope)** (`platform/identity`)

- **Implemented:** password login + JWT (`POST /auth/login`), `GET /auth/me` with resolved permissions,
  user listing/creation, config-driven **RBAC** (`<module>:<resource>:<action>` keys), a seeded platform
  **super admin**, and the rule that **login is refused until the organisation is `active`** — the tie
  between tenancy approval and sign-in ([router.py](../../../../platform/identity/backend/src/eos_identity/api/router.py)).
- **Specified/aspirational (manifest claims, not in code yet):** SSO (SAML/OAuth2/OIDC) and MFA. The
  website should not claim SSO/MFA as available today.
- **Roles & dashboards are data, not code:** 15 academy **profiles**
  ([platform/identity/config/profiles/](../../../../platform/identity/config/profiles/)) and ~55 **role
  dashboard layouts** ([config/dashboards/](../../../../platform/identity/config/dashboards/)). Only
  `org-admin` and `super-admin` are fixed in `packages/contracts`.

### Configurable dashboards & widgets — **Implemented (shell)**

- One dashboard page renders any role's layout from YAML; widgets are module code that declare the
  permission key they need. Widget contract in `packages/ui-kit`; the shell shows a "Not built yet" card
  for widget ids whose module isn't built. Working in `apps/frontend/src/dashboard/`.

### Module activation & entitlements — **Implemented** (`platform/tenancy` + `eos_core.entitlement`)

- Effective entitlement = `profile.modules ∩ plan.modules ∪ overrides − disabled`, evaluated per
  request. Toggling a module not in the plan returns **402 "upgrade to unlock"**.

### Billing, packages & subscriptions — **Implemented** (`platform/billing`)

- Plan catalogue (seeded from [config/plans.yaml](../../../../platform/billing/config/plans.yaml), editable
  at runtime by the super admin), per-organisation subscriptions, trial start, upgrade, cancel, payment
  webhook, trial expiry. Public `GET /plans`. *Detail and pricing in section H and the pricing guidance below.*

### Notifications — **Specified; email delivery STUBBED**

- Rich contract for email/SMS/WhatsApp/push/in-app with templates and preferences
  (`platform/notification/contracts/`), but **no backend code**. All current email goes through the
  **stub** [`eos_core.notify.send_email`](../../../../packages/core/src/eos_core/notify.py), which logs
  and keeps messages in memory — **nothing is actually delivered**. In dev mode the verification token is
  returned in the registration response instead. *This is the single most important gap for the sign-up
  flow's "approval email" and "verification email".*

### Audit, workflow, documents, search, reporting, scheduler, gateway, event bus — **Specified**

- **audit** — immutable append-only log for every state change (contracts + PRD; a test fake exists).
- **workflow** — configurable approval/state-machine engine (contracts only).
- **documents** — storage abstraction, versioning, access control (contracts only).
- **search** — global indexing/query (contracts only).
- **reporting** — dashboards, MIS reports, warehouse ETL (contracts only).
- **scheduler** — cron/jobs/reminders (contracts + PRD; a test fake exists; billing's trial-expiry job is
  meant to run here).
- **api-gateway** — edge routing, auth enforcement, per-request entitlement, rate limiting (contracts only;
  the entitlement rule itself lives in `eos_core` and runs inside `apps/backend`).
- **event-bus** — event contracts + broker abstraction; live services currently publish via
  `eos_core.events.publish` (outbox pattern) rather than a running broker.

### Integrations — one implemented, rest specified/scaffold (`integrations/`)

- **payment-sbiepay** — **Implemented** SBIePay gateway adapter (initiate/callback/reconcile/refunds),
  with its own tests. This is the adapter billing's upgrade flow targets when a payment adapter is
  configured.
- **messaging-providers** — **Specified** email/SMS/WhatsApp provider adapters (the intended physical
  sender behind `platform/notification`).
- **digilocker, nad, government-portals, video-conferencing, wearables, external-university-portals** —
  **Scaffold**.

---

## D. Student lifecycle (the journey)

The intended student journey spans the `student-lifecycle` and related suites. **Note the distinction
the website must respect:** *organisation* sign-up (an academy becoming a customer) is entirely separate
from a *student* joining an institution.

| Stage | Module(s) | Status | Notes |
|---|---|---|---|
| Public presence & discovery | web-portal-cms | Specified | CMS pages, announcements, pricing/sign-up landing. |
| **Organisation onboarding** | tenancy + billing + identity | **Implemented** | The academy signs up — *not* a student. See section H. |
| Admission application | admissions | Specified | Anonymous application; no Person record yet. |
| Selection (field-specific) | practice/selection-process | Specified-lite | Auditions, squad selection, casting, supervisor allocation. |
| Enrolment & registration | enrolment-registration | Specified | Admitted applicants become enrolled students, registered per term. |
| Student information (SoR) | student-information | Specified | The canonical Person record, created by staff — never by public sign-up. |
| Learning & assessment | academics (lms, examinations, timetable-attendance) | Specified | Day-to-day academic life. |
| Practice & portfolio | practice/* | Specified / Specified-lite | Projects, field training, skill progress, portfolios. |
| Campus services | campus-life/* | Specified / Scaffold | Hostel, library, transport, placements, alumni. |

**How the stages connect (by design):** modules integrate through **events**, not shared tables — e.g.
`admissions.application.accepted` → `fees-accounts` raises an invoice (ARCHITECTURE.md). **Actual vs
intended:** today only the onboarding stage (tenancy↔billing↔identity) is wired in code; the rest are
**intended integrations** declared in each module's `events.yaml` `consumers:` lists, with
`consumes_events: []` still empty in every manifest (subscriptions not yet confirmed).

---

## E. User roles

Roles are **compositions of module permissions**, defined as data in academy profiles and dashboard
layouts — not hard-coded (except `org-admin` and `super-admin`). Each academy adds its own learner,
instructor and field-staff roles on top of the common roles.

**Platform / cross-cutting roles:**

| Role | Responsibilities | Dashboard | Status |
|---|---|---|---|
| **Super admin** | Platform operator outside every organisation: approves academic packages & organisations, manages plans/subscriptions/overrides, audited impersonation. | `super-admin.yaml` | Backend endpoints **Implemented**; a wired approval-queue **UI is not built** (approval currently via API). |
| **Organisation admin** (`org-admin`) | Users, roles, settings and subscription of one organisation; full control of its public site. | `org-admin.yaml` | **Implemented** (created at registration; real dashboard). |

**Common organisation roles** (every academy): applicant, student, faculty, examination staff,
department admin, finance staff, HR staff, facilities staff, governance, support staff, management.
Each has a dashboard layout file under `config/dashboards/`. These are **Specified** (layouts exist;
most underlying module widgets aren't built, so the shell shows "Not built yet" cards).

**Per-academy learner / instructor / field-staff roles** (examples, from institution-types.md):

| Academy | Learner | Instructor | Field staff |
|---|---|---|---|
| Sports college | Athlete | Coach | Medical staff, Nutritionist |
| Arts academy | Artist | Studio instructor | Exhibition & gallery manager |
| Music academy | Musician | Music teacher | Ensemble / orchestra director |
| Film / media | Filmmaker | Production supervisor | Equipment manager |
| Medical college | Medical student | Clinical supervisor | Hospital coordinator |
| Law college | Law student | Legal mentor | Moot-court coordinator |
| Engineering college | Engineering student | Project guide | Lab in-charge |
| Management institute | Management student | Corporate mentor | Placement officer |

> ~55 role dashboard layouts exist in [config/dashboards/](../../../../platform/identity/config/dashboards/).
> **Do not claim any of these role dashboards is fully functional** beyond org-admin/super-admin and the
> generic shell — the widgets that fill them depend on modules that are mostly unbuilt.

---

## F. Specialized education solutions

Education OS serves 15 institution types from one platform. **How it works:** every academy runs the
core + common suites; field needs are met first by the **eight generic patterns** (built once in the
`practice`/`facilities` suites, given field vocabulary by the profile), and only genuinely
field-specific behaviour becomes a specialized module.

**The eight patterns** (from institution-types.md):

| Pattern | Common module | Appears as |
|---|---|---|
| Resource booking | facilities/facility-booking | practice rooms, studios, labs, pitches, kitchens, venues |
| Specialized inventory | facilities/inventory-equipment | instruments, costumes, lab gear, art materials, sports kit |
| Portfolio | practice/portfolio | artist portfolio, design collection, showreel, publications |
| Selection process | practice/selection-process | auditions, casting, squad selection, moot-court teams |
| Productions & events | practice/productions | performances, exhibitions, recitals, screenings, hackathons |
| Projects | practice/projects | capstone, film, live business, research, artwork |
| Field training | practice/field-training | clinical rotations, teaching practice, internships, court visits |
| Skill progress | practice/skill-progress | technique grades, practicum assessment, competencies |

**Existing vs planned:**

- **Sports** (first field suite) — four specialized modules exist as **Specified** contracts
  (athlete-performance, training-video-analysis, sports-nutrition-health, tournament-events); the
  `sports-college` profile is the reference/first-customer configuration. *Not yet coded.*
- **Arts, design/fashion, music, dance, theatre, film/media, medical, law, engineering, management,
  agriculture, hospitality, teacher education, research** — all have **profiles** (academy types) and
  **role dashboard layouts** defined; their field needs are expressed through the generic patterns.
  **Planned/Specified**, delivered by configuration rather than by 15 separate codebases.
- **What stays specialized** (a pattern cannot carry it): injury & physio records, hospital integration,
  scripts & rights, thesis & viva, wearables.

> **Website framing:** present the full 15-field breadth as "the platform is designed to configure for
> your field," with sports as the lead example. Do not present field modules (including sports) as
> shipping features yet.

---

## G. Website-ready content

Professional, honest content for the public site. (No invented testimonials, statistics,
certifications, contacts or policies — see sections I and J for what still needs confirmation.)

### Product positioning & value proposition

> **One platform for the whole institution — configured for the way your field teaches, trains,
> manages and supports its students.**

Education OS unifies admissions, academics, examinations, finance, campus life, governance and support
on a single multi-tenant platform. You sign up online, choose your academy type, and get a workspace
shaped for your institution — with role-based dashboards for everyone from applicants to the registrar.

### Homepage hero

- **Headline:** "The operating system for modern institutions."
- **Sub-headline:** "Admissions to alumni, studios to stadiums — one configurable platform for colleges
  and academies. Start a free trial, pick your academy type, and go live after a quick approval."
- **Primary CTA:** *Start free trial* → sign-up. **Secondary CTA:** *Explore the platform* / *See how it works*.

### Main product pillars (feature-card set)

1. **Configured for your field** — 15 academy types from one platform; your suites, roles and
   vocabulary, not a generic ERP.
2. **One record, every stage** — a shared student lifecycle from application to alumni, connected by
   events, not spreadsheets.
3. **Role-based dashboards** — every person sees the widgets for their job; ~55 role layouts, driven by
   configuration.
4. **Multi-tenant & secure by design** — strict per-organisation isolation with row-level security,
   audit trails, and governed activation.
5. **Modular & extensible** — add suites as you grow; specialized suites for sports, arts, medical, law,
   engineering and more.
6. **Transparent plans** — start free for 30 days, upgrade when you need more.

### Feature categories (concise cards)

- **Admissions & Enrolment** — applications, offers, enrolment, registration.
- **Academics & LMS** — programmes, curriculum, courses, learning content, assignments, quizzes.
- **Examinations** — cycles, hall tickets, invigilation, results, transcripts.
- **Timetable & Attendance** — scheduling, attendance capture, exam-eligibility.
- **Practice & Portfolio** — projects, field training, skill progress, portfolios, selection.
- **Campus Life** — hostel, library, transport, placements, alumni.
- **Facilities** — bookable resources, inventory & equipment, assets, maintenance.
- **Finance & Operations** — fees & payments, budgets & grants, procurement, HR & payroll, e-office.
- **Governance & Compliance** — grievance, RTI, IQAC/accreditation, statutory reports.
- **Support** — helpdesk, incidents, SLAs, knowledge base, vendor contracts.
- **Sports suite** — athlete performance, training & video analysis, nutrition & health, tournaments.

> Each card's copy must be written in the "designed to" voice for Specified modules; only the platform,
> onboarding, dashboards and facility-booking can use present-tense "does".

### Benefits by audience

- **Institutions / leadership:** one system of record; configure per field instead of buying ten tools;
  governed onboarding; clear plans and limits.
- **Administrators (org-admin):** manage users, roles, settings and subscription from one console;
  entitlements make it obvious what's unlocked and what an upgrade adds.
- **Faculty / instructors:** teaching-oriented dashboards; attendance, assessments, content and results
  in one place (as modules ship).
- **Students / learners:** a single portal for applications, courses, results, campus services and
  (per field) portfolios, projects and practice.

### Platform differentiators (architecture-backed)

- **Profiles, not forks** — 15 institution types from one codebase (ADR-0004).
- **Entitlement engine** — what's on = profile ∩ plan ∪ overrides, enforced per request.
- **Isolation by construction** — `organisation_id` + row-level security on every table; a cross-tenant
  leak test ships in `packages/testing`.
- **Events over joins** — modules integrate by domain events, keeping each independently deployable.
- **One dashboard, many roles** — layouts are data; the shell renders any role.
- **Deployment flexibility** — the same modules run as a multi-tenant monolith, grouped services, or a
  dedicated single-tenant instance, without code changes.

### Suggested homepage section order

1. Hero + primary CTA → 2. Product pillars → 3. "Built for your field" (academy-type selector) →
4. Lifecycle walkthrough (application → alumni) → 5. Platform/trust (security, multi-tenancy, audit) →
6. Plans & pricing → 7. How onboarding works (sign-up → verify → approval → sign-in) →
8. FAQ → 9. Final CTA.

### Suggested navigation

- **Product** (suites/modules) · **Solutions** (by academy type) · **Platform** (security, architecture,
  integrations) · **Pricing** · **Resources** (docs, FAQ) · **Sign in** · **Start free trial**.

### Suggested "Solutions" (by academy type) sections

One page/section per academy type, each explaining the field's needs mapped to the generic patterns,
with **Sports** as the flagship. Keep all in "designed for" voice until the field modules ship.

### FAQ topics (answerable from verified behaviour)

- *Is it one platform for different kinds of institutions?* Yes — you choose an academy type at sign-up.
- *How does sign-up work?* Register your organisation → verify your email → a platform admin approves
  your academic package → sign in. (See section H.)
- *Is there a free trial?* Yes — a 30-day trial plan (0 cost) with limits; upgrade for more.
- *What does a plan control?* Which suites/modules/integrations and usage limits (users, students,
  storage) your organisation gets.
- *How is my data kept separate from other institutions?* Every record is organisation-scoped with
  database row-level security.
- *Can an admin control who sees what?* Yes — role-based permissions and per-organisation module toggles.
- *(Avoid, until built:)* questions implying SSO/MFA, real email delivery, or that specific field modules
  are live.

### Calls to action

- Primary: **Start free trial** (sign-up). Secondary: **See plans**, **Explore the platform**,
  **Talk to us** *(only once a real contact channel exists — see section J)*.

### Pricing & package content guidance (from actual Billing config)

Source of truth: [platform/billing/config/plans.yaml](../../../../platform/billing/config/plans.yaml)
(seed/default; the super admin can edit plans at runtime, so treat figures as the current default, not a
published commitment — confirm before publishing).

| Plan | Price | Trial | What's included (suites) | Specialized suites | Integrations | Limits | After trial |
|---|---|---|---|---|---|---|---|
| **Trial** | ₹0 (INR), 30 days | 30 days | student-lifecycle, academics, practice, support | 1 of the profile's | messaging-providers | 25 users · 500 students · 2 GB | read-only |
| **Standard** | ₹24,999 / month (INR) | — | every common suite | all | messaging, payments, video, DigiLocker | 500 users · 10,000 students · 100 GB | — |
| **Premium** | ₹59,999 / month (INR) | — | everything | all | all integrations | 5,000 users · 100,000 students · 1,000 GB · priority support | — |

Pricing-page copy guidance: lead with the free 30-day trial; show the three tiers; explain that a plan
unlocks suites/modules/integrations and sets usage limits; note upgrades apply immediately on payment.
**Flag for confirmation:** currency presentation, GST/taxes, annual pricing, and whether these seed
numbers are the published prices (section J).

---

## H. Public pages and organisation sign-up flow (the M1 task)

This is the experience `web-portal-cms` is responsible for presenting. The business logic is **owned by
platform services** — web-portal-cms composes them client-side and never re-implements registration or
plans (PRD §3, [docs/prd.md](./prd.md)).

**Service ownership (respect these boundaries):**
- **Billing** owns plans & subscriptions. · **Tenancy** owns organisation registration, verification &
  approval lifecycle. · **Identity** owns authentication/login. · **Notification** owns email delivery
  (stubbed today). · **Web Portal CMS** owns the public website experience and content.

**Overall status:** the onboarding journey **works end-to-end against the real API** and is covered by a
Playwright E2E test ([tests/e2e/onboarding/register-approve-signin.spec.ts](../../../../tests/e2e/onboarding/register-approve-signin.spec.ts):
"register, approve, sign in, dashboard"). **But** it is implemented in the generic web app
[apps/frontend/src/auth/SignUp.tsx](../../../../apps/frontend/src/auth/SignUp.tsx), **not** in
web-portal-cms (which is scaffold), and it differs from the PRD in two important ways (no plan picker;
pasted token instead of emailed link). Details per step:

### 1. Public landing page & product overview
- **Purpose/UX:** marketing content + entry to sign-up. **Owner:** web-portal-cms (CMS pages, `scope=public`).
- **Status:** **Specified, not built.** web-portal-cms has no frontend code; there is no public
  marketing site yet. The current app opens directly on a sign-in/sign-up form, not a CMS landing page.

### 2. Academy / institution-type selection
- **Purpose/UX:** the prospect picks their academy type (the "academic package"). **Owner:** Tenancy
  (`GET /academy-types`, public) rendering web-portal-cms content around it.
- **Status:** **Implemented** in the sign-up form — a dropdown populated from `/tenancy/academy-types`
  with the chosen type's description (SignUp.tsx). All 15 profiles are selectable.

### 3. Academy package picker using real Billing data
- **Purpose/UX (as specified):** show the plans from Billing's `GET /plans` so the prospect can choose
  before committing (PRD §4.4, user-stories.md). **Owner:** Billing (`GET /plans`, public).
- **Status:** **GAP — specified but not built into sign-up.** `GET /plans` is **Implemented** and public
  ([billing router](../../../../platform/billing/backend/src/eos_billing/api/router.py)), but the current
  SignUp form does **not** call it or show a plan picker — registration **always starts on the trial
  plan** (tenancy `/register` "creates it on the trial plan"), and the plan is chosen/upgraded later
  **inside the app** (the dashboard's plan control → `billing.subscription.upgrade`). *Building the
  plan/package picker on the public sign-up page is the clearest open piece of the M1 task.*
  > Terminology note: "academic package" in this architecture = the **academy type** (approved by the
  > super admin), which is distinct from the **billing plan** (trial/standard/premium) that controls how
  > much is unlocked. The sign-up page conflates them in the task wording; keep them separate in the UI.

### 4. Organisation & administrator registration (existing tenancy service)
- **Purpose/UX:** one submission creates the organisation **and** its Organisation Admin account.
  **Owner:** Tenancy `POST /register` (public, `security: []`).
- **Status:** **Implemented.** `POST /tenancy/register` validates slug (3–40 chars, reserved words
  blocked, uniqueness), requires accepted terms, creates the org (`pending_verification`), creates the
  `org-admin` user via identity, starts the trial via billing, issues a 48h token, emits
  `tenancy.organisation.registered`
  ([tenancy service.py](../../../../platform/tenancy/backend/src/eos_tenancy/application/service.py)).

### 5. Email verification
- **Purpose/UX:** confirm the admin email; organisation moves to `pending_approval`. **Owner:** Tenancy
  `POST /register/verify` (public); **email delivery** is Notification's job.
- **Status:** **Mechanically Implemented, delivery STUBBED.** Verification works (token generated,
  stored, verifiable; org → `pending_approval` unless `TENANCY_AUTO_APPROVE=true`). **No real email is
  sent** — `eos_core.notify` only logs/stores it; in dev mode the token is returned in the register
  response and the UI pre-fills it. The current UI asks the user to **paste a token**, not click an
  emailed link (SignUp.tsx; E2E test confirms). *A real emailed verification link depends on
  `platform/notification` + `messaging-providers`, both unbuilt.*

### 6. Awaiting-approval & next-steps page
- **Purpose/UX:** after verification, tell the user they're waiting for platform approval and what
  happens next. **Owner:** web-portal-cms (static/CMS content) within the app flow.
- **Status:** **Implemented (basic).** SignUp.tsx shows an "Email verified … waiting for the platform
  administrator to approve its academic package … you'll get an email when approved" screen. It is a
  minimal in-app card, not a CMS-authored next-steps page.

### 7. Super Admin approval (existing platform workflow)
- **Purpose/UX:** a platform super admin approves the academic package; the org becomes `active`.
  **Owner:** Tenancy `POST /admin/organisations/{id}/approve` (perm `platform:organisations:manage`).
- **Status:** **Backend Implemented; approval-queue UI not built.** The endpoint works and is exercised
  by the E2E test via the API. The architecture's intended super-admin screens in `apps/frontend` are
  **not** functional for approvals — the admin console at
  [apps/frontend/src/admin](../../../../apps/frontend/src/admin) is a **design-stage** console (real
  identity sign-in, but module screens show sample data; its README says so), and the E2E test notes
  approval "goes through the API until the super admin approval queue exists in apps/frontend." Default
  `TENANCY_AUTO_APPROVE=false` means approval is required.

### 8. Approval email & next steps for the org admin
- **Purpose/UX:** email the admin that the org is approved and they can sign in. **Owner:** Notification.
- **Status:** **STUBBED / effectively missing.** On approval, tenancy emits
  `tenancy.organisation.approved`/`.activated`, but there is no notification consumer and **no real email
  is sent**. The website FAQ should describe this step as "you'll be notified," pending real email.

### 9. Login handoff to the existing identity service
- **Purpose/UX:** the org admin signs in and lands on their dashboard. **Owner:** Identity `POST /auth/login`.
- **Status:** **Implemented.** Login returns a JWT and **succeeds only once the organisation is
  `active`** — attempting to sign in while `pending_approval` returns a clear "waiting for platform
  approval" message (identity service + admin `signInError` copy). The org admin then lands on the
  `org-admin` dashboard.

**End-to-end flow (verified in code/tests):**

```
Sign-up form (apps/frontend)
  → GET /tenancy/academy-types            (public, Implemented)
  → [spec: GET /billing/plans picker]     (public endpoint Implemented; picker NOT built)
  → POST /tenancy/register                (public, Implemented) → org pending_verification,
                                            org-admin created, trial started, token issued, email STUBBED
  → POST /tenancy/register/verify {token} (public, Implemented) → org pending_approval
  → [await super-admin approval]          (POST /tenancy/admin/.../approve — backend Implemented, UI not built)
  → POST /identity/auth/login             (Implemented) → succeeds only when org is active → dashboard
```

---

## I. Evidence & implementation status

**Implemented (real code; ★ = has tests):**
- `platform/identity` ★ — login, JWT, RBAC, super-admin seed, org-active login gate.
  [backend/src/eos_identity/](../../../../platform/identity/backend/src/eos_identity/)
- `platform/tenancy` — registration, verification, approval lifecycle, entitlements, overrides,
  impersonation. [backend/src/eos_tenancy/](../../../../platform/tenancy/backend/src/eos_tenancy/)
- `platform/billing` — plans, trial, upgrade, cancel, payment webhook, trial expiry.
  [backend/src/eos_billing/](../../../../platform/billing/backend/src/eos_billing/),
  [config/plans.yaml](../../../../platform/billing/config/plans.yaml)
- `integrations/payment-sbiepay` ★ — SBIePay adapter.
- `apps/frontend` — sign-up, sign-in, role-dashboard shell, entitlement, preview mode; design-stage
  admin console. [src/](../../../../apps/frontend/src/)
- `apps/backend` — FastAPI host with the entitlement gate (foundation tests pass on SQLite & Postgres).
- `packages/core` (`eos_core`), `packages/ui-kit`, `packages/contracts`, `packages/testing` (incl. the
  cross-tenant leak test).
- `tests/e2e/onboarding/register-approve-signin.spec.ts` — the onboarding journey.

**Partially implemented:**
- `modules/facilities/facility-booking` — real backend + migration + tests; frontend stub.

**Specified (full contracts + PRD, scaffold code):**
- All `academics/*`; `campus-life/{hostel,library,transport}`; `facilities/{inventory-equipment,
  asset-management,maintenance,sports-facilities}`; all `finance-operations/*`; all `governance/*`;
  `practice/{projects,field-training,skill-progress}`; all `support/*`; all `sports/*`;
  `student-lifecycle/{web-portal-cms,admissions,student-information,enrolment-registration}`;
  `platform/notification` (rich contract); `integrations/messaging-providers`.
- Specified-lite (contracts, no PRD): `practice/{portfolio,selection-process}`.

**Specified, platform services (contracts only, scaffold code):**
- `platform/{api-gateway,audit,documents,event-bus,integration-hub,reporting,scheduler,search,workflow}`.

**Scaffold (README only, empty contracts):**
- `campus-life/{alumni,placement-career}`, `practice/productions`,
  `integrations/{digilocker,nad,government-portals,video-conferencing,wearables,external-university-portals}`.

**Aspirational (claimed in a manifest but not in code):**
- Identity SSO (SAML/OAuth2/OIDC) and MFA — manifest lists them; code implements password + JWT only.

**Billing contract vs code:** `GET /invoices` and `GET /admin/revenue` appear in billing's OpenAPI but
have no implementation yet (Specified within an otherwise-Implemented service).

---

## J. Website content gaps (confirm before publishing)

1. **Pricing is seed data, not a committed price list.** `plans.yaml` figures (₹0 / ₹24,999 / ₹59,999
   INR) are defaults the super admin can edit at runtime. Confirm published prices, currency
   presentation, taxes/GST, and whether annual billing exists.
2. **Real email delivery.** Verification and approval emails are **stubbed** — do not promise "check your
   inbox" until `platform/notification` + `messaging-providers` are built and wired.
3. **Plan/package picker on sign-up** is specified but **not built**; today sign-up starts on trial and
   plan is chosen in-app. Decide whether the public page should present plans before building copy that
   implies it.
4. **Super-admin approval UI** is not built (approval is API-only today). Describe the approval wait
   carefully.
5. **Public marketing/CMS site** doesn't exist yet (web-portal-cms is scaffold); there is no landing
   page, no CMS-authored content, no terms-of-service page in place.
6. **Feature availability claims.** Most modules are Specified; copy must use "designed to"/"will" voice
   for anything beyond the platform foundation, onboarding, dashboards shell, and facility-booking.
7. **SSO/MFA** must not be advertised as available.
8. **Brand, legal & contact:** approved logos/branding, company/legal entity, contact channels, privacy
   policy, terms of service, refund/cancellation policy, and any certifications/compliance claims
   (NAAC/UGC/data-protection) are **not** in the repository — obtain from the business before publishing.
9. **No testimonials, customer names, logos, uptime/adoption statistics, or awards** exist in the repo;
   do not invent them.
10. **Institution/customer examples:** `sports-college` is the reference *profile*, not a named customer.

---

### Primary repository sources inspected

Architecture: `docs/architecture/ARCHITECTURE.md`, `institution-types.md`, `module-standard.md`,
`approved-stack.yaml`, `adr/0004`, `adr/0005`. Platform (code): `platform/tenancy`, `platform/billing`
(+`config/plans.yaml`), `platform/identity` (+`config/profiles/`, `config/dashboards/`),
`packages/core/eos_core/notify.py`, `settings.py`. Integrations: `integrations/payment-sbiepay`,
`messaging-providers`. Frontend: `apps/frontend/src/{App.tsx,auth/SignUp.tsx,api/client.ts,admin/*}`.
This module: `modules/student-lifecycle/web-portal-cms/{module.yaml,docs/*,contracts/*}`. Tests:
`tests/e2e/onboarding/register-approve-signin.spec.ts`. Full module catalogue across `modules/*` and
`platform/*` and `integrations/*`.
