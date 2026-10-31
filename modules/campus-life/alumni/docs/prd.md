# alumni: product requirements

Owner: Gokula Lakshmi (@gokulalakshmirooman-source) · Status: draft for review · Issue #337 (was #133)
Suite: campus life · tier `common`

## Purpose

A directory of the institution's alumni, kept by staff, and alumni mentoring: staff assign an alumnus as mentor to a
student, and the student sees their mentor and upcoming sessions on the dashboard. Management institutes name
"alumni mentoring" as part of corporate relations (`docs/architecture/institution-types.md`, lines 36 and 76).
Contract: `contracts/openapi.yaml`, `events.yaml`, `permissions.yaml`. Stories: [user-stories.md](user-stories.md).

No PRD existed for this module before; every rule below is an owner decision recorded on #337.

## Decisions

Decided by the owner; see [#337](https://github.com/rooman-itsd/Education_OS/issues/337).

| # | Decision |
|---|---|
| A1 | An alumnus is a directory record created by staff. Alumni have no login and no role. |
| A2 | A record created by staff is verified: `verified_by` and `verified_at` are set to the creator and the creation time. The columns stay so that self-registration with staff approval can come later without breaking the contract. |
| A3 | Staff assign a mentor to a student. Mentoring sessions are optional records that staff keep. |
| A4 | The placement officer runs the module through the module role `alumni-coordinator`, listed in the `placement-officer` layout's `module_roles`. |
| A5 | A mentor's contact details (email, phone, LinkedIn) are visible only to the student assigned to them and to staff. |
| A6 | v1.0 covers the directory and mentoring only. Alumni events, donations and engagement campaigns (named in the original module description) are v1.1. |

## Users

| Role | Module role | Needs | Dashboard widget |
|---|---|---|---|
| Placement officer (management-institute) | `alumni-coordinator` | Keep the directory, flag mentors, assign mentors to students, record sessions | — |
| Management student (management-institute) | `alumni-mentee` | See their mentor, the mentor's contact details and upcoming sessions | `alumni.mentoring` (`GET /me/mentoring`) on the management-student layout |

Other profiles list the module (`campus-life/alumni`) but map no profile role onto these module roles yet, so in v1.0
only management institutes use it.

## Main flows

1. **Directory.** The coordinator adds an alumnus: name and graduation year (required), programme, current company,
   designation, industry, city, and contact details (email, phone, LinkedIn). The record is verified on creation (A2).
   Records are edited, archived with an optional reason, and restored. Nothing is deleted.
2. **Mentor flag.** The coordinator marks an alumnus `is_mentor`. Only an active alumnus with the flag is assigned.
3. **Assignment.** The coordinator assigns a mentor to a student (the student's identity user id), with a start date
   (default today) and an optional focus. The assignment is active until the coordinator ends it.
4. **Sessions (optional).** On an active assignment the coordinator schedules sessions (date and time, duration,
   mode: in person, online or phone, location or link, topic), edits or cancels them, and marks them completed with
   staff-only notes.
5. **Student view.** The student's `alumni.mentoring` widget shows their active mentor (name, company, designation,
   contact details) and up to five upcoming sessions. With no active mentor it shows an empty state.

## Rules

- Students do not browse the directory. `alumni:self:read` returns only the caller's own active assignment (A5).
- A mentor's contact details are returned to staff (`alumni:directory:read`, `alumni:mentoring:read`) and, through
  `GET /me/mentoring`, to the student on the mentor's active assignment only. Once an assignment ends, the student no
  longer sees that mentor (A5).
- Staff notes on an alumnus or a session are never returned to students.
- A student has at most one active assignment (409 `student_already_assigned`). A mentor may have several.
- A mentor with an active assignment is not archived, and their mentor flag is not cleared, until the assignment ends
  (409 `mentor_has_active_assignments`).
- Ending an assignment cancels its scheduled sessions.
- Event payloads carry ids only, no names or contact details.
- Every table carries `organisation_id` with row-level security; every event carries `organisation_id`.
- Every state change writes an audit record through `packages/sdk`.
- Timestamps are UTC.

## Data model (for the backend PR)

Schema `alumni`, one Alembic chain, every table with `organisation_id` and an RLS policy on `app.organisation_id`.

| Table | Holds |
|---|---|
| `alumni_alumnus` | The directory record, `is_mentor`, `status` (active, archived), `created_by`, `verified_by`, `verified_at`, `archived_at`, `archive_reason` |
| `alumni_mentoring_assignment` | `mentor_id` (alumnus), `student_id` (identity user id, no foreign key), `student_name`, `started_on`, `ended_on`, `status`, `focus`, `assigned_by`, `end_reason`. A partial unique index keeps one active assignment per student and organisation |
| `alumni_mentoring_session` | `assignment_id`, `scheduled_at`, `duration_minutes`, `mode`, `location`, `topic`, `status`, `notes`, `cancel_reason`, `created_by` |

## Integration points

| Direction | With | How |
|---|---|---|
| Publishes | none in v1.0 | `alumnus.added`, `alumnus.archived`, `mentoring-assignment.started`/`ended`, `mentoring-session.scheduled`/`completed`/`cancelled`. No module consumes them yet; notification may later. |
| Consumes | none | |
| Platform | identity, audit | through `packages/sdk` |

## Out of scope (v1.0)

- Alumni logins, self-registration and self-service profiles (A1).
- Students browsing the directory or requesting a mentor (A3).
- Automatic matching of mentors to students.
- Creating alumni from a graduation event (student-lifecycle publishes none).
- Alumni events, donations and engagement campaigns (A6, v1.1).
- Notifications to students about assignments or sessions.

## Open questions (for review)

1. `student_id` is not checked against identity until `packages/sdk` offers a user lookup; the coordinator's screen
   picks the student from identity's user list.
2. Consent: the PRD records no consent rule for keeping an alumnus's contact details. Staff are expected to hold the
   alumnus's consent before adding contact details; whether the record should store it is for review.
3. Erasure: records are archived, never deleted. Whether an alumnus's request to be removed needs a hard delete is
   for review.
4. Duplicate records (the same person added twice) are not detected in v1.0.
