# examinations: decisions, proposals and open questions

Issue #325 · Module owner: Shivani (@shivanisinghrooman-09)

This page records what the team has decided about examinations, what has only been proposed, and what
is still open, with the evidence for each. It supports [prd.md](prd.md), which states the requirements.

- **Confirmed** means the people who own the question agreed in a recorded comment or a merged contract.
- **Proposed** means someone suggested it and the person who must confirm it has not.
- **Open** means no record of an answer was found in the sources inspected.
- Times are UTC. A comment link looks like `https://github.com/rooman-itsd/Education_OS/pull/<n>#issuecomment-<id>`.

Nothing below is decided by being written here. The student, staff and instructor identifiers, department
authorisation, the minimum attendance, supplementary and backlog candidacy, result approval, and the
transcript and regulatory reporting requirements are **not** resolved by this page.

## 1. Contract availability is not implementation availability

A merged contract means the endpoint or event is defined. It does not mean any code serves or consumes it.

| Item | Contract | Implementation |
|---|---|---|
| examinations API (51 operations) and events (13) | merged (PR #183); the contracts lack 401/403 responses and `x-permission-any` (9 of 51 operations declare a 403, none declares a 401, and 9 permission keys appear in no `x-permission`) | **not implemented**: no backend, migrations or tests |
| examinations widgets `schedule`, `hall-tickets-issued`, `results-pending` | declared in the contract | UI merged (PR #216); their endpoints are not served, so they show "not available" |
| examinations widgets `exam-duties`, `upcoming-assessments`, `results-summary` | declared in the contract | **not built** |
| timetable-attendance `POST /reports/attendance-eligibility` | merged | **not implemented** (the timetable-attendance backend has timetables only) |
| fees-accounts `GET /dues` and key `fees-accounts:dues:read` | merged (PR #243) | served by the fees-accounts backend; **not called** from examinations |
| academic-management events (`term.*`, `course.*`, `offering.*`, `faculty-assignment.*`, `curriculum.published`) | merged (PR #168) | published by academic-management; **not consumed** by examinations (`consumes_events: []`) |
| enrolment-registration `course-registration.confirmed` / `.withdrawn` | merged | published; **not consumed** by examinations |
| student-information student-status event or API | not defined | none |

## 2. Q1 to Q13

| # | Question | State | Evidence | Next step and owner |
|---|---|---|---|---|
| Q1 | Is candidacy derived entirely from registration? Who registers supplementary and backlog candidates? | **Open** | No record found in the sources inspected. `course-registration.confirmed` carries a string `registration_type`; the contract does not say whether it covers supplementary or backlog registration. | Praveen |
| Q2 | What is `student_id`? Where do status and display name come from? | **Proposed** | Praveen proposed `student_id = person_id` from the enrolment events and asked for Faizan's confirmation ([PR #459, 2026-11-03T07:45Z](https://github.com/rooman-itsd/Education_OS/pull/459#issuecomment-6598201117)). Shivani's comment on PR #168 ([2026-10-10T15:53Z](https://github.com/rooman-itsd/Education_OS/pull/168#issuecomment-6099354051)) makes the canonical identifier for staff and person references, including instructors, pending Faizan's confirmation; `student_id` stays under C1, which that comment records as still open. Same question: timetable-attendance Q3, LMS LQ6. No record found in the sources inspected of an answer from Faizan. | Faizan, with Praveen |
| Q3 | Exam venues: free text or facility-booking resources? | **Open** | No record found in the sources inspected. The contract currently uses a free-text `venue_label`; that is not a confirmed decision. | Ashritha |
| Q4 | Can dues withhold eligibility or hall tickets? How are dues read? Who raises the invoice? | **Confirmed in principle by both owners; contract merged; response shape not confirmed by Examinations** | Gokula suggested events ([2026-10-13T06:34Z](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6139782495)); Shivani chose a synchronous `GET /dues` read at the cut-off, with examinations deciding through `check_dues` ([06:45Z](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6139932633)); Gokula agreed ([07:12Z](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6140320875)). Both recorded it as a "proposed decision": Shivani asked for it to be recorded "as the proposed decision, subject to agreement on the endpoint contract and ownership", and Gokula answered "Agreed, recorded as the proposed decision." Contract merged in [PR #243](https://github.com/rooman-itsd/Education_OS/pull/243) (2026-10-23T06:46Z, Faizan approved 06:38Z). | Follow-ups below |
| Q5 | Attendance for eligibility, and the minimum | **Partly decided** | The API part is confirmed: owner decision C7 ([Shivani, 2026-10-10T15:18Z](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6099000605)) and Praveen ([PR #459, 2026-11-03T07:45Z](https://github.com/rooman-itsd/Education_OS/pull/459#issuecomment-6598201117)): bulk read, excused classes excluded from the denominator, no threshold in the API. Where the minimum lives (owner decision C11) is unresolved. | Shivani (timetable-attendance), Akshata |
| Q6 | Does `upcoming-assessments` include LMS items? | **Confirmed** | Tejaswini: exam sessions only; a separate LMS widget would be needed for deadlines, which are not needed for Wave A and could be considered later; her comment does not address the first release beyond Wave A ([PR #175, 2026-10-13T07:06Z](https://github.com/rooman-itsd/Education_OS/pull/175#issuecomment-6140236257), answering [Shivani's question, 06:57Z](https://github.com/rooman-itsd/Education_OS/pull/175#issuecomment-6140101880)). Endpoint and key: [Shivani, 2026-10-10T15:03Z](https://github.com/rooman-itsd/Education_OS/pull/175#issuecomment-6098857599) and [15:04Z](https://github.com/rooman-itsd/Education_OS/pull/175#issuecomment-6098869576). | none |
| Q7 | Transcripts and certificates | **Open** | No record found in the sources inspected. | Praveen, Himanshu, Faizan |
| Q8 | Academic identifier names | **Confirmed** (names); **proposed** (person field) | Owner decision C5 ([Shivani, 2026-10-10T15:18Z](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6099000605)): `academic_period_id`, `course_offering_id`, `instructor_assignment_id`. The merged event payloads use them. Renaming the person on an assignment from `faculty_id` to `instructor_id` was proposed ([PR #168, 2026-10-10T15:53Z](https://github.com/rooman-itsd/Education_OS/pull/168#issuecomment-6099354051)), blocked on Faizan; merged events still say `faculty_id`. | Faizan (rename) |
| Q9 | Does LMS feed the continuous component? | **Confirmed** (Week 1) | Owner decision C9 ([Shivani, 2026-10-10T15:18Z](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6099000605)): no; exam marks are entered here; revisited later. | none |
| Q10 | Result approval: `platform/workflow` or this module's state machine? | **Open** | No record found in the sources inspected. The PRD does not use `platform/workflow` until this is decided. | Himanshu, Faizan |
| Q11 | Duty remuneration through hr-payroll? | **Confirmed** (v1); **proposed** (staff id) | v1: hr-payroll does not consume `examinations.duty.*`; pay is a manual payslip line (Gokula [2026-10-13T06:34Z](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6139782495); Shivani [06:45Z](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6139932633); Gokula [07:12Z](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6140320875)). Shivani said `staff_id` is the identity user id, pending Faizan's confirmation of the canonical identifier. | Faizan (identifier) |
| Q12 | Result fields for reporting, regulatory reports, NAD and DigiLocker | **Open** | No record found in the sources inspected. | Himanshu, Madhumita |
| Q13 | How is the caller's department known? | **Open** | No record found in the sources inspected of an answer from Faizan. Praveen's statement on PR #459 that the `*-department` keys grant nothing until Faizan answers (his Q9) applies to timetable-attendance's keys, not directly to examinations. The same question is timetable-attendance Q9. | Faizan |

## 3. Confirmed decisions

| Decision | Author and time | Evidence |
|---|---|---|
| Dues are read synchronously through `GET /dues` at the cut-off; examinations decides through `check_dues`; fees-accounts raises the invoice with source `{examinations, exam_cycle_id}`; key `fees-accounts:dues:read` (confirmed in principle by both owners; contract merged; response shape not confirmed by Examinations) | Gokula, Shivani; 2026-10-13 | PR #183 comments 6139782495, 6139932633, 6140320875 |
| Attendance for eligibility comes from `POST /reports/attendance-eligibility`; excused classes are excluded; the API applies no threshold | Shivani 2026-10-10T15:18Z; Praveen 2026-11-03T07:45Z | PR #183 comment 6099000605; PR #459 comment 6598201117 |
| `upcoming-assessments` shows exam sessions only; LMS deadlines would be a separate widget, not needed for Wave A and possibly considered later | Tejaswini, 2026-10-13T07:06Z | PR #175 comment 6140236257 |
| Academic identifier names (C5) | Shivani, 2026-10-10T15:18Z | PR #183 comment 6099000605 |
| LMS coursework grades do not feed `continuous` in Week 1 (C9) | Shivani, 2026-10-10T15:18Z | PR #183 comment 6099000605 |
| No hr-payroll consumption of `duty.*` in v1; manual payslip lines | Gokula, Shivani; 2026-10-13 | PR #183 comments 6139782495, 6139932633, 6140320875 |

## 4. Proposed decisions (not confirmed)

| Proposal | Proposed by | Needs | Evidence |
|---|---|---|---|
| `student_id = person_id` from the enrolment events | Praveen, 2026-11-03T07:45Z | Faizan | PR #459 comment 6598201117 |
| Rename the assignment person field `faculty_id` to `instructor_id` in all three academic modules | Shivani, 2026-10-10T15:53Z | Faizan | PR #168 comment 6099354051 |
| `staff_id` is the identity user id (platform-wide staff identifier) | Shivani, 2026-10-13T06:45Z | Faizan | PR #183 comment 6139932633 |
| The minimum attendance is set per exam cycle (`min_attendance_percent`) | the PRD | Shivani, Akshata | PRD Q5 |

## 5. Unresolved decisions and owners

| Decision | Owner |
|---|---|
| Canonical `student_id` (Q2), including student status and display name | Faizan, Praveen |
| Canonical staff identifier and the `faculty_id` / `instructor_id` rename (Q8, Q11) | Faizan |
| Department authorisation (Q13) | Faizan |
| Where the minimum attendance lives (Q5; owner decision C11) | Shivani, Akshata |
| Supplementary and backlog candidacy, and what `registration_type` means (Q1) | Praveen |
| Result approval workflow (Q10) | Himanshu, Faizan |
| Transcripts and certificates (Q7) | Praveen, Himanshu, Faizan |
| Result fields for reporting, regulatory reports, NAD, DigiLocker (Q12) | Himanshu, Madhumita |
| Exam venues (Q3) | Ashritha |
| How `course.updated` and `offering.updated` are applied (section 7) | Shivani, with Faizan for the architecture |
| Event envelope `version` (R-1): the outbox now has a `version` column; no record found in the sources inspected that R-1 is closed or how this contract changes | Faizan |
| Whether the merged `GET /dues` fits examinations (Gokula asked on PR #243; no record found in the sources inspected of a reply from Shivani) | Shivani |
| The 401 and 403 responses, and `x-permission-any` for the widening keys, are missing in the examinations contract (9 of 51 operations declare a 403; none a 401; 9 keys appear in no `x-permission`) | Shivani, with Faizan where other modules use the contract |
| How one module calls another module's API (needed for `GET /dues` and the eligibility read); there is no SDK | Faizan |

Owner decisions C1 to C3, C6, C8, C10 to C16, C22 to C25 are listed as still open in the decision record
([PR #183, 2026-10-10T15:18Z](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6099000605)),
but no record of their text was found in the sources inspected. Only C1 (student identifier) and C11 (where the minimum attendance
lives) can be identified from other comments.

## 6. Related decisions outside Q1 to Q13

| Decision | State | Evidence |
|---|---|---|
| Widget split: Akshata builds `examinations.schedule`, `hall-tickets-issued`, `results-pending`; `enrolment-registration.registered-candidates` stays with enrolment | Confirmed; merged in PR #216 | Akshata [2026-10-09T19:03Z](https://github.com/rooman-itsd/Education_OS/pull/183#issuecomment-6087418067); Shivani [PR #216, 2026-10-13T06:33Z](https://github.com/rooman-itsd/Education_OS/pull/216#issuecomment-6139774842) |
| Assessment Scheme belongs to examinations, not academic-management (CR-1) | Confirmed | Akshata, PR #168 [2026-10-08T18:56Z](https://github.com/rooman-itsd/Education_OS/pull/168#issuecomment-6066920488) and [2026-10-11T15:58Z](https://github.com/rooman-itsd/Education_OS/pull/168#issuecomment-6110869429). Whether academic-management's PRD wording was updated was not verified |
| `offering_ref` keeps `course_id` so `course.updated` can be applied | Confirmed (in the PRD data model) | Akshata, PR #168, 2026-10-08T18:56Z |
| Academic-management event names are authoritative once PR #168 merged; each consumer declares them in its own `consumes_events` in a follow-up PR (C4) | Confirmed; the follow-up is not done | PR #183 comment 6099000605 |
| Keep the event names `term.*` and `faculty-assignment.*` | Confirmed | Shivani, PR #168, 2026-10-10T15:53Z |
| Examinations does not consume `timetable.published` / `.unpublished` | Confirmed | Shivani, [PR #179, 2026-10-10T15:54Z](https://github.com/rooman-itsd/Education_OS/pull/179#issuecomment-6099361776) |
| Student-dashboard endpoints and keys: `GET /me/exam-schedule`, `examinations:session:read-own` | Agreed for examinations; others proposed | Shivani's proposed mapping, PR #175, 2026-10-10T15:03Z and 15:04Z ([6098857599](https://github.com/rooman-itsd/Education_OS/pull/175#issuecomment-6098857599), [6098869576](https://github.com/rooman-itsd/Education_OS/pull/175#issuecomment-6098869576)); Tejaswini's confirmation for the examinations item, 2026-10-13T07:06Z ([6140236257](https://github.com/rooman-itsd/Education_OS/pull/175#issuecomment-6140236257)) |
| `fees-accounts:dues:read` is granted to the profile roles `examination-staff` and `finance-staff` | In the merged contract; Faizan approved the PR | PR #243 |

## 7. Event payload limitation

`academic-management.course.updated` and `academic-management.offering.updated` carry only `changed_fields`
(`{course_id, changed_fields[]}` and `{course_offering_id, changed_fields[]}`). Their payloads do not contain
the updated values.

- A consumer cannot bring `offering_ref` up to date from these payloads alone.
- No decision on whether consumers may read academic-management's API to populate their read models
  was found in the sources inspected. The intended approach for this work is not to call the owner's API.
- Akshata noted the same point on PR #168 (2026-10-08T18:56Z): the consumer "re-reads `GET /offerings/{offering_id}`".

An architectural decision is needed before the full read-model update handlers are written. The options
(an enriched event payload, a read of the owner's API, or accepting stale data) are not chosen here.
The handlers for `offering.created`, `offering.status-changed`, `faculty-assignment.*` and
`course-registration.*` do not depend on this decision. The same limitation affects timetable-attendance.

## 8. Choices and gaps of the backend foundation

Found while building the domain rules and tables. None is decided; each is isolated or applied literally.

| Point | What the code does | Needs |
|---|---|---|
| Whether a grading band's `max_percent` is inclusive (PRD FR-3: bands "cover 0 to 100 without gaps or overlaps") | Validates each band and that the scheme has bands, grades are unique and values lie within 0 to 100. **The coverage rule is not enforced**: a test records that gaps and touching bands are accepted | Shivani, the controller's owner: the boundary convention |
| Which time zone "a session must fall within the cycle dates" is read in (FR-5) | `ensure_within_cycle` takes the zone as an argument; nothing supplies one yet | A source for the organisation's time zone (the same gap exists in timetable-attendance) |
| Cycle status moves other than the next one (PRD section 6 shows a line, and says the controller closes a cycle) | Only the next status is allowed, and `results_published` only by publication. Closing early, skipping and going back are refused | Shivani: whether a cycle may be closed or reopened from other statuses |
| Whether a grading scheme or exam cycle `code` must be unique | No uniqueness rule: the contract declares no 409 for creating a cycle | Shivani |
| What a cycle uses as grading scheme when the request names none and no default exists | `new_cycle` takes the scheme from the caller; the module does not choose one | Shivani |
| Candidates, hall tickets, marks, results, `registration_ref` | **No tables or code**: they carry `student_id` or depend on eligibility (the `student_id` mapping, supplementary and backlog candidacy, attendance minimum, dues) | Faizan (Q2), Praveen (Q1), Shivani (Q5) |
| FR-5's rule that a student may not be a candidate in two overlapping sessions | Not implemented (needs candidates) | As above |
| Department-scoped keys (`*-department`) | No department is read or assumed; `Actor` has no department | Faizan (Q13) |
| `offering_ref` | The table follows the PRD's columns, strictly (NOT NULL). It is not written yet; the consumer slice may need to relax it, as timetable-attendance's `offering_ref` had to be, because events arrive unordered and `offering.updated` carries no new values | The consumer slice, and the architectural decision in section 7 |
| The identity of `staff_id` on duties | Stored as a plain external id (PRD 5.8); no identity lookup or mapping | Faizan (Q11) |

## 9. Evidence limits

This record covers PR #183 (5 comments, 1 review, no inline comments), PRs #168, #175, #179, #216, #243 and
#459, and parts of #170, #64, #63, #107 and #184. It does **not** cover:

- PRs #176 and #177, and PR #222.
- The Student-dashboard issue #67.
- Any discussion outside GitHub.
- The full text of owner decisions C1 to C25 (section 5).

It does not claim to cover every team discussion. An item marked "open" means no record of an answer was
found in the sources inspected, not that none was given.
