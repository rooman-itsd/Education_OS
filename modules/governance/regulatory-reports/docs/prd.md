# regulatory-reports: product requirements

Owner: Madhumita (@madhumitha-rooman) · Status: draft for review · Week 1 task (issue linked in the PR)
Suite G, Governance · tier `common` (every academy type enables it)

## Purpose

UGC, AISHE, NIRF and other statutory reporting (`module.yaml`). Institutions owe recurring returns to regulators and
statutory bodies. This module keeps the organisation's list of those obligations, tracks each filing for each period
from preparation through review to submission and acknowledgement, and shows what is due and when. It records that a
return was filed and its acknowledgement reference; it does not compile the data, generate the forms or talk to the
regulators' portals. The contract is `contracts/openapi.yaml`, `events.yaml` and `permissions.yaml`.

The repository names UGC, AISHE and NIRF but defines no regulator, return, form or deadline, and regulators differ by
field. Obligations are therefore the organisation's own records: no regulator or return content is built in, and the
module stays field-neutral.

## Users and what they need

| Role (profile role → module role, proposed; open question 10) | Needs | Dashboard widget |
|---|---|---|
| Governance (`governance` → `regulatory-reports-coordinator`) | Keep the list of obligations, create filings per period, review, submit and record acknowledgements; see everything due | `regulatory-reports.due` (`GET /stats/due?scope=all`) |
| Filing owners (`hospital-coordinator`, `research-office`, `department-admin`, `finance-staff`, `hr-staff` → `regulatory-reports-preparer`) | Prepare the filings they own and send them for review; see their own due filings | `regulatory-reports.due` (`GET /stats/due?scope=mine`) on the Hospital Coordinator and Research Office dashboards |
| Management (`management` → `regulatory-reports-viewer`) | Read obligations and filings; see the compliance calendar | `regulatory-reports.compliance-calendar` (`GET /calendar`) |

## Main flows

1. **Obligations.** The coordinator records each return the organisation must file: a title, the authority it is filed
   with (a label such as "UGC"), an optional portal link, a description, a recurrence label (`once`, `monthly`,
   `quarterly`, `half_yearly`, `annual`; informational only) and a default owner. Obligations are deactivated, never
   deleted.
2. **Filings.** For each period the coordinator creates a filing of an obligation: a period label and dates, a due date
   and an owner (the obligation's default owner unless another is given). It starts `open`, and the owner is told through
   notification. There is no automatic creation per period (open question 3).
3. **Prepare.** The owner starts preparation (`open → in_preparation`), keeps preparation notes and links (for example to
   a working sheet or the portal page), and sends the filing for review (`in_preparation → under_review`).
4. **Review.** The coordinator returns it with a comment (`under_review → in_preparation`; the owner is told) or submits it.
5. **Submit.** The coordinator records the submission with the date and the reference the authority gave
   (`under_review → submitted`). Publishes `regulatory-reports.filing.submitted`. The filing itself happens outside the
   system, on the authority's portal or by post.
6. **Acknowledge.** When the authority acknowledges the return, the coordinator records the date and any acknowledgement
   reference (`submitted → acknowledged`, final). Publishes `regulatory-reports.filing.acknowledged`.
7. **Not applicable.** A filing that does not apply for a period is closed with a reason (`open` or `in_preparation` →
   `not_applicable`, final).
8. **Due and calendar.** A filing is overdue when it is not yet submitted and its due date has passed, and due soon when it
   is due within `REGULATORY_REPORTS_DUE_SOON_DAYS`; both are worked out when read. Owners see their own due filings,
   the coordinator sees all, and management sees a calendar of filings by due date.

### Statuses

```
open → in_preparation → under_review → submitted → acknowledged
under_review → in_preparation                     (returned with a comment)
open | in_preparation → not_applicable            (with a reason, final)
```

Final states: `acknowledged` and `not_applicable`.

## Rules

- Every table carries `organisation_id` with row-level security; every event carries `organisation_id`.
- Every state change, filing creation, edit, return, submission and acknowledgement writes an audit record through
  `packages/sdk`.
- Owners can edit notes and links of their own filings only while `open` or `in_preparation`. Owner and due date are
  changed by the coordinator before submission. Submitted and final filings are read-only.
- One filing per obligation per period label.
- Links are stored as given. No files are stored (open question 5).
- Nothing is deleted: obligations are deactivated, filings end as `acknowledged` or `not_applicable`.
- No regulator, return, form or deadline is built in, and nothing in the module assumes one field.
- No dependency on another module being enabled. No real institutional data in tests or seeds.

## Data model (summary)

| Entity | Key fields |
|---|---|
| Obligation | id, title, authority, portal_url, description, recurrence, default_owner_id, active |
| Filing | id, obligation_id, period_label, period_start, period_end, due_on, owner_id, status, preparation_notes, links, review_comment, submitted_on, submission_reference, submitted_by, acknowledged_on, acknowledgement_reference, not_applicable_reason |

## Dashboard widgets

| Widget id | Dashboards | Endpoint | Permission | Shows |
|---|---|---|---|---|
| `regulatory-reports.due` | Governance, Hospital Coordinator, Research Office | `GET /stats/due?scope=mine\|all` | `regulatory-reports:stats:read` (`scope=all` also needs `regulatory-reports:data:read`) | Filings due soon and overdue, with a short list of the soonest |
| `regulatory-reports.compliance-calendar` | Management | `GET /calendar?from=&to=` | `regulatory-reports:data:read` and `regulatory-reports:stats:read` (both required) | Filings by due date in the range: obligation title, authority, period, due date and status |

The widget implementation is out of scope for this PR; this PR defines only the endpoint contracts.

## Events

| Event | What it is for | Current consumers |
|---|---|---|
| `regulatory-reports.filing.submitted` | A filing was recorded as submitted (identifiers, period label, date) | None yet |
| `regulatory-reports.filing.acknowledged` | The authority's acknowledgement was recorded (identifiers, date) | None yet |

Payloads never carry preparation notes, links, review comments or submission and acknowledgement references. Whether to
keep the events is open question 9.

## Integration points

| Direction | With | How |
|---|---|---|
| Publishes | anyone | the two events above (`events.yaml`) |
| Consumes | none | No events from examinations or any other module in v1 (open question 2) |
| Platform | identity, audit, notification | through `packages/sdk`: permission checks and person ids; audit; notices to owners when a filing is created or returned |
| Not integrated in v1 | platform/reporting, platform/documents, scheduler, examinations, student-information, hr-payroll, fees-accounts, iqac-accreditation, grievance, rti, regulators' portals | No data compilation, files, timers or portal integration |

## Configuration

`config/env.example`: `REGULATORY_REPORTS_DUE_SOON_DAYS` (a widget threshold) and `REGULATORY_REPORTS_CALENDAR_MAX_DAYS`
(the longest range `GET /calendar` returns). Neither is a legal value.

## Out of scope (v1)

- Compiling return data from other modules, analytics and data warehousing (`platform/reporting`).
- Built-in regulators, returns, forms or deadlines.
- Creating filings automatically each period, and reminders (the scheduler is not used).
- Submission evidence files (links and references only).
- Integration with regulators' portals.
- Computing payroll and tax returns (hr-payroll); whether to track them here is open question 7.

## Open questions (for review)

1. **Returns and authorities.** The repository lists none, so obligations are organisation-defined in v1. Should standard
   reference data be offered later, and who maintains it?
2. **Automatic data.** Should returns ever be compiled from other modules' data? examinations (PR #183) already lists
   regulatory-reports as a consumer of `examinations.result.published` and `examinations.result.revised`; this module
   does not consume them in v1, to be resolved with Shivani. The same applies to iqac-accreditation responses and to
   grievance and RTI counts.
3. **Recurrence.** Create filings automatically each period (needs the scheduler), or keep manual creation (v1)?
4. **Reminders.** Reminders before due dates need the scheduler (PR #189, not merged).
5. **Submission evidence files.** `platform/documents` has no contract on `main`, so v1 keeps links and references only.
6. **Portal integration.** Is integration with regulators' portals out of scope for good, or a later version?
7. **Payroll and tax returns.** hr-payroll puts filing PF, ESI, TDS and professional tax returns out of its scope. Should
   they be tracked here as obligations?
8. **Review.** v1 submits only from `under_review`, so every filing is reviewed. Should the coordinator be able to submit
   without review?
9. **Event publication.** Keep `regulatory-reports.filing.submitted` and `regulatory-reports.filing.acknowledged` public,
   or drop them until a module needs them?
10. **Role naming and mapping (Faizan).** Module roles or profile role names; the proposed defaults, including the field
    roles `hospital-coordinator` and `research-office`; the link to the `audit-officer` role proposed in PR #189.
11. **Event format (Himanshu, Faizan).** This contract follows the convention on `main`: `organisation_id` in each payload
    and a file-level `version`. The event-bus contract proposed in PR #189 puts `organisation_id` in the envelope only and
    declares `version` on every event.
