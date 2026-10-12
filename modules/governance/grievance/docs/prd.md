# grievance: product requirements

Owner: Madhumita (@madhumitha-rooman) · Status: draft for review · Week 1 task (issue linked in the PR)
Suite G, Governance · tier `common` (every academy type enables it)

## Purpose

SGRC, anti-ragging and POSH-ICC complaint intake and resolution (`module.yaml`). A person files a complaint on one of
three tracks: a student grievance (heard by a Student Grievance Redressal Committee, SGRC), a ragging complaint (heard
by the anti-ragging committee), or a sexual harassment complaint (heard by the Internal Committee, ICC). The committee
acknowledges it, inquires, and decides; SGRC decisions can be appealed to an ombudsperson. Cases are confidential: only
the complainant and the members of the committee handling the case see its content. The contract is
`contracts/openapi.yaml`, `events.yaml` and `permissions.yaml`.

The repository names these three tracks but does not specify their procedures, timelines or committee rules. This
contract therefore makes timelines configurable and leaves statutory details to the open questions; it does not
encode legal requirements.

## Users and what they need

| Role (profile role → module role, proposed; open question 10) | Needs | Dashboard widget |
|---|---|---|
| Every signed-in person (→ `grievance-complainant`) | File a complaint, follow their own cases, answer the committee, withdraw, appeal an SGRC decision | — |
| Committee members (→ `grievance-committee-member`, for people on a committee) | See and work the cases of their own committees only: acknowledge, inquire, record proceedings, message the complainant, decide, transfer; ombudsperson members decide appeals | — |
| Governance (`governance` → `grievance-coordinator`) | Set up committees and their members; see counts. **No access to case content.** | `grievance.open-by-committee` (`GET /stats/open-by-committee`) |
| Management (`management` → `grievance-viewer`) | Counts only | `grievance.open` (`GET /stats/open`) |

`org-admin` gets no default role in this module, so it has no access to case content (open questions 4 and 10).

## Tracks and committees

| Track | Committee kind |
|---|---|
| `student_grievance` | `sgrc` |
| `ragging` | `anti_ragging` |
| `sexual_harassment` | `icc` |
| (appeals against SGRC decisions) | `ombudsperson` |

Each organisation sets up its own committees, names them and lists their members with a role (`chair`, `member`,
`external_member`). Whether the system should enforce any composition rule is open question 7.

## Main flows

1. **Set up committees.** A coordinator creates committees of the four kinds and maintains their members. A committee
   can be deactivated; one with open cases cannot.
2. **File.** A complainant chooses a track, and a committee of the matching kind when the organisation has more than one
   active, and gives a category (the organisation's own label), a description, the incident date and, optionally, the
   respondent (a person id or a description). The case gets a per-organisation number (`GRV-000123`) and status
   `submitted`. Committee members are told through notification. Publishes `grievance.case.filed`.
3. **Admit or not.** A member acknowledges the case (`submitted → acknowledged`) or does not admit it, with a reason
   (`submitted → not_admitted`, final).
4. **Inquire.** A member starts the inquiry (`acknowledged → under_inquiry`) and records proceedings (hearings,
   statements, notes). Proceedings are visible only to the committee.
5. **Talk to the complainant.** Members and the complainant exchange updates on the case, for example a request for
   information and its answer. Both sides see updates.
6. **Transfer.** A case filed with the wrong committee or track is transferred, with a reason, to an active committee of
   the right kind, before a decision. Its track follows the new committee's kind.
7. **Decide.** The committee records its decision (`under_inquiry → decided`): outcome, findings and recommended actions.
   The complainant sees the decision.
8. **Appeal (SGRC only).** Within the configured appeal window the complainant appeals an SGRC decision with a reason
   (if `GRIEVANCE_APPEAL_WINDOW_DAYS` is not configured, no appeal is accepted and the request is refused with the
   error "Appeal window is not configured")
   (`decided → appealed`). The appeal goes to the organisation's active ombudsperson committee, whose member decides it
   (`appealed → appeal_decided`). Appeals on other tracks are open question 5.
9. **Withdraw.** The complainant withdraws before a decision (`submitted`, `acknowledged` or `under_inquiry` →
   `withdrawn`, final).
10. **Close.** A member closes a decided case once the appeal window has passed, or straight away on non-SGRC tracks, and
    closes an appeal-decided case. Every final state (`closed`, `not_admitted`, `withdrawn`) publishes
    `grievance.case.closed`.
11. **Deadlines.** Each case has a due date worked out when read from per-track settings (acknowledge-by and decide-by
    days); an open case past it is overdue. No values are set by default (open question 1).
12. **Counts.** Governance sees open cases per committee and status, with overdue counts; management sees open cases per
    track, with overdue counts. Neither sees case content.

### Statuses

```
submitted → acknowledged → under_inquiry → decided → closed
submitted → not_admitted                                         (final)
submitted | acknowledged | under_inquiry → withdrawn             (final)
decided → appealed → appeal_decided → closed                     (SGRC track only)
```

## Confidentiality and access

- **Case content** (description, respondent, proceedings, updates, decision, appeal) is visible only to the complainant
  (their own cases, without proceedings) and to members of the committee currently handling the case. Holding a
  permission is not enough: membership is checked on the server for every read and change. Ombudsperson members see a
  case once it is appealed to them.
- **Coordinators and management** see committees and counts only, never case content.
- **Break-glass access** for anyone else is not part of this contract (open question 4). If it is added, it must be
  audited.
- **Audit:** every state change, every proceeding and update, every transfer, decision and appeal, committee changes, and
  every read of case content by a committee member are recorded through `packages/sdk`.
- **Notifications** carry only the case number and a generic message ("there is an update on case GRV-000123"), never
  case content.
- **Events** carry only identifiers and metadata (see Events).

## Rules

- Every table carries `organisation_id` with row-level security; every event carries `organisation_id`.
- A case's committee must be active and of the kind matching its track.
- Status changes follow the transitions above; anything else is refused.
- Nothing is deleted: cases end as `closed`, `not_admitted` or `withdrawn`; committees are deactivated.
- References to other modules use `{module, entity, id}` by id only, with no foreign keys and no check against the
  other module. People are identity person ids.
- No dependency on another module being enabled. No real complaint data in tests or seeds.

## Data model (summary)

| Entity | Key fields |
|---|---|
| Committee | id, name, kind (sgrc, anti_ragging, icc, ombudsperson), members [person_id, role], active |
| Grievance | id, number, track, committee_id, complainant_id, respondent (person_id or description), category, description, incident_date, status, closure (decided, withdrawn, not_admitted), filed_at, acknowledged_at, decided_at, closed_at |
| Proceeding | id, grievance_id, kind (hearing, statement, note), held_on, summary, recorded_by |
| Update | id, grievance_id, author_id, from_committee, body, created_at |
| Decision | grievance_id, outcome (upheld, partly_upheld, not_upheld), findings, actions_recommended, decided_by, decided_at |
| Appeal | grievance_id, committee_id (ombudsperson), reason, filed_at, outcome (upheld, modified, dismissed), outcome_note, decided_by, decided_at |

## Dashboard widgets

| Widget id | Dashboard | Endpoint | Permission | Shows |
|---|---|---|---|---|
| `grievance.open-by-committee` | Governance | `GET /stats/open-by-committee` | `grievance:stats:read` | Open cases per committee, by status, with overdue counts |
| `grievance.open` | Management | `GET /stats/open` | `grievance:stats:read` | Open cases per track, with overdue counts |

The widget implementation is out of scope for this PR; this PR defines only the endpoint contracts.

## Events

| Event | What it is for | Current consumers |
|---|---|---|
| `grievance.case.filed` | A case exists: identifiers, track and committee only | None yet |
| `grievance.case.closed` | A case reached a final state, with how it ended (`decided`, `withdrawn`, `not_admitted`) and whether it was appealed | None yet; regulatory-reports may need counts (open question 6) |

Payloads never carry the complainant, respondent, category, description, proceedings, updates, decision outcome,
findings or any other case text. Whether even these two events should be public is open question 6.

## Integration points

| Direction | With | How |
|---|---|---|
| Publishes | anyone | the two events above (`events.yaml`) |
| Consumes | none | |
| Platform | identity, audit, notification | through `packages/sdk`: permission checks and person ids; audit; generic notices to committee members and complainants |
| Boundaries | helpdesk, hostel | Grievances are not helpdesk tickets (helpdesk's own PRD); a hostel's discipline incidents stay in hostel, while ragging complaints come here |

## Configuration

`config/env.example`: `GRIEVANCE_CASE_NUMBER_PREFIX`, and per track `GRIEVANCE_<TRACK>_ACKNOWLEDGE_DAYS` and
`GRIEVANCE_<TRACK>_DECIDE_DAYS` for `STUDENT_GRIEVANCE`, `RAGGING` and `SEXUAL_HARASSMENT`, plus
`GRIEVANCE_APPEAL_WINDOW_DAYS` and `GRIEVANCE_DAY_COUNTING`. While `GRIEVANCE_APPEAL_WINDOW_DAYS` is empty, appeals are
refused ("Appeal window is not configured"); there is no fallback. The day values are left empty: they are the organisation's
to set and are not legal values (open question 1). With no value, a case has no due date.

## Out of scope (v1)

- Evidence and document attachments (open question 3).
- Respondent access to cases (open question 8).
- Anonymous complaints (open question 2).
- Appeals on the ragging and sexual harassment tracks (open question 5).
- Reminders and timers; the scheduler is not used.
- Turning helpdesk tickets into grievances (open question 9).
- Hostel discipline records (hostel).

## Open questions (for review)

1. **Statutory timelines.** The repository specifies no timelines. What acknowledge-by, decide-by and appeal-window days
   apply per track, and are they working or calendar days? To be confirmed by the governance office; until then the
   settings are empty.
2. **Anonymous complaints.** Should any track accept anonymous complaints (for example ragging), or none? v1 always
   records the complainant.
3. **Evidence attachments.** `platform/documents` has no contract on `main`, so v1 has no attachments. They are central to
   grievances; this needs a priority with Himanshu.
4. **Break-glass access.** Should the governance office or org admin ever read case content without being a committee
   member? If so, under what control, and always audited.
5. **Appeal scope.** Only SGRC to ombudsperson in v1. Do appeals on the other tracks go to bodies outside the institution
   and stay out of this module?
6. **Sensitive event publication.** Keep `grievance.case.filed` and `grievance.case.closed` public, or publish nothing and
   offer counts only through the statistics API (for example for regulatory-reports)?
7. **Committee composition.** Should the system enforce composition rules (for example an external member on an ICC), or
   leave composition to the organisation?
8. **Respondent access.** Should respondents see or answer a complaint in v1, or is that out of scope?
9. **Misfiled helpdesk tickets.** Should there be a way to redirect a helpdesk ticket that is really a grievance? That
   would be a helpdesk change in its own PR.
10. **Role naming and mapping (Faizan).** Module roles or profile role names; how committee membership grants
    `grievance-committee-member`; whether `org-admin` should get the coordinator role.
11. **Event format (Himanshu, Faizan).** This contract follows the convention on `main`: `organisation_id` in each payload
    and a file-level `version`. The event-bus contract proposed in PR #189 puts `organisation_id` in the envelope only
    and declares `version` on every event.
