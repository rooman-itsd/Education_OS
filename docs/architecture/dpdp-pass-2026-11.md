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
