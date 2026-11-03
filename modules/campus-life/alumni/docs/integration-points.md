# alumni: integration points

## Published events

Written to the `eos_core` outbox in the same transaction as the change; platform/event-bus relays them. Payloads are
exactly those of [`contracts/events.yaml`](../contracts/events.yaml): ids, dates and the session mode, never names,
contact details or notes. No module consumes them in v1.0; notification may later (PRD).

| Event | When | Payload |
|---|---|---|
| `alumni.alumnus.added` | `POST /directory` | `organisation_id`, `alumnus_id`, `graduation_year`, `is_mentor`, `verified_by` |
| `alumni.alumnus.archived` | `POST /directory/{id}/archive` | `organisation_id`, `alumnus_id` |
| `alumni.alumnus.restored` | `POST /directory/{id}/restore` | `organisation_id`, `alumnus_id` |
| `alumni.mentoring-assignment.started` | `POST /mentoring/assignments` | `organisation_id`, `assignment_id`, `mentor_id`, `student_id`, `started_on` |
| `alumni.mentoring-assignment.ended` | `POST /mentoring/assignments/{id}/end` | `organisation_id`, `assignment_id`, `mentor_id`, `student_id`, `ended_on` |
| `alumni.mentoring-session.scheduled` | `POST /mentoring/assignments/{id}/sessions` | `organisation_id`, `session_id`, `assignment_id`, `student_id`, `scheduled_at`, `mode` |
| `alumni.mentoring-session.rescheduled` | `PUT /mentoring/sessions/{id}` when `scheduled_at` changes | `organisation_id`, `session_id`, `assignment_id`, `student_id`, `scheduled_at` (the new time) |
| `alumni.mentoring-session.completed` | `POST /mentoring/sessions/{id}/complete` | `organisation_id`, `session_id`, `assignment_id`, `student_id` |
| `alumni.mentoring-session.cancelled` | `POST /mentoring/sessions/{id}/cancel`, and for each scheduled session when its assignment ends | `organisation_id`, `session_id`, `assignment_id`, `student_id` |

Dates are ISO `YYYY-MM-DD` (Asia/Kolkata); `scheduled_at` is an ISO timestamp in UTC.

## Consumed events

None.

## Platform services

| Service | How | Use |
|---|---|---|
| identity | `eos_core.security.decode_token` and `eos_core.config.permissions_for` in `api/deps.py` | The caller, their organisation and permission keys. The management-institute layouts give `placement-officer` the module role `alumni-coordinator` and `management-student` the role `alumni-mentee`. `student_id` is not looked up in identity in v1.0. |
| audit | `alumni_audit_entry`, written by the module | Every state change, until the audit SDK ships. |

## Dashboard

The widget `alumni.mentoring` on the management-student layout reads `GET /me/mentoring` (frontend, separate PR).
