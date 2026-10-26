# academic-management: user stories

Stories by role, from [prd.md](prd.md). Each acceptance criterion is testable and names the requirement
(FR-n) and the contract response it relies on (`contracts/openapi.yaml`). Every story runs inside one
organisation: data of another organisation is never read or changed (PRD section 10).

**Status** says where each story stands in code:
- **API**: served end to end: domain rules, use case, persistence (prefixed tables with row-level security) and the
  route of `contracts/openapi.yaml`, with API tests on a throwaway database (`backend/tests/test_api_*.py`).
- **Partial**: served, with the named part still waiting for shared work (prd.md section 13).

Roles are platform role ids. `contracts/permissions.yaml` grants each key to the role blocks `org-admin`,
`department-admin`, `faculty`, `student` and `examination-staff`; each story names the key it needs.

## Org admin (`org-admin`)

### AM-1 Set up terms (FR-1, FR-2) · API
As an org admin, I create the academic terms of my organisation and activate the current one, so that
offerings and other modules know which term is running.
- A term needs code, name, start date and end date; an end date before the start date is refused (400 `invalid_term_dates`).
- Single-day terms are allowed.
- Term dates may not overlap another term of the organisation, both ends inclusive (409 `term_dates_overlap`); the error names every clashing term.
- Activating a term closes every other active term, so exactly one term is active; activating the active term changes nothing.
- Activating an unknown term is 404 `term_not_found`.
- Activation publishes `academic-management.term.activated` in the same transaction.

### AM-2 Maintain programmes (FR-3) · API
As an org admin, I record each programme with its level, duration in terms and total credits.
- Level is one of `certificate`, `diploma`, `undergraduate`, `postgraduate`, `doctoral`, `other` (400 `invalid_choice` otherwise).
- Duration is a whole number of terms, at least 1; credits required are a number, at least 0.
- A programme code is unique in the organisation (409 `duplicate_code`); comparison is exact.
- Archiving an archived programme succeeds and changes nothing.

### AM-3 Publish a curriculum (FR-4, FR-5) · API
As an org admin, I publish a curriculum version so students and other modules see a fixed programme structure.
- Each item names a course, a programme term between 1 and the programme's duration, a category `core` or `elective`, and credits of at least 0.
- Publishing re-checks every item against the programme as it is now; a failure names the item (422, `details.field` like `items[0].programme_term`).
- The items' credits must add up exactly to the programme's credits required (422 `credits_mismatch`); core and elective items both count.
- A published curriculum cannot change (409 `curriculum_published`); a change is a new version numbered after the highest existing version.

### AM-4 Keep the course catalogue (FR-6, FR-7) · API
As an org admin, I keep one catalogue of courses for the organisation.
- A course code is unique in the organisation (409 `duplicate_code`).
- Credits and lecture and practical hours are numbers of at least 0; hours are optional.
- `course_type` is one of `theory`, `practical`, `practicum`, `project`, `studio`.
- Courses are archived, never deleted; archiving twice is not an error.

## Department admin, HoD (`department-admin`)

### AM-5 Plan offerings and sections (FR-8, FR-9, FR-10) · Partial
As a HoD, I offer a course in a term, split into sections, and move the offering through its life cycle.
- An offering needs at least one section (400 `sections_required`); each section's capacity is a whole number of at least 1, and an error names the section (`sections[1].capacity`).
- An archived course cannot be offered (409 `course_archived`).
- Status moves only planned → open → in_progress → completed, or planned or open → cancelled (409 `invalid_status_transition` otherwise).
- Opening needs exactly one active primary faculty assignment (409 `primary_required`).
- Sections can be added only while the offering is planned or open (409 `offering_not_editable`).
- A section is never deleted (the contract has no delete): one with enrolled students is closed, keeps its roster and takes no new registrations.
- Department scoping is not enforced: no trusted department claim exists yet (prd.md section 13).

### AM-6 Assign faculty (FR-11, FR-12) · API
As a HoD, I assign faculty to an offering or one of its sections with a role and weekly contact hours.
- Role is `primary`, `co_instructor` or `teaching_assistant`; contact hours are at least 0.
- A section, when given, belongs to the offering (400 `section_not_in_offering`).
- Once an offering is open, in progress or completed, a second active primary is refused (409 `primary_already_assigned`) and its primary cannot be ended (409 `primary_required`).
- Ending an ended assignment is 409 `assignment_ended`.
- The faculty member is the platform/identity user id, `faculty_id`.

### AM-7 Watch faculty load (FR-13) · Partial
As a HoD, I see each faculty member's weekly teaching load for a term against the organisation's maximum, so
that I can rebalance before the term starts.
- Without the `academic-management:faculty-load:read` key the request is 403 `forbidden`.
- Without a term in the request and with no active term, the answer is 404 `active_term_not_found`.
- Load is the sum of contact hours of active `primary` and `co_instructor` assignments; `teaching_assistant` hours and ended assignments do not count.
- A faculty member with no counted assignment is not listed.
- A faculty member over `ACADEMIC_MANAGEMENT_MAX_WEEKLY_CONTACT_HOURS` (default 18) is flagged `over_load`, not refused; exactly at the maximum is not over it.
- Rows are ordered over-load first, then by contact hours descending.
- `faculty_count` and `over_load_count` stay the same when `over_load_only=true` narrows the rows.
- The report carries the term's id, code and name and each faculty member's name.
- `department_id` narrows the report and is never proof of access; access is the `faculty-load:read` key alone. The default department (the caller's own) waits for a trusted department claim.
- Faculty names come from an identity lookup that does not exist yet; until it does, the route answers 503 `faculty_directory_unavailable` rather than showing ids as names.

## Faculty (`faculty`)

### AM-8 See my offerings and rosters (FR-14, FR-15) · Partial
As a faculty member, I see the offerings I teach and the students enrolled in each section.
- I see only offerings I am assigned to (`academic-management:roster:read`); department-wide reading needs `academic-management:roster:read-all`.
- Each roster entry identifies the learner by `person_id`, with section and enrolment time.
- The roster is built only from enrolment-registration's events; academic-management never writes enrolment.
- Built from the events agreed with enrolment-registration, upserted by `registration_id`: duplicates are applied once, a withdrawal keeps the row as withdrawn, a section change moves the same registration, `roll_number` is optional, and closed offerings and closed or full sections take no new registration.
- `roster:read-all` reads every roster of the organisation: department restriction waits for a trusted department claim.
- The consumer is subscribed once enrolment-registration publishes its `events.yaml` and the event relay exists.

## Every reader (`student`, `examination-staff` and the roles above)

### AM-9 Read the catalogue · API
As a student or examination staff member, I read programmes, published curricula, courses and offerings.
- Reads need the matching `:read` key; lists are paginated with `limit`, `offset` and `total`.
- Examination staff read course code, title, credits and department; assessment schemes belong to `academics/examinations`.
- `student` and `examination-staff` hold the read keys of the catalogue.

## Every change

### AM-10 Audit and events (FR-9, FR-16) · Partial
- Every state change, including roster changes applied from enrolment events, writes an `academic_management_audit_entry` row in the same transaction, shaped like platform/audit's `Record`: `client_token`, action, `entity_type`, entity id, a one-line summary and the changed fields before and after (never names, roll numbers or descriptions), plus the reason for an offering status change. A change that alters nothing writes no row; a replayed `client_token` returns the original row. Writing to `platform/audit` waits for the audit SDK; the rows are then backfilled with their tokens.
- Every state change publishes the matching event of `contracts/events.yaml` in the same transaction (`eos_core.events.publish`). The envelope `version` is not set yet: the shared outbox has no version column (Faizan).
