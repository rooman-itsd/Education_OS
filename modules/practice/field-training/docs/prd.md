# field-training: product requirements

Owner: Tejaswini (@tejaswini-rooman) · Status: draft for review · Issue #67
Practice suite · tier `common` (every academy type enables it) · generic pattern "Field training"

## Purpose

One module for every kind of supervised training a learner does away from the classroom at a host site:
clinical rotations, school internships, industrial training, farm rotations, legal clinics, industry
internships. The module knows only the generic pattern: **sites** offer **openings**, a **trainee** is
given a **placement** in an opening, logs **hours and activities** that a **supervisor** verifies, and is
**assessed** at the end. The contract is `contracts/openapi.yaml`, `events.yaml` and `permissions.yaml`.

## Vocabulary, not field words

The contract uses only the generic words above. What a learner sees comes from the academy profile
(`platform/identity/config/profiles/<profile>.yaml`, key `field-training.<term>`):

| Term key | Generic word | Examples from the profiles |
|---|---|---|
| `field-training.placement` | Placement | Clinical rotation, School internship, Industrial training, Farm / practical rotation, Legal internship / clinic, Internship |
| `field-training.site` | Site | Hospital ward, partner school, plant, farm, court or law firm (not yet in any profile) |
| `field-training.supervisor` | Supervisor | Clinical supervisor, mentor teacher, industry mentor, farm supervisor (not yet in any profile) |

Free-text labels inside the data (a site's `kind`, an opening's `discipline`, an assessment's `outcome`
scale) are set by each organisation, never by the module. No academy type is named in code or contract.

## Users and what they need

Role ids are those of the dashboard layouts. Any academy's roles map onto the four generic actors.

| Generic actor | Example roles | Needs | Dashboard widget |
|---|---|---|---|
| Trainee | medical-student, teacher-trainee, field-trainee, law-student, engineering-student, management-student | See current and upcoming placements, apply for openings, log hours and activities, see verified hours against the requirement | `field-training.my-placement` (`GET /me/placements`), `field-training.hours-logged` (`GET /me/hours`) |
| Supervisor | clinical-supervisor, mentor-teacher, farm-supervisor, legal-mentor, corporate-mentor, design-mentor, project-guide | Verify or return log entries, assess assigned trainees, see open openings at their site | `field-training.trainees-to-assess` (`GET /me/trainees`), `field-training.placements-open` (`GET /openings?status=open`) |
| Coordinator | hospital-coordinator, practicum-coordinator, industry-coordinator, placement-officer, industry-liaison, moot-court-coordinator, research-lead | Manage sites and openings, assign and approve placements, watch active placements | `field-training.active-placements` (`GET /placements?status=active`), `field-training.placements-open` |
| Viewer | management, department-admin, org-admin | Overview, read only | — |

## Main flows

1. **Sites.** A coordinator records host sites: name, kind (organisation's label), address, contact, and the
   supervisors attached to it (`person_id`s). A site can be deactivated.
2. **Openings.** A coordinator creates an opening at a site: title, discipline (label), period, seats,
   required hours, eligibility notes, supervisors, and whether trainees may apply. Draft → open (published)
   → closed. A cancelled opening withdraws its unstarted placements.
3. **Placement.** Either the coordinator assigns a trainee to an opening (`assigned` at once), or a trainee
   applies to an open opening that allows it (`requested`), and the coordinator approves or rejects.
   Seats are never over-filled. A trainee cannot hold two placements with overlapping periods.
4. **Start.** A daily job moves assigned placements to `active` on their start date; the coordinator can
   also start one early. The supervisor is notified.
5. **Logbook.** During an active placement the trainee adds log entries: date, hours, activities, optional
   reflection. The supervisor verifies or returns each one (with a reason); a returned entry can be edited and
   resubmitted. Verified entries are locked. Hours count toward the requirement only when verified.
6. **Assessment.** The supervisor records a mid-placement (optional) and a final assessment: outcome on the
   organisation's scale, optional score, comments. Detailed rubric-based skill assessment belongs to
   skill-progress; field-training records the placement outcome only.
7. **Complete.** The coordinator completes the placement once a final assessment exists and verified hours
   meet the requirement; completing short of the hours needs an override reason. A trainee or coordinator can
   withdraw a placement before completion, with a reason.

## Rules

- Every table carries `organisation_id` with row-level security; every event carries `organisation_id`.
- Every state change writes an audit record through `packages/sdk`.
- A trainee sees only their own placements, logs and assessments (`/me/*`). A supervisor sees only placements
  they supervise unless they also hold coordinator permissions.
- A supervisor never verifies their own log entries or assesses a placement where they are the trainee.
- Hours are decimals in steps of 0.25, at most 24 per entry and per day.
- Nothing is deleted: placements are withdrawn or completed, entries returned, openings closed or cancelled.
- No real trainee, patient, pupil or client data in tests or seeds, and log entries must not carry it: the UI
  warns, and the contract has no field for third-party personal data.
- No dependency on another module being enabled. skill-progress, productions or projects may react to
  field-training events if they are enabled.

## Data model (summary)

| Entity | Key fields |
|---|---|
| Site | id, name, kind, address, contact_name, contact_email, supervisor_ids, active |
| Opening | id, site_id, title, discipline, starts_on, ends_on, seats, seats_filled, required_hours, allow_applications, supervisor_ids, status (draft, open, closed, cancelled) |
| Placement | id, opening_id, trainee_id, supervisor_id, starts_on, ends_on, required_hours, verified_hours, status (requested, assigned, active, completed, rejected, withdrawn) |
| LogEntry | id, placement_id, date, hours, activities, reflection, status (submitted, verified, returned), verified_by, return_reason |
| Assessment | id, placement_id, assessor_id, stage (mid, final), outcome, score, comments, recorded_at |

## Integration points

| Direction | With | How |
|---|---|---|
| Publishes | skill-progress, portfolio and anyone | `field-training.placement.*`, `log.*`, `assessment.recorded` and the rest of `events.yaml` |
| Platform | identity, audit, notification, scheduler | through `packages/sdk` (vocabulary from the profile, notifications, the daily start job) |
| References | student-information, hr-payroll | `trainee_id` and `supervisor_id` are `person_id`s; names cached from their events |

## Out of scope

- Paid job placement drives and offers (placement-career).
- Rubric-based skill and competency assessment (skill-progress).
- Attendance in timetabled classes (timetable-attendance); site timetables and shift rosters.
- Agreements and MoUs with host sites as documents (platform/documents holds the files; a later version may link them).
- Any field-specific rule, such as a medical council's case-log categories. If one is needed, it is a profile
  setting or a specialized module, not a change to this generic one.

## Open questions (for review)

1. Add `field-training.site` and `field-training.supervisor` to the profiles' vocabulary? Profiles are owned by
   Faizan; this PR does not change them, and the UI falls back to the generic word.
2. Should a supervisor who holds only `field-training:supervision:read` see the whole open-openings list for their
   site, or only openings they are named on? Proposed: openings at sites where they are a supervisor.
3. Should log entries accept attachments (through platform/documents) in wave A, or later?
