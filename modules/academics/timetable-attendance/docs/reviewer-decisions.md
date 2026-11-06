# timetable-attendance: decisions for the reviewer

Issue #325 · Reviewer: @praveen-rooman · Raised by: Shivani

This page has four parts: the decisions the reviewer has confirmed, what is still unresolved, the design choices the
code has made that nobody has reviewed, and the original nine points as submitted with PR #459 (sections 1 to 9, which
describe the code as it was then); section 10 records the publication work. The contracts (`contracts/*.yaml`) have not been changed by any of this work.
Times are UTC.

## A. Confirmed by the reviewer

Praveen's review of PR #459
([comment 6598201117, 2026-11-03T07:45Z](https://github.com/rooman-itsd/Education_OS/pull/459#issuecomment-6598201117)),
where he approved the PR and asked for these to be recorded. "Contract change" means a change to
`contracts/*.yaml`, to be made in a separate `contract/timetable-attendance/...` PR.

| Point | Confirmed decision | Status in the code |
|---|---|---|
| Percentage with no counted class (section 1) | `null`, plus the `no_eligible_classes` flag | Domain already returns `None`. **Contract change** (nullable `percentage`) not made yet |
| Date range for generating classes (section 2) | Keep a `term_ref`; generate inside the term, narrowed by each slot's effective dates; refuse to publish if the term is unknown. `academic-management.term.created` carries `starts_on` and `ends_on` | `term_ref` and its `term.created` consumer exist. Publish refuses an unknown term (section 10). Generation is not built |
| Cancelling a class with an open session (section 3) | Mark the session cancelled; do not run close (which would make unmarked students absent). Cancelled classes never count | Not built. The contract's session status has only `open` and `closed`, so a cancelled status is a **contract change** |
| Read models (section 4) | The events exist. `offering_ref`, `section_ref`, `assignment_ref` come from academic-management `offering.*`, `section.*` and `faculty-assignment.created/ended`; `section_member` from enrolment-registration `course-registration.confirmed/withdrawn` and `section-allocation.changed` (`effective_on`). Copy enrolment-registration's `consumers.py` and register it under `eos.event_consumers` | Partly built (this PR): `term_ref`, `offering_ref`, `section_ref`. See B for what is not |
| Department scope | Waiting on Faizan (Q9). Until then the `*-department` keys grant nothing | Nothing enforces a department. No department claim is read |
| Exam eligibility | The API, `POST /reports/attendance-eligibility`, as decided in C7 | Contract merged; endpoint not implemented |
| 401/403 and the unused keys | Agreed, as a separate contract PR using `x-permission-any`. It needs Faizan, because other modules use this contract | Not done. **Contract change** |
| Student report paths | Intended: students use `/me/...` only | No implementation needed |
| Deviations from the PRD (schema naming, interim audit table) | All fine: the table prefix and separate version table follow every other module | none |

## B. Not decided, and not built because of it

| Open point | Owner | Effect on the code |
|---|---|---|
| Whether `faculty_id` (the person on `academic-management.faculty-assignment.*`) may be stored as the instructor (`instructor_id`). The rename is proposed in academic-management's PR #168; no record of Faizan's confirmation was found in the sources inspected | Faizan | **The `faculty-assignment.created` and `.ended` consumers are not implemented**, so `assignment_ref` is never filled by an event and a slot cannot name an instructor assignment outside tests |
| Whether `student_id` is the `person_id` carried by the enrolment events (Praveen proposed it and asked for Faizan's confirmation under Q3) | Faizan | **Built on that assumption** at the lead's request (section E). enrolment-registration's `docs/integration-points.md` records `person_id` (the student-information Person id, agreed on issue #100) as the answer to Q3. Open still: `/me` reads the caller's identity user id as the `student_id`, so a student whose user id is not their person id sees nothing there |
| How `offering.updated` and `course.*` are applied: they carry only `changed_fields`, not the new values | Shivani, with Faizan | Not consumed. A change to an offering's course code or title after creation is not reflected |
| How a department is known (Q9) | Faizan | See A |

## C. Design choices of the event consumers (not reviewed)

These are decisions the code makes that no one has approved. They follow `platform/event-bus/contracts/events.yaml`
(at-least-once, unordered, idempotent on the envelope id) but are the author's.

- **Idempotency** is keyed on the envelope id, kept per organisation in `processed_event`, and written in the handler's
  own transaction so a failure rolls it back.
- **A status is unknown until an event reports it.** `offering.created` and `section.created` carry no status, so
  `status` stays NULL rather than assuming a starting status (`planned`, `open`).
- **Partial rows.** An event can arrive before its creation event, so `offering_ref` and `section_ref` columns that only
  the creation fills (and `status`) are nullable. A row is treated as known only after its creation event (`academic_period_id`
  or `code` is set). Slot validation therefore refuses an offering or section that has only been mentioned.
- **Ordering** uses the envelope `occurred_at`, compared per row, to decide whether a status change is stale (an equal
  time applies). The event-bus contract says `occurred_at` is "not a reliable ordering key across modules" and tells
  consumers that need order to use "the entity's own state or occurred_at". Arrival order is never used.
- **A creation never overwrites**: a second `offering.created`, `section.created` or `term.created` for a known id is
  ignored, and the status a later event set is kept.
- **A malformed payload is refused** (the relay records the failure and retries, then dead-letters), not half applied.
  An envelope version other than 1 is refused too.
- **An event is applied only in its own organisation.** The handler refuses to run if the session is not scoped to the
  event's organisation, and an event with no organisation is not applied.

## D. Scheduled classes, attendance and reports: choices made (not reviewed)

Made by the classes-and-attendance PR (issue #325), from the contract, the PRD and section A. Each needs the reviewer's
confirmation; none is hidden behind a flag.

| Point | Choice | Why |
|---|---|---|
| Who "teaches" a class | `instructor_id` (from `assignment_ref`) equals the caller's user id | The faculty-assignment mapping (section B) is unconfirmed; this is the PRD's intent |
| Who "is" a student | the caller's user id is the `student_id` of `section_member` | PRD Q3 is open; `/me/schedule` and `/me/attendance-*` need one id |
| An ad-hoc class's date | the start's date in the offset the request gives (`09:30+05:30` is that day in India) | The organisation's time zone has no source (section 10); this uses the caller's own wall clock and assumes no zone |
| Today, when `date` is omitted | the UTC date | Same reason; the widgets pass the viewer's date, so they are not affected |
| The active academic period | the known term (`term_ref`) containing today; the latest-starting if several | academic-management answers 404 `active_term_not_found` the same way; the contract adds the 404 |
| Department scope (Q9) | `report:read-department` and `attendance-record:correct-department` grant nothing more. Department and student reports need `report:read-all`; a head without it gets 403 `department_unknown` (after the period is resolved, so a new organisation sees the widget's empty state) | Section A: "Until then the `*-department` keys grant nothing" |
| Reading sessions and records | the instructor, `report:read-all` or `override` | PRD section 12 read-scope rule, without the department step |
| What counts in reports | closed sessions of classes not cancelled; open sessions wait; cancelled sessions never count | FR-13, FR-18 and decision A3 |
| `override` | lifts the own-class limit and the marking window for open and mark; corrections at any time | permissions.yaml: "outside own-class and time-window limits" |
| Rescheduling an open session's class | its marking deadline follows the new end | The deadline is the end plus the window (FR-7) |
| Records of unmarked students | listed with `id: null` until marked, though a row exists (the snapshot) | The contract: "Null for an eligible student not yet marked" |
| Student history | covers every period when `academic_period_id` is omitted | A history has no natural "current"; the summary keeps the active-term default |
| Department report average | the mean of the students' percentages, students with no counted class left out | The contract names it `average_percentage` |

Not built: closing sessions automatically at the deadline (FR-11) needs a job under `eos.scheduler_jobs`.

## E. Section membership from enrolment-registration (for Praveen: PRD Q2)

PRD Q2 (the enrolment-registration events for section allocation, with an effective date) is answered by that module's
published `contracts/events.yaml`, which lists timetable-attendance as a consumer of all three. The consumers are built
on it; please confirm the mapping:

| Event | Effect on `section_member` |
|---|---|
| `course-registration.confirmed` | in `section_id` from the date of `confirmed_at` (read in the offset it carries) |
| `section-allocation.changed` | `from_section_id` ends the day before `effective_on`; `to_section_id` starts on it |
| `course-registration.withdrawn` | every membership of the registration ends on the date of `withdrawn_at` (inclusive) |

Each event adds a fact to `registration_ref` (one row per `registration_id`), and the registration's memberships are
rebuilt from all of its facts, so arrival order does not matter. A move received before its confirmation opens the new
section at once; the confirmation adds the first section later. A repeated fact (a second confirmation or withdrawal,
the same move twice) changes nothing, and the latest `student_name` wins by envelope `occurred_at`. A registration
always has the same `person_id` and offering; an event naming others is refused. The confirmation's `section_id` is
trusted over a move's `from_section_id`.


## Original submission (PR #459)

The nine points below are as submitted with PR #459. Where section A now records an answer, A is current.

Contract check run on the three files: 31 operations, unique operation ids, every `x-permission` is in
`permissions.yaml`, every `$ref` resolves, every role grant names a catalogue key.

## 1. Percentage when no class was counted

- **Contract:** `OfferingAttendance.percentage` and the student summary's `overall_percentage` are numbers; `percentage`
  is required.
- **Implemented now:** the domain returns `None` when no class is held (all excused or no closed session), and never
  flags that student as short. FR-18 reports the case as `no_eligible_classes`.
- **Proposal:** make `percentage` nullable in the contract and show "no classes yet" in the widget. Alternative: `0`,
  which reads as a shortage.
- **Needs:** reviewer choice; a contract change if nullable.

## 2. Date range for generating classes and publishing

- **Contract/PRD:** publishing generates classes (FR-3, FR-5); `generate-classes` takes a range. Slots carry only
  optional `effective_from` / `effective_to`. No academic-period dates exist in the PRD's read models.
- **Implemented now:** generation takes an explicit `first` and `last` date and narrows them by the slot's effective
  dates. It does not know where the range comes from.
- **Proposal:** (a) academic-management publishes period start and end dates, cached in a read model; or (b) publish
  requires the range in the request. Neither is built.
- **Needs:** the source of period dates (academic-management owner, Q1).

## 3. Cancelling a class that has an open attendance session

- **Contract:** cancelling is refused only when the class has a *closed* session.
- **Implemented now:** a class with an open session can be cancelled; the session is not touched by the domain.
- **Proposal:** close the open session when its class is cancelled (unmarked students would then become absent, which
  is wrong for a cancelled class), or refuse the cancellation while a session is open. Neither is built.
- **Needs:** reviewer choice.

## 4. Trusted source of instructor assignments and eligible students

- **PRD:** `instructor_id` comes from the instructor-assignment read model, and the eligible students from the
  section-allocation read model; both are filled from other modules' events, whose names are still unconfirmed
  (Q1, Q2, Q3).
- **Implemented now:** the four tables exist (`offering_ref`, `section_ref`, `assignment_ref`, `section_member`).
  Nothing writes them. The domain takes the resolved values as arguments. Slot validation against these tables is
  written but would answer 422 for every id until they are filled.
- **Not built, as instructed:** the event consumer, and any substitute API or event.
- **Needs:** event names and payloads from academic-management and enrolment-registration, and which id `student_id`
  is (Q3).

## 5. Trusted source of department-level authorization

- **PRD/contract:** HoD scope (department timetables, department reports, `correct-department`) needs the caller's
  department. Q9 is open with platform/identity.
- **Implemented now:** the domain has a `department` correction scope as an input only. The caller's department is
  not read from anywhere, and `department_id` is stored as a plain id, never as a grant.
- **Proposal:** none; no claim is assumed. Until Q9 is answered, department-scoped keys cannot be enforced as
  department-scoped.
- **Needs:** Faizan (platform/identity).

## 6. Eligibility for examinations: event or API

- **PRD:** examinations reads attendance through `POST /reports/attendance-eligibility` (FR-18, decided C7); how the
  population and the minimum are decided is open (Q4, Q5).
- **Implemented now:** the arithmetic only (present plus late over classes not excused; `no_eligible_classes` flag).
  No endpoint, no event, no consumer.
- **Needs:** the examinations owner and Faizan (Q4, Q5), after the allocation events (item 4).

## 7. Missing 401/403 responses and unused permission keys

- **Contract today:** 22 of 31 operations declare no 403, and none declares a 401. The 9 that do: open and close
  session, list and mark records, correct record, both student reports, department report, eligibility.
  academic-management declared 403 everywhere in #235 and tests that every route matches its contract.
- **Unused keys:** `attendance-session:override`, `attendance-record:correct-department` and `report:read-all` appear
  in no `x-permission`. They widen scope; academic-management lists widening keys with `x-permission-any`.
- **Implemented now:** nothing; the API layer is not written.
- **Proposal:** a separate `contract/timetable-attendance/...` PR that adds the 401 and 403 responses and
  `x-permission-any` for the widening keys. Needs the consumers' owners as second reviewers if they use the
  contract.

## 8. Student access to `/reports/students/{id}/...`

- **Contract:** both endpoints require `report:read-department`. A student holds only `report:read-own`, and reads
  their own data through `/me/attendance-summary` and `/me/attendance-history`.
- **Implemented now:** nothing.
- **Question:** is that intended (students use `/me/...` only), and how is a HoD limited to their department (item 5)?
  If students should also use the `{student_id}` path for themselves, the key needs `report:read-own` with an own-id
  check.
- **Needs:** reviewer choice.

## 9. Deviations from the PRD (implemented now)

| PRD | Implemented | Why |
|---|---|---|
| "Own schema `timetable_attendance`" (section 8) | Table prefix `timetable_attendance_` and own version table `timetable_attendance_alembic_version` | The convention of every module with a backend; `module-standard.md` rule 2 still says one schema. |
| `instructor_assignment_ref` | `assignment_ref` | PostgreSQL rejects the generated index name (65 characters over the 63 limit). |
| `attendance_record_change` | `record_change` | The same limit (66 characters). |
| Audit written to `platform/audit` through `packages/sdk` (FR-16) | Interim table `timetable_attendance_audit_entry`, shaped like platform/audit's `Record`, to be backfilled by `client_token` | The SDK does not exist; the same approach as academic-management. |
| Eligible students "snapshotted" at open; table not specified | `attendance_record` rows are created at open with a NULL status; closing turns NULL into `absent` | A stored snapshot is needed for the counts; no separate table. |
| `slot_id` on a scheduled class (foreign key implied) | Plain id, no foreign key | Replacing slots must not orphan classes already taught. |

Other choices made in the domain, also unreviewed: a slot's section must belong to its offering and its assignment
must match both; a conflict pair inside one timetable is reported once with the lower slot id first; location labels
compare ignoring case and spacing; a correction to the same status is a 400.

## 10. Publish and unpublish (implemented), class generation (not built)

Implemented in the publication PR (issue #325), from the reviewed rules and the contract:

- **Publish** (`POST /timetables/{id}/publish`): refused with 409 when the timetable is already published
  (`already_published`), when a blocking conflict remains (`blocking_conflicts`, with `details.conflicts` listing them, as
  the contract says "409 and the conflict list"), or when the academic period is not a known term (`unknown_term`).
  The unknown-term refusal is 409 because that is the contract's declared status for publish; the contract declares no
  422 for it. Success raises the version by one and sets `published_at`.
- **Unpublish** (`POST /timetables/{id}/unpublish`): only from `published` (409 `not_published`); the version stays.
  It cancels the timetable's scheduled classes that start after now and have no attendance session (open or closed),
  one audit entry and one `scheduled-class.cancelled` event per class; past classes, classes that already started,
  completed or cancelled classes and ad-hoc classes of other timetables are not touched. A class starting exactly now
  is not in the future. The optional `reason` (1 to 500 characters) is recorded as the classes' cancel reason and on
  the audit entries.
- Every write is audited and its event published in the same transaction as the change, and any failure rolls all of
  it back, including a failure on the second of several class cancellations.

**Not built, and why:** the contract says publishing generates the scheduled classes, and `generate-classes` is its own
operation. Both need each slot's wall-clock times (`09:00`) as instants, "in the organisation's time zone" (contract),
and the repository has no source for an organisation's time zone (no module setting, no platform setting, nothing in
the PRD or in the decisions above). It was asked and the decision was to leave generation out rather than assume UTC.
Until it is decided and built, publishing creates no class (`scheduled_class_count: 0` in the event), and unpublishing
has classes to cancel only if they were created some other way.

| Open point | Owner | Effect |
|---|---|---|
| The organisation's time zone: where it is stored and how the module reads it | Faizan (platform), with Shivani | `generate-classes` and the generation step of publish are not built; the contract's description of publish is not met until then |
