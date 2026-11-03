# timetable-attendance: decisions for the reviewer

Issue #325 · Reviewer: @praveen-rooman · Raised by: Shivani

This page has four parts: the decisions the reviewer has confirmed, what is still unresolved, the design choices the
code has made that nobody has reviewed, and the original nine points as submitted with PR #459 (sections 1 to 9, which
describe the code as it was then). The contracts (`contracts/*.yaml`) have not been changed by any of this work.
Times are UTC.

## A. Confirmed by the reviewer

Praveen's review of PR #459
([comment 6598201117, 2026-11-03T07:45Z](https://github.com/rooman-itsd/Education_OS/pull/459#issuecomment-6598201117)),
where he approved the PR and asked for these to be recorded. "Contract change" means a change to
`contracts/*.yaml`, to be made in a separate `contract/timetable-attendance/...` PR.

| Point | Confirmed decision | Status in the code |
|---|---|---|
| Percentage with no counted class (section 1) | `null`, plus the `no_eligible_classes` flag | Domain already returns `None`. **Contract change** (nullable `percentage`) not made yet |
| Date range for generating classes (section 2) | Keep a `term_ref`; generate inside the term, narrowed by each slot's effective dates; refuse to publish if the term is unknown. `academic-management.term.created` carries `starts_on` and `ends_on` | `term_ref` and its `term.created` consumer exist (this PR). Generation and publish are not built |
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
| Whether `student_id` is the `person_id` carried by the enrolment events (Praveen proposed it and asked for Faizan's confirmation under Q3) | Faizan | **The enrolment-registration consumers are not implemented**, so `section_member` is never filled |
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
