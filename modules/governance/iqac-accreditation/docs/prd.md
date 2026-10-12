# iqac-accreditation: product requirements

Owner: Madhumita (@madhumitha-rooman) · Status: draft for review · Week 1 task (issue linked in the PR)
Suite G, Governance · tier `common` (every academy type enables it)

## Purpose

IQAC data collection, NAAC/NBA metrics, evidence repository (`module.yaml`). The Internal Quality Assurance Cell (IQAC)
prepares the institution for accreditation and its periodic quality reports. It keeps the accreditation frameworks the
institution reports against and their metrics, runs collection cycles in which metric owners across departments supply
values and narratives with evidence, reviews what they supply, and tracks quality action items to completion. The
contract is `contracts/openapi.yaml`, `events.yaml` and `permissions.yaml`.

The repository names NAAC and NBA but does not define their criteria or metrics. Frameworks and metrics are therefore
the organisation's own records; no accreditation content is built into this module.

## Users and what they need

| Role (profile role → module role, proposed; open question 9) | Needs | Dashboard widget |
|---|---|---|
| IQAC coordinator (`governance` → `iqac-accreditation-coordinator`) | Keep frameworks and metrics, run cycles, assign metrics to owners, review responses, manage action items | `iqac-accreditation.action-items` (`GET /stats/action-items`) |
| Metric and action owners (`department-admin`, `faculty` → `iqac-accreditation-contributor`) | Fill in and submit the responses assigned to them with evidence; update the action items assigned to them | — |
| Management, org admin (`management`, `org-admin` → `iqac-accreditation-viewer`) | Read frameworks, cycles, responses, evidence and action items; see counts | — |

## Main flows

1. **Frameworks and metrics.** The coordinator records the frameworks the institution reports against (for example the
   organisation's NAAC or NBA framework) and their metrics: a code, a title, the criterion it belongs to (a label), whether
   it is `quantitative` or `qualitative`, a unit and guidance. Frameworks and metrics are deactivated, never deleted.
2. **Cycles.** The coordinator opens a cycle for one framework and period (for example an annual quality report or an
   accreditation cycle) in `planning`, then starts collection (`planning → collecting`).
3. **Assign.** The coordinator assigns metrics of the cycle's framework to owners with a due date. Each assignment is a
   response in `pending`; the owner is told through notification.
4. **Respond.** The owner records a value (quantitative) or a narrative (qualitative), adds evidence and submits
   (`pending → submitted`). Evidence is a link or a reference to a record in another module (`{module, entity, id}`);
   files are open question 2.
5. **Review.** The coordinator accepts a submitted response (`submitted → accepted`, publishes
   `iqac-accreditation.response.accepted`) or returns it with a comment (`submitted → returned`); the owner corrects and
   submits again (`returned → submitted`).
6. **Close the cycle.** When collection is done the coordinator moves the cycle to `under_review`, records the date it was
   submitted to the accrediting body (`under_review → submitted`), and closes it (`submitted → closed`). Every cycle
   status change publishes `iqac-accreditation.cycle.status-changed`. Submitting to the accrediting body's own portal
   happens outside the system.
7. **Action items.** The coordinator records quality action items (from IQAC meetings, peer team visits, internal audits or
   anything else, as a free-text source), optionally linked to a cycle or metric, with an owner and a due date. The owner
   moves them `open → in_progress → done`; the coordinator can also cancel them. An open or in-progress item past its due
   date is overdue, worked out when read.
8. **Counts.** The widget shows action items that are open, in progress, overdue and due within
   `IQAC_ACCREDITATION_DUE_SOON_DAYS`.

### Statuses

```
Cycle:       planning → collecting → under_review → submitted → closed
Response:    pending → submitted → accepted
             submitted → returned → submitted
ActionItem:  open → in_progress → done
             open | in_progress → cancelled
```

Final states: cycle `closed`; response `accepted`; action item `done` and `cancelled`.

## Rules

- Every table carries `organisation_id` with row-level security; every event carries `organisation_id`.
- Every state change, assignment, review, evidence change and action item change writes an audit record through
  `packages/sdk`.
- A response can only be edited by its owner while `pending` or `returned`, and only while its cycle is `collecting` or
  `under_review`. An accepted response is read-only.
- Metrics can be assigned only from the cycle's framework, one response per metric per cycle.
- A cycle can move to `submitted` only when every response is `accepted`.
- Evidence links and references are stored as given; references use `{module, entity, id}` by id only, with no foreign
  keys and no check against the other module.
- Nothing is deleted: frameworks and metrics are deactivated, action items cancelled. Evidence added by mistake can be
  removed while its response is not accepted; the removal is audited.
- No dependency on another module being enabled. No real institutional data in tests or seeds.

## Data model (summary)

| Entity | Key fields |
|---|---|
| Framework | id, code, name, description, active |
| Metric | id, framework_id, code, title, criterion, kind (quantitative, qualitative), unit, guidance, active |
| Cycle | id, framework_id, name, period_start, period_end, status, submitted_on, closed_at |
| Response | id, cycle_id, metric_id, owner_id, due_on, status, value, narrative, review_comment, submitted_at, reviewed_by, reviewed_at |
| Evidence | id, response_id, title, kind (link, reference), url, reference {module, entity, id}, note, added_by |
| ActionItem | id, title, description, source, cycle_id, metric_id, owner_id, due_on, status, completed_at |

## Dashboard widget

| Widget id | Dashboard | Endpoint | Permission | Shows |
|---|---|---|---|---|
| `iqac-accreditation.action-items` | Governance | `GET /stats/action-items` | `iqac-accreditation:stats:read` | Action items open, in progress, overdue and due within `IQAC_ACCREDITATION_DUE_SOON_DAYS`, with the soonest due |

The widget implementation is out of scope for this PR; this PR defines only the endpoint contract.

## Events

| Event | What it is for | Current consumers |
|---|---|---|
| `iqac-accreditation.cycle.status-changed` | A cycle moved status (identifiers, framework, from and to status) | None yet |
| `iqac-accreditation.response.accepted` | A metric response was accepted (identifiers and metric code only) | None yet; regulatory-reports might reuse accepted data (open question 4) |

Payloads never carry values, narratives, evidence or review comments.

## Integration points

| Direction | With | How |
|---|---|---|
| Publishes | anyone | the two events above (`events.yaml`) |
| Consumes | none | |
| Platform | identity, audit, notification | through `packages/sdk`: permission checks and person ids; audit; notices to owners on assignment and return |
| References | any module | evidence may reference a record in another module by `{module, entity, id}` |
| Reads (later) | academics and other modules | other modules already give governance and IQAC roles read-only access to their reports; drawing metric values from them automatically is open question 3 |

## Configuration

`config/env.example`: `IQAC_ACCREDITATION_DUE_SOON_DAYS` (a widget threshold).

## Out of scope (v1)

- Accreditation criteria and metric content (the organisation's own records; open question 1).
- Evidence files (open question 2).
- Computing metric values automatically from other modules (open question 3).
- Submitting to accrediting bodies' portals; recording grades and peer team outcomes (open questions 5 and 6).
- Statutory returns such as AISHE or NIRF (regulatory-reports).
- Reminders and timers; the scheduler is not used.

## Open questions (for review)

1. **Framework content.** The repository defines no NAAC or NBA criteria or metrics. Should organisations enter them, or
   should reference data be provided later, and who maintains it?
2. **Evidence files.** `platform/documents` has no contract on `main`, so v1 evidence is links and references only. Files are
   central to an evidence repository; this needs a priority with Himanshu.
3. **Automatic data.** Should some metric values be drawn from other modules (for example student-information or
   examinations) through their published APIs, rather than entered by hand?
4. **Overlap with regulatory-reports.** Statutory returns and accreditation metrics overlap. Should regulatory-reports reuse
   accepted responses (for example by consuming `iqac-accreditation.response.accepted`)?
5. **External submission.** v1 only records the date a cycle was submitted to the accrediting body. Is more needed?
6. **Outcomes.** Should grades, scores or peer team recommendations be recorded on a cycle?
7. **Department scope.** Owners are people. Should heads of department see all responses of their department?
8. **Event publication.** Keep the two events public, or drop them until a module needs them?
9. **Role naming and mapping (Faizan).** Module roles or profile role names; the proposed defaults; the link to the
   `audit-officer` role proposed in PR #189.
10. **Reminders.** Due-date reminders for responses and action items would need the scheduler (PR #189, not merged).
11. **Event format (Himanshu, Faizan).** This contract follows the convention on `main`: `organisation_id` in each payload
    and a file-level `version`. The event-bus contract proposed in PR #189 puts `organisation_id` in the envelope only and
    declares `version` on every event.
