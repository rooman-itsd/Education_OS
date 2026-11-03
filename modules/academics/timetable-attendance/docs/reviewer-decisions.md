# timetable-attendance: decisions for the reviewer

Issue #325 · Reviewer: @praveen-rooman · Raised by: Shivani

Status of this page: **nothing below is decided.** "Implemented now" is what the code on this branch does today
(domain and database foundations, no API yet). "Proposal" is the author's suggestion; it is not agreed and nothing
depends on it being accepted. The contracts (`contracts/*.yaml`) are unchanged by this work.

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
