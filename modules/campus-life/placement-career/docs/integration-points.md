# placement-career: integration points

placement-career reads nothing from other modules and imports nothing outside itself and `packages/`.

## Platform services (through `packages/`)

| Service | How | For |
|---|---|---|
| identity | `eos_core.security.decode_token` and `eos_core.config.permissions_for` in `api/deps.py` | the caller (`sub`), organisation (`org`), roles and their keys; the optional `name` claim becomes the applicant's name. Replace with the identity SDK when it ships. |
| audit | own `placement_career_audit_entry` table, same transaction | every state change. Replace with the audit SDK when it ships. |
| events | `eos_core.events.publish` (transactional outbox, relayed by platform/event-bus) | the events below |

## Events published

Payloads carry ids, dates and the cancel reason only (P9). Every event carries `organisation_id` in the envelope and
the payload; `actor` is the acting user. No module consumes them in v1.0; notification may.

| Event | When |
|---|---|
| `placement-career.drive.scheduled` | `POST /drives/{id}/schedule` |
| `placement-career.drive.rescheduled` | `PUT /drives/{id}` changes `scheduled_on` or `ends_on` of a scheduled drive |
| `placement-career.drive.completed` | `POST /drives/{id}/complete` |
| `placement-career.drive.cancelled` | `POST /drives/{id}/cancel` |
| `placement-career.opening.published` | `POST /openings/{id}/publish` |
| `placement-career.opening.closed` | `POST /openings/{id}/close` |
| `placement-career.opening.cancelled` | an open opening cancelled, on its own or with its drive (a draft publishes nothing) |
| `placement-career.application.submitted` | `POST /me/applications` |
| `placement-career.application.shortlisted`, `.offered`, `.accepted`, `.declined`, `.rejected` | `POST /applications/{id}/status` (in_process publishes nothing) |
| `placement-career.application.withdrawn` | `POST /me/applications/{id}/withdraw` |

## Events consumed
None.

## Layouts (platform/identity)
The `module_roles` of placement-officer, industry-coordinator and practicum-coordinator list
`placement-career-officer`; industry-liaison lists `placement-career-viewer`; every learner layout extends `student`,
which this catalogue grants `opening:read`, `self:read` and `self:apply`.

## Dashboard widgets (frontend, to follow)

| Widget | Endpoint | Permission |
|---|---|---|
| `placement-career.drives` | `GET /reports/drives-upcoming` | `placement-career:report:read` |
| `placement-career.openings-summary` | `GET /reports/openings-summary` | `placement-career:report:read` |
| `placement-career.openings` | `GET /me/openings` | `placement-career:self:read` |
