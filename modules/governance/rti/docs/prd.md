# rti: product requirements

Owner: Madhumita (@madhumitha-rooman) · Status: draft for review · Week 1 task (issue linked in the PR)
Suite G, Governance · tier `common` (every academy type enables it)

## Purpose

RTI request intake, assignment, tracking and responses (`module.yaml`). Right to Information requests usually come
from members of the public by post, in person, by email or through an online portal. RTI staff record each request,
assign an officer, ask internal custodians for the information, send the response or transfer the request to another
public authority, and record and decide first appeals. The contract is `contracts/openapi.yaml`, `events.yaml` and
`permissions.yaml`.

The repository names RTI but does not specify its procedure, deadlines, fees or appeal rules. This contract therefore
makes timelines configurable and leaves statutory details to the open questions; it does not encode legal requirements.

## Users and what they need

| Role (profile role → module role, proposed; open question 10) | Needs | Dashboard widget |
|---|---|---|
| RTI officer (`governance` → `rti-officer`) | Record requests, assign, refer to custodians, respond, transfer, close; see deadlines | `rti.nearing-deadline` (`GET /stats/nearing-deadline`) |
| Custodians (`department-admin`, `faculty` → `rti-custodian`) | See and answer the referrals sent to them, without the applicant's details | — |
| Appellate authority (`management` → `rti-appellate-authority`) | Record and decide first appeals; read the requests | — |
| Org admin (`org-admin` → `rti-viewer`) | Counts and deadlines only | — |

Applicants are mostly not users of the system. They have no screens in v1 (open questions 4 and 9).

## Main flows

1. **Record.** An officer records a received request: how and when it was received, the applicant (name, address,
   email, phone, and a person id if the applicant is a user), subject, the information sought, and fee metadata
   (status `paid`, `exempt` or `pending`, amount, mode, receipt reference). It gets a per-organisation number
   (`RTI-000045`) and status `received`. Publishes `rti.request.received`.
2. **Assign.** The request is assigned to an officer (`received → assigned`); it can be re-assigned while `assigned`.
3. **Refer.** The officer asks one or more internal custodians for the information, with a question and an optional
   due date. Each custodian sees only the question and the request number, and replies. Referrals do not change the
   request status.
4. **Correct.** Before a response, an officer can correct the applicant details, subject, information sought or fee
   metadata.
5. **Respond.** The officer records the response (`assigned → responded`): information provided, partly provided or
   refused, a summary, the grounds (free text, required when partly provided or refused) and how and when it was
   dispatched.
6. **Transfer.** A request meant for another public authority is transferred, with the authority's name and address,
   the date and a reason (`received` or `assigned` → `transferred`, final). Publishes `rti.request.closed`.
7. **Appeal.** Within the configured appeal window, the appellate authority records a first appeal received against
   the response (`responded → appealed`) and later decides it (`appealed → appeal_decided`). If
   `RTI_APPEAL_WINDOW_DAYS` is not configured, no appeal is accepted and the request is refused with the error
   "Appeal window is not configured".
8. **Close.** An officer closes a responded request once the appeal window has passed, or an appeal-decided request
   (`→ closed`, final). Publishes `rti.request.closed`. While `RTI_APPEAL_WINDOW_DAYS` is not configured, a responded
   request stays `responded` and cannot be closed; there is no fallback.
9. **Deadlines.** A request's due date is worked out when read from `received_on` and `RTI_RESPONSE_DAYS`, and an
   appeal's from `filed_on` and `RTI_APPEAL_DECIDE_DAYS`. An open item past its due date is overdue. With no value
   set there is no due date. The widget lists open requests due within `RTI_NEARING_DEADLINE_DAYS` and overdue ones.

### Statuses

```
received → assigned → responded → closed
assigned → assigned                        (re-assign)
received | assigned → transferred          (final)
responded → appealed → appeal_decided → closed
closed                                     (final)
```

## Confidentiality and access

- **Applicant personal data** (name, address, email, phone, person id) is visible only to `rti-officer` and
  `rti-appellate-authority` through `rti:request:read`. Custodians see only their referral's question and the request
  number. Viewers see counts, request numbers and due dates only.
- **Audit:** every state change, every referral and reply, and every read of a full request are recorded through
  `packages/sdk`.
- **Notifications** to officers, custodians and the appellate authority carry only the request number and a generic
  message, never applicant data or request content.
- **Events** carry only identifiers and metadata (see Events).

## Rules

- Every table carries `organisation_id` with row-level security; every event carries `organisation_id`.
- Status changes follow the transitions above; anything else is refused.
- A response of type `partly_provided` or `refused` needs grounds. No list of exemptions is built in.
- Nothing is deleted: requests end as `closed` or `transferred`.
- People (applicant when a user, officers, custodians, appellate authority) are identity person ids, by id only, with no
  foreign keys to other modules.
- No dependency on another module being enabled. No real applicant data in tests or seeds.

## Data model (summary)

| Entity | Key fields |
|---|---|
| RtiRequest | id, number, received_via (post, in_person, email, online_portal), received_on, applicant {name, address, email, phone, person_id}, subject, information_sought, fee {status, amount, mode, receipt_reference}, officer_id, status, closure (responded, appeal_decided, transferred), created_by, assigned_at, responded_at, closed_at |
| Referral | id, request_id, custodian_id, question, due_on, status (open, replied), reply, replied_at |
| Response | request_id, type (information_provided, partly_provided, refused), summary, grounds, dispatched_on, dispatch_mode, responded_by |
| Transfer | request_id, authority_name, authority_address, transferred_on, reason, transferred_by |
| Appeal | request_id, filed_on, grounds, outcome (upheld, partly_upheld, dismissed), decision_note, decided_by, decided_on |

## Dashboard widget

| Widget id | Dashboard | Endpoint | Permission | Shows |
|---|---|---|---|---|
| `rti.nearing-deadline` | Governance | `GET /stats/nearing-deadline` | `rti:stats:read` | Counts of open requests due within `RTI_NEARING_DEADLINE_DAYS` and overdue, and a list of request numbers, statuses and due dates; no applicant data |

The widget implementation is out of scope for this PR; this PR defines only the endpoint contract.

## Events

| Event | What it is for | Current consumers |
|---|---|---|
| `rti.request.received` | A request was recorded: identifiers, how and when it was received | None yet |
| `rti.request.closed` | A request reached a final state: how it ended (`responded`, `appeal_decided`, `transferred`), the response type and whether it was appealed | None yet; regulatory-reports may need counts (open question 8) |

Payloads never carry the applicant's name, address, email, phone or person id, the subject, the information sought,
fee details, referral questions or replies, the response summary or grounds, the transfer authority, or appeal grounds
or decision notes. Whether these events should be public at all is open question 8.

## Integration points

| Direction | With | How |
|---|---|---|
| Publishes | anyone | the two events above (`events.yaml`) |
| Consumes | none | |
| Platform | identity, audit, notification | through `packages/sdk`: permission checks and person ids; audit; generic internal notices |
| Not integrated in v1 | fees-accounts, web-portal-cms, platform/documents, scheduler, regulatory-reports, grievance, helpdesk, incident-management | Fees are metadata only; no public form; no attachments; no timers; counts later |

## Configuration

`config/env.example`: `RTI_REQUEST_NUMBER_PREFIX`, `RTI_DEFAULT_CURRENCY`, `RTI_NEARING_DEADLINE_DAYS` (a widget
threshold, not a legal value), and `RTI_RESPONSE_DAYS`, `RTI_APPEAL_WINDOW_DAYS`, `RTI_APPEAL_DECIDE_DAYS` and
`RTI_DAY_COUNTING`, which are left empty until open question 1 is settled. While `RTI_APPEAL_WINDOW_DAYS` is empty,
appeals are refused ("Appeal window is not configured") and responded requests stay `responded`; there is no fallback.

## Out of scope (v1)

- Collecting fees (fees-accounts) and fee exemption rules (open question 3).
- A public online form or applicant self-service (open question 4).
- Attachments: scanned applications, response letters, supplied copies (open question 6).
- Second appeals to bodies outside the institution (open question 7).
- Messages to applicants through the system (open question 9).
- Reminders and timers; the scheduler is not used.

## Open questions (for review)

1. **Statutory timelines.** Response days, appeal window, appeal decision days, and working or calendar days. The
   repository specifies none; they are empty settings until the governance office confirms them.
2. **Urgent requests.** Is faster handling needed for some requests (for example where life or liberty is involved)?
   v1 has no field or setting for it.
3. **Fees and exemptions.** v1 records fee metadata only. How would fees-accounts collect from applicants who are not
   users, and which exemptions apply?
4. **Public intake and applicant self-service.** An online RTI form in `web-portal-cms` or a public endpoint, or staff
   recording only (v1)?
5. **Third-party information.** Is a procedure needed when the information concerns a third party?
6. **Attachments.** `platform/documents` has no contract on `main`, so v1 has no attachments.
7. **Second appeals.** Appeals beyond the internal appellate authority go to bodies outside the institution. Track them,
   or keep them out?
8. **Event publication.** Keep `rti.request.received` and `rti.request.closed` public, or offer counts only through the
   API (for example for regulatory-reports)?
9. **Applicant communication.** Should the system ever send applicants email, or does correspondence stay outside it?
10. **Role naming and mapping (Faizan).** Module roles or profile role names; the proposed defaults; the link to the
    `audit-officer` role proposed in PR #189.
11. **Event format (Himanshu, Faizan).** This contract follows the convention on `main`: `organisation_id` in each
    payload and a file-level `version`. The event-bus contract proposed in PR #189 puts `organisation_id` in the
    envelope only and declares `version` on every event.
