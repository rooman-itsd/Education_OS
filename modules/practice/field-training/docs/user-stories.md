# field-training: user stories

Owner: Tejaswini (@tejaswini-rooman) · Status: draft for review · Issue #339

Stories by role for the field-training module. Each story follows `prd.md` and is bounded by the contract in
`contracts/openapi.yaml` (0.1.0), `events.yaml` and `permissions.yaml`; where a need is not in the contract it is
listed under [Gaps](#gaps-not-in-the-contract) instead of being written as a story. Paths are relative to
`/api/v1/field-training`. The words placement, site and supervisor are the generic ones; each academy's profile
vocabulary (`field-training.placement`, `.site`, `.supervisor`) renames them on screen.

## Roles

| Role (`permissions.yaml`) | Who | Grants |
|---|---|---|
| `field-training-coordinator` | Placement or practicum coordinator (hospital-coordinator, practicum-coordinator, industry-coordinator, placement-officer, moot-court-coordinator) | `site:read`, `site:manage`, `opening:read`, `opening:manage`, `placement:read`, `placement:manage` |
| `field-training-supervisor` | Supervisor at a site (clinical-supervisor, mentor-teacher, farm-supervisor, legal-mentor, corporate-mentor, design-mentor, project-guide) | `site:read`, `supervision:read`, `log:verify`, `assessment:record` |
| `field-training-trainee` | Learner on placements (medical-student, teacher-trainee, field-trainee, law-student, engineering-student, management-student, ...) | `self:read`, `self:apply`, `self:log` |
| `field-training-viewer` | Management, department and org admin, read only (also industry-liaison, research-lead) | `site:read`, `opening:read`, `placement:read` |

All keys above are short for `field-training:<resource>:<action>`. Each academy role holds the module roles its
dashboard layout lists in `module_roles` (`platform/identity/config/dashboards/<role>.yaml`). A call without a key
the contract names for its endpoint is refused with 403 and changes nothing.

## Rules every story inherits

- **R1 Tenant isolation.** Every record carries `organisation_id` and is protected by row-level security. Another
  organisation's record is never listed, and a request for it by id answers 404. The cross-tenant leak test passes.
- **R2 Events carry the tenant** and only ids, dates, hours and outcomes: log text and assessment comments are
  never published.
- **R3 Audit.** Every state change writes an audit record with the actor (module-local audit table until the audit
  SDK ships).
- **R4 Nothing is deleted.** Openings are closed or cancelled, placements rejected, withdrawn or completed, log
  entries returned; sites are deactivated.
- **R5 Own records only.** A trainee sees only their own placements, logs, assessments and hours; another trainee's
  placement answers 404. A supervisor with only `supervision:read` sees only the placements they supervise and the
  openings at sites where they are a supervisor.
- **R6 Business dates** (today, a log entry's date, start and due dates) are Asia/Kolkata dates; timestamps are UTC.
- **R7 Hours** are in steps of 0.25, more than 0 and at most 24 per entry, and at most 24 per trainee per day.
- **R8 Clean refusals.** Ids are uuids, strings and numbers are bounded, dates fall in 1900 to 9998, NUL characters
  are refused: a bad request is a 422 (a NUL in the path a 404), never a 500.
- **R9 No dependency** on another module being enabled; no real trainee, patient, pupil or client data in tests.
- **R10 Nobody acts on their own placement.** Assigning, deciding (approve or reject), starting, changing and completing a
  placement answer 403 `own_placement` when the caller is its trainee, whatever other role they hold. A coordinator who
  is also a trainee still manages everyone else's placements, and withdraws their own only before it is active.

## 1. Sites

**SI-1 Record a site.** As a coordinator, I add a host site with a name, the organisation's own `kind` label,
address, contact and the supervisors attached to it (`POST /sites`, `site:manage`).
- Name 1 to 200 characters; contact email well formed; supervisors are person ids, each once.

**SI-2 Change or deactivate a site.** `PATCH /sites/{id}` updates the fields given, replaces the supervisors when
`supervisor_ids` is sent, and `active: false` deactivates it. An inactive site takes no new openings (409
`site_inactive`).

**SI-3 Find a site.** Anyone with `site:read` lists sites (`?active=`, `?q=` name contains, wildcards taken
literally) and reads one (`GET /sites/{id}`).

## 2. Openings

**OP-1 Create an opening.** As a coordinator, I create an opening in draft at an active site: title, discipline label,
period, seats (1 to 10 000), required hours, eligibility notes, supervisors, and whether trainees may apply
(`POST /openings`). The end is not before the start (422).

**OP-2 Publish, close, cancel.** `publish` (draft → open) publishes `field-training.opening.published`; `close`
(open → closed) publishes `field-training.opening.closed` and existing placements continue; `cancel` needs a reason,
withdraws the opening's requested and assigned placements (each publishes `field-training.placement.withdrawn`),
publishes `field-training.opening.cancelled`, and is refused (409 `placement_active`) while a placement is active.
A transition from the wrong status answers 409.

**OP-3 Change an opening.** `PATCH /openings/{id}` replaces the opening. Seats cannot drop below seats filled (409
`seats_below_filled`); the period and site cannot change once a placement has started, nor leave a requested or
assigned placement outside the period (409 `period_locked`). Placements not yet started follow a new requirement. A
cancelled opening cannot change.

**OP-4 See openings.** `GET /openings` filters by status, site, `has_seats`, `starts_after`, paged with a cursor.
Seats filled count assigned, active and completed placements. With `opening:read` every opening is listed; with only
`supervision:read`, openings at sites where the caller is a supervisor; with only `self:apply`, open openings that
accept applications. `GET /openings/{id}` needs `opening:read` or `supervision:read` (the latter for own sites).

## 3. Placements

**PL-1 Assign.** As a coordinator, I assign a trainee to an open opening (`POST /placements`, → assigned). The period
defaults to the opening's and must fall inside it (422); the supervisor defaults to the opening's first supervisor
and is never the trainee. Refused (409) when the opening is not open, has no seat left (`no_seats`), the trainee
already holds a placement or application in it (`already_applied`), or overlaps another of their requested, assigned
or active placements (`overlapping_placement`). Publishes `field-training.placement.assigned`.

**PL-2 Apply.** As a trainee, I apply for an open opening that accepts applications, with an optional statement of up
to 2000 characters (`POST /openings/{id}/apply`, → requested). Same refusals as PL-1, plus
`applications_not_allowed`. A request holds no seat. Publishes `field-training.placement.requested`. After a
rejection or withdrawal I may apply again.

**PL-3 Decide.** As a coordinator, I approve (→ assigned, needs a seat and an open opening, may set the supervisor)
or reject (needs a reason of at least 3 characters) an application. Publishes `field-training.placement.assigned` or
`field-training.placement.rejected`. Deciding anything but a request answers 409.

**PL-4 Start.** The daily job starts assigned placements on their start date; a coordinator can start one early
(`POST /placements/{id}/start`). Publishes `field-training.placement.started` (the supervisor is notified from it).

**PL-5 Change supervisor or dates.** `PATCH /placements/{id}` on a placement not yet completed: dates inside the
opening, no overlap with the trainee's other placements, and an active placement keeps every logged day inside it
(409 otherwise).

**PL-6 Withdraw.** A coordinator withdraws any placement before completion; a trainee withdraws their own before it
is active (an active one answers 403; someone else's 404). A reason of at least 3 characters; the seat is freed;
publishes `field-training.placement.withdrawn` with `was_active`.

**PL-7 See placements.** `GET /placements` filters by status, opening, site, trainee and supervisor, paged. A caller
with only `supervision:read` sees the placements they supervise. `GET /placements/{id}` returns the hours summary
(required, verified, pending) and the final outcome.

## 4. Logbook

**LB-1 Log hours.** As a trainee on an active placement, I add an entry: date, hours, activities (up to 4000
characters, no third-party personal data), optional reflection (`POST /placements/{id}/logs`). The date falls
inside the placement (from the day it started when started early) and not in the future; my day stays at or under
24 hours (409 `date_outside_placement`, `date_in_future`, `day_over_24_hours`; 409 `placement_not_active`).
Publishes `field-training.log.submitted`.

**LB-2 Correct an entry.** I edit a submitted or returned entry (`PATCH /logs/{id}`); a returned entry goes back to
submitted and publishes `field-training.log.submitted` again. A verified entry is locked (409 `entry_verified`).

**LB-3 Verify or return.** As the placement's supervisor, I verify an entry (its hours now count; publishes
`field-training.log.verified`) or return it with a reason (publishes `field-training.log.returned`). Another
supervisor, or the trainee themself, gets 403 (`not_supervisor`, `own_entry`); an entry not submitted, or a
placement no longer active, answers 409.

**LB-4 Read the logbook.** `GET /placements/{id}/logs` (newest first, `?status=`) with the same visibility as the
placement.

## 5. Assessments and completion

**AS-1 Assess.** As the placement's supervisor, I record a mid (optional, may repeat) or final assessment of an active
placement: outcome on the organisation's scale (up to 200 characters), optional score 0 to 100, comments. One final
per placement (409 `final_recorded`). Publishes `field-training.assessment.recorded`. Rubric-based skill assessment
is skill-progress's.

**AS-2 Read assessments.** `GET /placements/{id}/assessments`, mid first, same visibility as the placement.

**CO-1 Complete.** As a coordinator, I complete an active placement (`POST /placements/{id}/complete`). Refused with the
contract's Refusal body: `not-active`, `no-final-assessment`, `hours-short` (verified below required, without
override), `reason-required` (override without a reason). Completing short of the hours with an override records the
reason. Publishes `field-training.placement.completed` with verified and required hours, final outcome and
`hours_overridden`. A completed placement keeps its seat.

## 6. Self-service

**ME-1 My placements.** `GET /me/placements`: active first, then upcoming soonest first, then requested;
`include_past=true` adds completed, rejected and withdrawn, newest first.

**ME-2 My hours.** `GET /me/hours`: for the active placement, else the most recent, else zeros with
`placement_id: null`: required, verified, awaiting verification and returned hours, plus the last 14 days by date
(today included, Asia/Kolkata). `?placement_id=` picks one of my own placements; another's answers 404.

**ME-3 My trainees.** `GET /me/trainees` (`supervision:read`): active placements I supervise with entries awaiting
verification or a final assessment due (within 7 days of the end date or past it, none recorded), final due first,
then nearest end date, then most entries; `limit` 1 to 100.

## 7. Widgets

Each widget declares the one key behind the endpoint it calls, shows a loading state, an empty state, the data, and
an error state: "Field training data is not available yet." with a retry (404, 502, 503, network), "Sign in again to
see this." (401) or "You do not have access to this." (403) without a retry, otherwise "Could not load ...".

| Widget | Key | Endpoint | Shows |
|---|---|---|---|
| `field-training.my-placement` | `self:read` | `GET /me/placements` | Up to three placements with period, site, status, and verified against required hours for the active one |
| `field-training.hours-logged` | `self:read` | `GET /me/hours` | Verified of required hours with a bar, awaiting and returned hours, hours of the last 14 days |
| `field-training.trainees-to-assess` | `supervision:read` | `GET /me/trainees` | Trainees with a final assessment due or entries to verify |
| `field-training.placements-open` | `opening:read` | `GET /openings?status=open&has_seats=true` | Open openings with seats left, soonest first |
| `field-training.active-placements` | `placement:read` | `GET /placements?status=active` | Placements under way with verified hours |

## 8. Daily job

**JB-1 Start placements.** Once a day after midnight Asia/Kolkata, assigned placements whose start date has come
become active, dated that day, and `field-training.placement.started` goes out once each.

## Gaps (not in the contract)

- `trainee_name` and `supervisor_name` are null: the module consumes no student-information or hr-payroll events yet.
- Notifications (opening published, application received, entry returned, placement started) are left to the
  notification service reading the events.
- Attachments on log entries (PRD open question 3) and screens for coordinators, supervisors and trainees are a later
  wave; only the five widgets are built.
