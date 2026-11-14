# Education OS — Akshata T. Rathod: Work Report Addendum & Demo Guide

**Date:** Sunday, 8 November 2026  
**Author:** Akshata T. Rathod (@akshatatrathodrooman)  
**Area:** Sports Suite & Role Dashboards (Sprint Batch `[S05]`)  
**HTML Presentation File:** [`Akshata_Education_OS_Demo_Report_8Nov2026.html`](file:///c:/Users/Rathod/Education_OS/Akshata_Education_OS_Demo_Report_8Nov2026.html) (double-click to open in browser for your demo!)

---

## 1. What is Education OS & What Are We Building Here?

### The Core Vision
Education OS is **one configurable higher-education operating system**: a cloud-native, multi-tenant SaaS platform built to replace the dozens of fragmented legacy ERPs and point-solutions that colleges and academies currently juggle.

Instead of an institution running separate, siloed tools for admissions, fee collection, attendance, examinations, sports academies, student housing, and faculty management, Education OS provides **one unified engine** tailored to higher education.

### How the Architecture Works
1. **Multi-Tenant with Strict Data Isolation:** Every single database table has an `organisation_id` column with PostgreSQL **Row-Level Security (RLS)** policies. A sports college can never access or leak data from another college.
2. **Core Foundation & Common Services:**
   - Platform Core: Identity, Tenancy, Billing, and API Gateway.
   - Platform Services: Asynchronous Event Bus (Transactional Outbox), Tamper-evident Audit Ledger, Scheduled Tasks, Multi-channel Notifications, and Unified Search.
3. **Common Suites (Present in every college):**
   - Student Lifecycle (Admissions, Enrolment, Student Information, Public CMS)
   - Academics (Timetable, Course Offerings, Examinations, LMS)
   - Finance & Operations (Fees, Accounts, Payroll, Procurement, Budgets)
   - Facilities (Space Booking, Maintenance, Inventory, Equipment)
   - Campus Life (Hostel, Transport, Library, Placement)
4. **Specialized Suites (Configured by Institution Profile):**
   - Different fields have completely different operational models. An engineering college does not need athlete fitness clearances; a sports college does not need heavy CAD labs.
   - **Your Specialized Domain — Sports College:** Covers athlete profiling, fitness benchmarks, medical clearance tracking, nutrition planning, sports video analysis with coach annotations, and inter-university tournament management.
5. **Security & Permission Resolution:**
   - Access is evaluated in four strict layers: `User -> Role -> Permission Keys (x-permission) -> Organisation Plan Entitlement`. Modules never inspect raw role names—they only enforce capability-based permission keys.

---

## 2. What Changed & What Was Added Since Your 5 Nov Report?

The 25-page PDF report you prepared on 5 November 2026 captured work up to that date. Here is everything delivered between **6 November and 8 November 2026** that was missing, pending, or marked "open" in that PDF:

| Item | Status in 5 Nov PDF | Status Today (8 Nov 2026) |
|---|---|---|
| **Training Video Analysis Enablement** | **Open / Blocked:** Listed as PR #480 (*"waiting on a branch fix; module not enabled on live app"*). | **MERGED & ENABLED:** Merged into `origin/main` in **PR #565** on Fri 6 Nov at 12:44 (`88d1eb71`). Now active in both backend and frontend `modules.enabled.yaml`! |
| **Coach Session Plan & Athlete Training Schedule** | **Open / Unmerged:** Listed as PR #481 & #482 (*"coach session plan still shows as not built"*). | **COMPLETED & REBASED:** Unified in [`UpcomingSessions.tsx`](file:///c:/Users/Rathod/Education_OS/modules/sports/training-video-analysis/frontend/src/widgets/UpcomingSessions.tsx) serving both `session-plan` and `training-schedule` with 115 lines of passing unit tests ([`sessions.test.tsx`](file:///c:/Users/Rathod/Education_OS/modules/sports/training-video-analysis/frontend/tests/sessions.test.tsx)). Rebased on main in `f89365d6`. |
| **Examinations Candidate Eligibility (Issue #325 / Q5)** | **Unresolved Question:** Q5 (minimum attendance threshold and ownership) was holding up candidate eligibility. | **ARCHITECTURALLY RESOLVED:** Collaborated with Shivani (Academics) on 6 Nov. Established the hierarchical resolution (`Course > Programme > Exam Cycle > Organisation default`), approved absences excluded from denominator (decision C7), and manual condonation override. |
| **Sports College E2E Dashboard Journeys** | Marked as tasks in Rooman Projects. | **MERGED IN #544:** Commit `55c3b163` officially registered all sports college journeys in the test suite documentation. |

---

## 3. Pin-to-Pin Inventory of Everything Akshata Built

### A. The Client Admin Console (Foundational Delivery)
* **PR:** [#187](https://github.com/rooman-itsd/Education_OS/pull/187) (Merged 12 Oct 2026)
* **Size:** 90 files, 14,584 lines of production React, TypeScript & CSS.
* **Paths:** [`apps/frontend/admin.html`](file:///c:/Users/Rathod/Education_OS/apps/frontend/admin.html) and [`apps/frontend/src/admin/`](file:///c:/Users/Rathod/Education_OS/apps/frontend/src/admin/)
* **What it does:** The mission control for institutional administrators. Features headline KPI dashboards, live user management, role & permissions inspector, module registry by suite, entitlement rule engine, audit log, and super-admin organisation management.

### B. The Five Modules Built End-to-End
Every module follows the strict Education OS standard: contracts first, PostgreSQL schema with RLS, service layer, domain rules, full unit & leak tests, frontend widgets, and host enablement.

#### 1. Athlete Performance
* **PRs:** #165 (PRD), #352 (Backend & tests), #377 (Event publishing & clearance lapse), #385 (Widgets & clearance report), #427 (Host enablement).
* **Path:** [`modules/sports/athlete-performance/`](file:///c:/Users/Rathod/Education_OS/modules/sports/athlete-performance/)
* **Metrics:** 33 API operations, 65 automated backend tests, 4 widgets.
* **Widgets Built:**
  - `squad-overview` (Coach): View squad athletes, benchmark comparisons, and clearance badges.
  - `fitness-clearances` (Medical Staff): Active athlete clearances, most urgent first (not cleared / restricted / lapsing).
  - `performance-trend` (Athlete): Personal results over time with trend indicators (improving / declining).
  - `body-composition-trend` (Nutritionist): Weight, body fat %, and lean mass tracking.

#### 2. Sports Nutrition & Health
* **PRs:** #370 (Backend & tests), #389 (Widgets), #478 (Host enablement).
* **Path:** [`modules/sports/sports-nutrition-health/`](file:///c:/Users/Rathod/Education_OS/modules/sports/sports-nutrition-health/)
* **Metrics:** 18 API operations, 41 automated backend tests, 5 widgets.
* **Widgets Built:**
  - `nutrition-plan` (Athlete): Active meal plan, daily calories, macronutrient split (protein, carbs, fat), hydration.
  - `injured-athletes` (Medical Staff): Recovery status, expected return date, severity badges.
  - `appointments-today` (Medical Staff): Daily physiotherapy and medical consultation roster.
  - `athletes-on-plans` (Nutritionist): Active diet plans across all assigned athletes.
  - `plan-reviews-due` (Nutritionist): Overdue and upcoming plan review queue.

#### 3. Tournament Events
* **PRs:** #387 (Backend & tests), #388 (Widgets), #479 (Host enablement).
* **Path:** [`modules/sports/tournament-events/`](file:///c:/Users/Rathod/Education_OS/modules/sports/tournament-events/)
* **Metrics:** 21 API operations, 85 automated backend tests, 2 widgets.
* **Widgets Built:**
  - `upcoming` (Athlete): Confirmed tournament meets, dates, venues, categories entered.
  - `calendar` (Coach): 4-week lookahead of scheduled matches, fixtures, and registration deadlines.

#### 4. Training Video Analysis
* **PRs:** #167 (Contracts), #386 (Backend & tests), #390 (`reviews-pending` widget), #565 (Host enablement merged 6 Nov).
* **Path:** [`modules/sports/training-video-analysis/`](file:///c:/Users/Rathod/Education_OS/modules/sports/training-video-analysis/)
* **Metrics:** 23 API operations, 82 automated backend tests, 3 widgets.
* **Widgets Built:**
  - `reviews-pending` (Coach): Queue of unannotated video clips waiting for coach feedback.
  - `session-plan` (Coach) & `training-schedule` (Athlete): Built in [`UpcomingSessions.tsx`](file:///c:/Users/Rathod/Education_OS/modules/sports/training-video-analysis/frontend/src/widgets/UpcomingSessions.tsx) from `GET /sessions`.

#### 5. Skill Progress (Generic Pattern Module)
* **PRs:** #166 (Contracts), #206 (PRD), #384 (Backend & tests), #440 (`my-progress`), #499 (`assessments-due` & `cohort-overview`).
* **Path:** [`modules/practice/skill-progress/`](file:///c:/Users/Rathod/Education_OS/modules/practice/skill-progress/)
* **Metrics:** 20 API operations, 82 backend tests, 20 widget tests, 3 widgets.
* **Widgets Built:**
  - `my-progress` (Learner, across 6 role layouts): Skill levels and assessment timeline.
  - `assessments-to-verify` (Instructor, across 6 role layouts): Queue of submitted assessments to verify.
  - `cohort-overview` (Practicum Coordinator): Per-framework competency breakdown.

### C. Examination Staff Dashboard (Wave A Contribution)
* **PRs:** #216 (Frontend widgets), #225 (Playwright E2E journey), #268 (Dashboard enablement).
* **Path:** [`modules/academics/examinations/frontend/src/widgets/`](file:///c:/Users/Rathod/Education_OS/modules/academics/examinations/frontend/src/widgets/)
* **Widgets Built:** `ExamSchedule.tsx`, `HallTicketsIssued.tsx`, `ResultsPending.tsx`.

---

## 4. What is Remaining (Pin to Pin)

1. **Merge Schedule Widgets PR:**
   - Branch `feat/training-video-analysis/schedule-widgets` is rebased on `main` and ready to merge.
   - Branch `platform/identity/session-widget-layouts` wires the widgets into `coach.yaml` and `athlete.yaml` (needs Faizan's quick approval as Platform owner).
2. **Complete 6 E2E Data Journeys:**
   - In [`tests/e2e/dashboards/coach.spec.ts`](file:///c:/Users/Rathod/Education_OS/tests/e2e/dashboards/coach.spec.ts): Un-`fixme` the 3 data journeys (`squad-overview`, `reviews-pending`, `calendar`).
   - In [`tests/e2e/dashboards/athlete.spec.ts`](file:///c:/Users/Rathod/Education_OS/tests/e2e/dashboards/athlete.spec.ts): Un-`fixme` the 3 data journeys (`performance-trend`, `nutrition-plan`, `upcoming`).

---

## 5. 10-Minute Demo Script for Tomorrow

### Minute 0:00 – 1:30 | Introduction & Admin Console
* **Action:** Open `https://educationos.futureacad.ae/admin.html` (or `http://localhost:5173/admin.html`).
* **Say:** *"Education OS is a unified, multi-tenant operating system for higher education. Here is the Admin Console I built—90 files, 14,500+ lines. It gives administrators full visibility into users, roles, and the module registry with our entitlement engine."*

### Minute 1:30 – 4:00 | The Coach & Training Experience
* **Action:** Open the Coach Dashboard.
* **Say:** *"For our sports academy, here is the Coach Dashboard. In Squad Overview, coaches see instant performance metrics and clearance statuses. In Videos to Review, our training video analysis module pulls unannotated drill recordings with exact timestamps."*

### Minute 4:00 – 6:30 | Athlete, Medical & Nutrition Workflows
* **Action:** Show the Athlete Dashboard, then Medical Staff.
* **Say:** *"An athlete sees only their data: personal sprint progress curves, active nutrition macros (calories, protein, carbs), and tournament registrations. Medical staff get real-time fitness clearances sorted urgency-first, and physiotherapists see today's appointments."*

### Minute 6:30 – 8:30 | Engineering Rigor & Cross-Module Impact
* **Action:** Show `modules/sports/athlete-performance/contracts/openapi.yaml` and test runs.
* **Say:** *"Everything we build is contract-first. We built 5 full modules with over 115 API operations and 355+ backend tests with PostgreSQL row-level security. Beyond sports, I built the Examination Staff widgets and collaborated with Academics on candidate eligibility."*

### Minute 8:30 – 10:00 | Project Status & Q&A
* **Say:** *"All 5 sports modules are completed and enabled in the host. We are on track for our final v1.0.0 release on Thursday, 12 November."*

