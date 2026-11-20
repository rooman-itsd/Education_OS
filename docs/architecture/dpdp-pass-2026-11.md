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
