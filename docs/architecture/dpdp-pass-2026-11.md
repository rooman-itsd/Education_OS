# DPDP pass, November 2026 (v1.0 launch)

The review of Education OS against India's Digital Personal Data Protection Act, 2023 (the Act) before the v1.0
launch: issue #148, launch checklist item "Privacy notice and terms published on the public site; the DPDP pass
(#148) done". Scope: every module, platform service and integration on `origin/main`, the registration flow, the
export and deletion features, and the public site.

Reviewer: Claude (AI-assisted), for Faizan and Praveen. Date: 20 November 2026. Code reviewed at `72ce9d2f`
(main after #665). Method: each `infrastructure/models.py` or `domain/models.py` and its migrations read for
personal data, each `contracts/permissions.yaml` for who may read it, the export, deletion and retention code read,
and the tests that prove them run (section 5). **Not legal advice.** The legal bases below are proposals for
counsel to confirm, and the privacy notice and terms are drafts that need legal review before publication.

Nothing below is marked done unless code or a test shows it. Where a claim rests on reading code alone, it says so.

## 1. Who is the Data Fiduciary

| Data | Data Fiduciary | Education OS operator |
|---|---|---|
| What an institution keeps about its students, applicants, staff, parents, alumni, vendors, complainants and visitors (every feature module) | The institution (the organisation that registered) | **Data Processor** (s.8(2)): processes on the institution's instructions under a contract, which the Terms of Service now provide (section 5 of the terms) |
| The organisation's account: its record, the first administrator's name, email and password hash, the consent record, the registration token | The operator, `[Company legal name]` | Data Fiduciary |
| Billing: subscription, GST invoices (recipient legal name, GSTIN, address), payment references | The operator | Data Fiduciary |
| Platform emails (recipient address, rendered body), audit trail, event outbox, web server access logs | The operator, for the platform's own purposes; the content is often the institution's data | Data Fiduciary for the logs, Processor for the content |

Consequences: the consent of students and parents, the notice to them and the answer to their requests are the
institution's obligations; the platform must give institutions the means to meet them (section 6), and the operator
must meet its own obligations for account, billing and visitor data. Whether the operator is a Significant Data
Fiduciary (s.10) is for the Central Government to notify; nothing suggests it today.

**Commencement.** The Digital Personal Data Protection Rules, 2025 were notified in November 2025 with most of the
Act's obligations taking effect 18 months later (around May 2027). Counsel should confirm the dates. This pass
treats the obligations as in force, because institutions will ask about them now.

## 2. What runs in production

From `apps/backend/config/modules.enabled.yaml` on 20 November 2026:

- **Platform services enabled:** identity, tenancy, billing, notification, event-bus, scheduler, audit, workflow,
  reporting, api-gateway.
- **Feature modules enabled:** 41, every module under `modules/` except `campus-life/placement-career`.
- **Integrations enabled:** messaging-providers (email over SMTP) and payment-sbiepay.
- **Built but not enabled:** platform/documents, platform/search, campus-life/placement-career and six integrations
  (digilocker, nad, government-portals, external-university-portals, video-conferencing, wearables).
  platform/integration-hub is contracts only. These hold no production data today; they are in the data map so the
  notice covers them before they are switched on.
- **Public routes:** only `health` and the platform services bypass the entitlement gate
  (`apps/backend/src/eos_backend/gateway.py`). The admissions module's anonymous routes
  (`/admissions/public/{org_slug}/...`) exist but need a bearer token at the gate, so no anonymous applicant can
  reach them yet.

## 3. Data map

Every table below carries `organisation_id` with the row-level-security policy (checked in CI by
`tools/scripts/check-migrations.py`), except `tenancy_organisation` (it defines the tenants) and the platform-level
rows noted. Only personal-data columns are named; the full column lists are in each module's models.

**Abbreviations.**
Legal basis, proposed, for counsel to confirm: **C** consent of the person, or of a parent or lawful guardian for a
child (s.6, s.9), obtained by the institution; **V** data the person gave voluntarily for a specified purpose
(s.7(a)); **E** employment purposes (s.7(i)); **L** a duty under Indian law (s.7(c), (d); e.g. GST, the POSH Act 2013,
UGC anti-ragging regulations, the RTI Act 2005, AISHE returns); **M** medical emergency (s.7(f)), only for the urgent
use of health data.
Retention: **R0** kept while the organisation exists, then deleted by the organisation purge 30 days after a
deletion request (`EOS_ORGANISATION_RETENTION_DAYS`, run by hand, section 5) and gone from backups within 8 weeks
(`infra/backup-dr/README.md`). No module has a shorter retention for individual records unless the table says so.
Who can read: the roles the module's `contracts/permissions.yaml` grants, abbreviated (the module's own roles, and
academy roles that inherit them). Super admins can read every organisation only through support impersonation, which
needs a stated reason and publishes `tenancy.impersonation.started` (60-minute token).

### 3.1 Platform services and integrations

| Area | Personal data | Principals | Purpose | Basis | Retention | Who can read |
|---|---|---|---|---|---|---|
| platform/identity | `identity_user`: email, name, password hash (PBKDF2), roles, status, OIDC subject | every user; super admins (organisation_id NULL) | sign-in, authorisation | V, and C at registration for the first admin | R0; super admins indefinitely | the user (`/auth/me`); org-admin lists users |
| platform/tenancy | `tenancy_organisation`: organisation name, slug, country, consent record (`terms_version`, `terms_accepted_at`, `terms_accepted_by`, #665), deletion requester; `tenancy_registration_token`: admin email, token | first administrator | registration, verification, approval, deletion | C (terms accepted at registration) | R0 (the organisation row is deleted last by the purge) | org-admin its own organisation; super admin all |
| platform/billing | `billing_invoice`: recipient legal name, GSTIN, address, state code; `billing_profile`: legal name, GSTIN, address; `billing_subscription`: payment reference | organisation (sometimes a sole proprietor, then personal data) | invoicing, GST | L (CGST Act) | R0; **gap D15**: GST requires keeping invoices about 6 years, the purge deletes them | org-admin; super admin |
| platform/notification | `notification_message`: recipient address, user id, rendered subject and body, variables; `notification_preference`: locale, channels, quiet hours | every recipient | service emails | V / C | R0. `NOTIFICATION_HISTORY_RETENTION_DAYS=90` is in `config/env.example` but **nothing reads it (gap D14)** | the recipient (member, own inbox); org-admin; super admin |
| platform/audit | `audit_record`: actor id, before/after payloads, context. Email addresses and keys naming email, phone or mobile are dropped before storage (`eos_audit/application/consumers.py`) | anyone whose record changes | accountability, security | L / legitimate use | 7 years (`AUDIT_RETENTION_DAYS`, floor 2555 days, prune job). Append-only: the organisation purge cannot delete it; on `tenancy.organisation.purged` the payloads are tombstoned (`redact_organisation`) | org-admin its own trail; super admin |
| platform/event-bus and the outbox | `event_bus_delivery` and the outbox: event payloads, which can carry names and emails (e.g. `admin_email` in `tenancy.organisation.registered`) | anyone in an event | delivery between modules | as the source module | delivered events pruned after 30 days (`EVENT_BUS_RETENTION_DAYS`, `relay.prune`) | org-admin, super admin (operations) |
| platform/workflow | `workflow_request`: requester id and name, title, description, context; `workflow_action`: actor id and name, comments | staff, students | approvals | V / E | R0 | the requester, approvers; department-admin, org-admin |
| platform/reporting | `reporting_execution`: requester, parameters; `reporting_metric_fact`: dimensions (ids) | staff | reports | V | executions 90 days (`REPORTING_EXECUTION_RETENTION_DAYS`); facts R0 | org-admin, management, department-admin, faculty |
| platform/scheduler | job arguments (ids) | none directly | jobs | n/a | runs 90 days | org-admin, super admin |
| platform/documents (not enabled) | `documents_document`: title, filename, uploader, linked entity; the files themselves in object storage | anyone who uploads or is documented | files | as the linking module | metadata R0; **stored files are not deleted by the purge (gap D13)** | per document permission |
| platform/search (not enabled) | indexed copies of module records in OpenSearch | as the source | search | as the source | removed on `tenancy.organisation.purged` | filtered by caller's permissions |
| messaging-providers | none stored; sends through the configured SMTP relay | recipients | email delivery | as notification | not stored | super admin (configuration) |
| payment-sbiepay | `payment_sbiepay_payment`: payer, description, amount, gateway transaction id; refunds; callbacks | fee payers (students, applicants, parents) | online fee payment | V / contract | R0 | applicant, student (own), finance-staff, org-admin |
| digilocker (not enabled) | `digilocker_issued_document`: person id, holder name, date of birth, document number, document XML | students | issue and fetch certificates | C (the person links DigiLocker; `DIGILOCKER_CONSENT_DAYS=30`) | R0 | org-admin |
| nad (not enabled) | `nad_lodged_award`: person id, APAAR id **hash**, award number | students | NAD / ABC lodging | L (UGC NAD/ABC regulations) | R0 | org-admin |
| government-portals (not enabled) | submission package files (aggregate returns; may hold staff and student lists) | staff, students | AISHE, NIRF, NAAC | L | R0 | org-admin |
| external-university-portals (not enabled) | `exchange`: person id, partner name, transcript document | students | transcript exchange | C | R0 | org-admin |
| video-conferencing (not enabled) | `attendance`: person id, display name, time in meeting; meeting host; recordings (document ids) | students, staff | online classes | V | R0 | org-admin |
| wearables (not enabled) | `record`: person id, provider data (heart rate, sleep, training), read log | athletes | training | C (athlete's own link; revocable) | 730 days (`WEARABLES_RETENTION_DAYS`, tested) | coach, org-admin; every read logged in `read_log` |

### 3.2 Feature modules

Retention is R0 for every row unless stated. Most modules also keep their own `audit_entry` (actor, action, entity,
and in some modules before/after snapshots and a reason), purged with the organisation.

| Module | Personal data | Principals | Purpose | Basis | Who can read |
|---|---|---|---|---|---|
| student-lifecycle/student-information | `person`: first, last and preferred name, **date of birth**, gender, **national ID or passport number** (`identity_number`), contact (JSON), **guardians** (JSON, free form), linked user; status history; documents; ID cards | students, guardians | the learner record | C (V for adults) | registrar, org-admin, management, admissions-staff |
| student-lifecycle/admissions | `application`: applicant first and last name, email, phone, **date of birth**, user id; uploaded documents and their verification; offers, decline reasons; merit list rank and score | applicants (often minors) | admission | C | applicant (own), admissions-reviewer, admissions-staff, department-admin, management, org-admin |
| student-lifecycle/enrolment-registration | `programme_enrolment`: person id, student name, roll number, end reason; course registrations, withdrawal reasons | students | enrolment | C / V | registration-staff, org-admin, management, department-admin, examination-staff |
| student-lifecycle/web-portal-cms | page and announcement bodies (staff-written; no visitor data stored) | staff (as editors) | public site | V | public pages: anyone; editing: web-portal-cms-editor, org-admin |
| academics/academic-management | `roster_entry`: person id, student name, roll number; `faculty_assignment`: faculty id | students, faculty | sections and rosters | V / E | org-admin, department-admin, faculty, student, examination-staff |
| academics/examinations | `candidate`: student id, eligibility and override reasons; `exam_duty`: staff id | students, staff | exams, eligibility | V / L (university regulations) | examinations roles (controller, department head, faculty, student own, viewer) |
| academics/lms | submissions (text, files), quiz attempts and answers, grades and feedback, discussion posts, `member_ref`: student name | students, instructors | teaching and assessment | V | lms roles (admin, department head, instructor, student own, viewer) |
| academics/timetable-attendance | `attendance_record`: student id, status, remark, who marked; changes with reasons; section members' names | students, faculty | attendance, exam eligibility | V / L | timetable-attendance roles (admin, department head, faculty, student own, viewer, exam-eligibility) |
| campus-life/hostel | `allocation`: person name, notes, room; `leave_request`: destination, reason, **contact phone**; `visit`: **visitor name, relation, ID document note**; `incident`: category, description, action taken | residents (often minors), their visitors | residence, safety | C / V | hostel-admin, warden, security, resident (own), student, viewer |
| campus-life/library | members (name, category, block reason), loans, reservations, fines | students, staff | lending | V | library-admin, librarian, member (own), viewer |
| campus-life/transport | drivers (name, **licence number**, phone); passes (person name, route, stop); **`position`: GPS latitude/longitude of a trip** (the vehicle, not the rider) | riders, drivers | transport, safety | V / E | transport-admin, driver, rider, viewer. Positions deleted after 30 days (`TRANSPORT_POSITION_RETENTION_DAYS`, tested) |
| campus-life/alumni | `alumnus`: full name, email, phone, LinkedIn URL, employer, city, notes; mentoring assignments and session notes | alumni, mentees | alumni relations | C | alumni-coordinator, alumni-mentee |
| campus-life/placement-career (not enabled) | `application`: student name, declared CGPA, backlogs, offer CTC; company contacts (name, email, phone) | students, recruiters | placement | C | placement-career-officer, viewer, student (own) |
| facilities/asset-management | custodian id, verifier ids, disposal recipient | staff | assets | E | asset-management roles, facility-staff |
| facilities/facility-booking | bookings: booked by/for, notes, party size | staff, students | bookings | V | booking user (own), approver, manager, facility-staff, academy roles |
| facilities/inventory-equipment | loans: borrower, purpose, damage notes; movements: issued to | staff, students | equipment loans | V | inventory roles, academy roles |
| facilities/maintenance | tickets: reporter, assignee, description, photos, rating, feedback | staff, students | repairs | V | maintenance roles, facility-staff |
| facilities/sports-facilities | usage: group name, headcount, recorder | staff | facility use | V | sports-facilities roles, coach, athlete, org-admin |
| finance-operations/fees-accounts | invoices (person name), payments (**instrument number, bank name**, gateway reference), receipts, refunds, **concessions with reasons and documents** (can reveal category, income or disability) | students, payers | fees | V / C; L for receipts | finance-staff, examination-staff (dues), management, org-admin; applicant and student their own |
| finance-operations/hr-payroll | `employee`: name, email, phone, **date of birth**, designation, **bank account holder, last 4 digits and IFSC, PAN last 4**, exit reason; salary structures, payslips, leave reasons, appraisals (self review, ratings) | staff | HR, payroll | E; L (tax, PF) | hr-staff, finance-staff, management, org-admin; staff their own (department-admin and faculty roles hold self-service keys) |
| finance-operations/procurement | vendors: contact name, email, phone, address, GSTIN, **PAN**, bank last 4, IFSC (a sole proprietor is a person) | vendor contacts | purchasing | V / L | finance-staff, management, department-admin, facility-staff, faculty, research-office, org-admin |
| finance-operations/budget-grants | investigators (user id, role); expenditure descriptions | staff | grants | E | finance-staff, research-office, management, department-admin, org-admin, faculty, research roles |
| finance-operations/e-office | file notes (text, author), movements, receipts (sender), dispatches (**addressee, address, email**); categories carry `retention_years`, which **nothing enforces** | staff, correspondents | office files | E / L | file holders and the roles in its catalogue (hr, finance, department-admin, management, org-admin, faculty and others) |
| governance/grievance | `case`: **complainant id, respondent person id or description, category (incl. sexual harassment, ragging), description**, proceedings, decisions, appeals | students, staff | grievance redressal | L (POSH Act, UGC regulations) | grievance-complainant (own), committee-member, coordinator, viewer |
| governance/rti | `request`: **applicant name, address, email, phone**, information sought, fee; responses, transfers, appeals | the public | RTI Act duties | L (RTI Act 2005) | rti-officer, custodian, appellate-authority, viewer |
| governance/iqac-accreditation | response owners, narratives, evidence links | staff | accreditation | E / L | iqac roles |
| governance/regulatory-reports | filing owners, preparation notes | staff | statutory filings | E / L | regulatory-reports roles |
| practice/field-training | sites (contact name, email); placements (trainee and supervisor names), log entries and reflections, assessments | trainees, supervisors | internships | C / V | field-training roles (trainee own) |
| practice/portfolio | items (owner, description, media), reviews, scores | learners | portfolios | C | portfolio roles, academy roles |
| practice/productions | crew roles (user id, role name, notes, reason), tasks | students, staff | productions | V | productions roles, academy roles |
| practice/projects | members, guides, submissions (notes, files), reviews and scores | students, faculty | projects | V | projects roles |
| practice/selection-process | candidates (person id, source), panel decisions (scores, comments), interview slots | applicants | auditions, interviews | C | panelist, coordinator, org-admin, applicant and student (own) |
| practice/skill-progress | assessments: learner, evaluator, scores, level, feedback, evidence URLs | learners | skills | V | skill-progress roles |
| sports/athlete-performance | `athlete`: full name, **date of birth, gender**, squad, coach; results, fitness assessments, **medical clearance and restrictions** | athletes (often minors) | performance | C | athlete-performance roles, coach, medical-staff, athlete (own), nutritionist, management, org-admin |
| sports/sports-nutrition-health | **health records, injuries (body part, severity, clinical notes), appointments, nutrition plans, body weight** | athletes | athlete health | C; M in an emergency | sports-nutrition-health roles (medical, nutritionist, coach, athlete own), medical-staff, org-admin |
| sports/tournament-events | entries (athlete ids, team names), officials (name), logistics (contact person, accommodation) | athletes, officials | competitions | V | tournament-events roles |
| sports/training-video-analysis | **videos of athletes**, annotations naming athletes, session attendance | athletes, coaches | coaching | C | training-video-analysis roles, athlete (own), org-admin |
| support/helpdesk | tickets (requester, description, attachments, rating, feedback), comments | students, staff | support | V | helpdesk roles, support-staff, org-admin, management |
| support/incident-management | incidents and problems (reporter, lead, responders, timeline text) | staff | IT incidents | E | incident-management roles |
| support/knowledge-base | article authors and reviewers; feedback (person id, comment); `view_seen` reader key | staff, readers | articles | V | knowledge-base roles |
| support/sla-management | ticket references and assignees | staff | SLA clocks | E | sla-management roles |
| support/amc-vendor-support | vendor contacts (JSON) on contracts | vendor staff | maintenance contracts | V | amc-vendor-support roles |

**Special categories.** The Act has no "sensitive" category, but these tables carry data whose misuse harms most and
deserve the institution's strictest roles: health and injuries (sports-nutrition-health, athlete-performance
clearance), grievances about sexual harassment and ragging (grievance), national ID numbers (student-information),
financial data (hr-payroll, fees-accounts concessions), children's data (below), and location (transport).

## 4. Consent and notice at registration

**Organisation sign-up, before this pass.**

- The public site's register page (`modules/student-lifecycle/web-portal-cms/frontend/src/public/pages/RegisterPage.tsx`)
  had a required box, "I accept the Education OS terms of service on behalf of this organisation", with no link: no
  terms or privacy notice existed. It sends `accepted_terms: true`.
- The dashboard app's sign-up (`/app#signup`, `apps/frontend/src/auth/SignUp.tsx`) has **no box at all** and sends
  `accepted_terms: true` for every registration (gap D3).
- `platform/tenancy` refused `accepted_terms: false` (400, "terms must be accepted") but stored nothing: no version,
  no time, no user. No test covered the refusal.

**Done in this pass.**

- **#665 (merged):** the organisation records `terms_version` (`EOS_TERMS_VERSION`, default `2026-11-20`),
  `terms_accepted_at` and `terms_accepted_by` (the first administrator's user id); they are in the organisation's
  responses and its export, and `tenancy.organisation.registered` carries the version. Migration `tenancy_0003`.
  Tests: `platform/tenancy/backend/tests/test_terms_acceptance.py` (refusal stores nothing; version, time and user
  recorded; environment override; visible to the organisation and in the export).
- **#667 (open):** the Privacy Notice and Terms of Service at `#/privacy` and `#/terms`, linked from the footer and
  from the register page's box, which now reads "I agree to the Terms of Service on behalf of this organisation and
  have read the Privacy Notice". `LEGAL_VERSION` in `public/legal.ts` equals tenancy's `DEFAULT_TERMS_VERSION`.

**Still missing.**

- Users the organisation creates (`POST /identity/users`) and students signing in see no notice and give no consent.
  That is the institution's notice to give (section 1); the platform could show the institution's notice at first
  sign-in (gap D16).
- Changing the terms: nothing asks existing organisations to accept a new version (gap D17).
- The public admissions routes, once the gateway exposes them, take an applicant's name, email, phone and date of
  birth with no notice, consent or age check (gap D18).

## 5. Retention, export and deletion: what is verified

Tests run on 20 November 2026 against `72ce9d2f`, SQLite, with the repository's virtual environment:

| What | Proof | Result |
|---|---|---|
| The export holds every table with `organisation_id` of every enabled module, only this organisation's rows, secrets redacted (`password_hash` → `[redacted]`), invoices included; org admins get 403 | `apps/backend/tests/test_organisation_export_and_deletion.py::test_export_then_delete_restore_and_purge` (the real host with every enabled module) | 1 passed |
| Deletion archives at once (sign-in refused with "archived", module routes 403), needs `confirm_slug` for a paying organisation, can be restored; the purge is refused before `delete_after`, then removes every row; the other organisation is untouched | same test | passed |
| Export and purge without module code, tables found from the database (also reflected ones), FK-blocked tables retried, 409 `purge_blocked` naming the table, append-only tables kept and listed, redaction of secret-like suffixes, retention configurable, force purge | `platform/tenancy/backend/tests/test_export_and_deletion.py` (15 tests) and `test_terms_acceptance.py` (4) | 24 passed |
| Audit: personal keys and email addresses dropped before storage; a purged organisation's trail tombstoned; prune job removes only records past retention; retention below the 7-year floor raised to it | `platform/audit/backend/tests/test_audit_consumers.py`, `test_audit_records.py` | 48 and 32 passed. The Postgres-only tests (`test_audit_postgres.py`, grants and the `audit_redact_organisation` function) skip on SQLite; CI runs them |
| Event outbox: delivered events pruned after retention, pending and dead-lettered kept | `platform/event-bus/backend/tests/test_relay.py::test_prune_removes_only_delivered_events_past_retention` | 19 passed |
| Transport GPS positions purged after `TRANSPORT_POSITION_RETENTION_DAYS` | `modules/campus-life/transport/backend/tests/test_jobs.py::test_purge_old_positions` | 4 passed |
| Wearables: data gone on unlink even when the provider is down; retention deletes only old records | `integrations/wearables/tests/test_linking.py` | 16 passed (module not enabled) |
| Documents: a delete that storage refuses deletes nothing; deleting a version keeps the chain (#645) | `platform/documents/backend/tests/test_document_replay_and_versions.py` | not run locally (needs `minio`); passed in CI on main (api workflow run 43818587678, 16 November) |

**Gaps found here.**

- **Export is super admin only** (`platform:organisation:export`). An institution cannot download its own data; it
  must ask (the terms say so). Files are references only: platform/documents is not enabled, and when it is, the
  export must include the files (gap D12).
- **The purge runs by hand.** Nothing schedules it (`platform/tenancy/README.md`, "Who runs the purge"); retention is
  kept only if a super admin runs `POST .../purge` after `delete_after` (gap D11).
- **Stored files survive the purge.** The purge deletes `documents_document` rows but not the objects in storage;
  documents has no consumer of `tenancy.organisation.purged` (gap D13, before documents is enabled).
- **Notification history is kept forever.** `NOTIFICATION_HISTORY_RETENTION_DAYS=90` is documented but read by no
  code (gap D14).
- **Invoices are purged.** GST law needs them kept (gap D15, already noted in the tenancy README).
- **Retention schedules exist only as settings.** e-office categories have `retention_years`, which nothing
  enforces. No feature module deletes individual records on a schedule; everything is R0.
- **Backups.** Purged data stays in backups up to 8 weeks, and restoring an older backup brings a purged organisation
  back; the restore runbook must repeat the purge (`infra/backup-dr/README.md` says so).
