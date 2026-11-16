# lms: integration points

lms reaches other modules only through their published contracts, and they reach it only through
`contracts/openapi.yaml` and `contracts/events.yaml`. No code is imported from another module.

## Events published

To the transactional outbox (`eos_core.events`), in the same transaction as the change and its audit entry. Every
payload carries `organisation_id`; the envelope carries the acting user (`actor`, null when the system acts).
`backend/tests/test_events.py` checks every payload against `contracts/events.yaml`.

| Event | When |
|---|---|
| `lms.course-space.created` | An administrator creates a course space |
| `lms.material.published` | A material is published (again after being unpublished, too) |
| `lms.assignment.published` | An assignment is published |
| `lms.assignment.updated` | A published assignment's `due_at`, `max_points`, `target_section_ids` or `late_policy` changes (`changed_fields` names them), or it is closed (`["status"]`) |
| `lms.submission.submitted` | A student submits an attempt |
| `lms.grade.released` | A grade is released, by an instructor, by `auto_release`, or again with a higher `version` after a change |
| `lms.quiz.published` | A quiz is published |
| `lms.quiz-attempt.submitted` | A student submits an attempt, or the system does at its deadline (`submitted_by_system`) |
| `lms.discussion-thread.created` | A member starts a thread |

## Events consumed

Handled in `backend/src/eos_lms/application/consumers.py`, registered under the `eos.event_consumers` entry point
(`backend/pyproject.toml`) and listed in `module.yaml`. Idempotent per envelope id, tolerant of order, applied only
in the event's organisation.

| Event | Publisher | Read model |
|---|---|---|
| `academic-management.offering.created` | academic-management | `offering_ref`: code, title, department, period |
| `academic-management.offering.status-changed` | academic-management | `offering_ref.status` |
| `academic-management.faculty-assignment.created` | academic-management | `instructor_ref` active: the faculty member teaches the offering's course space |
| `academic-management.faculty-assignment.ended` | academic-management | `instructor_ref` ended |
| `enrolment-registration.course-registration.confirmed` | enrolment-registration | `member_ref` active, with section and name |
| `enrolment-registration.course-registration.withdrawn` | enrolment-registration | `member_ref` withdrawn |
| `enrolment-registration.section-allocation.changed` | enrolment-registration | `member_ref.section_id` |
| `student-information.person.account-linked` | student-information | `person_account`: the learner's person id for their identity user id. Until it arrives, the user id is the learner's id |

Not consumed: `offering.updated` and `course.*` carry only `changed_fields`; section events are not needed (section
ids are kept by value); no scheduled-class events (owner decision C19).

## Platform services

| Service | How | Status |
|---|---|---|
| identity | Bearer token verified with `eos_core.security.decode_token`; permission keys from every catalogue with `eos_core.config.permissions_for` (`api/deps.py`) | Swap for the identity SDK when it ships |
| audit | `lms_audit_entry`, one row per state change (`application/common.py`) | Stands in for the audit SDK |
| event-bus | `eos_core.events.publish` to the outbox; consumers through the entry point | Available |
| documents | Materials and submissions keep `document_id` only; lms never stores file bytes | Ids are not verified yet (LQ7) |
| scheduler | `application/jobs.py` `submit_overdue_attempts()` submits attempts past their deadline; attempts are also settled whenever a request looks at them | Waits for platform/scheduler |
| search, notification | Not used in week 1 (LQ14) | — |

## Dashboard widgets

| Widget | Layouts | Endpoint | Permission |
|---|---|---|---|
| `lms.assignments-to-grade` | `faculty` and every layout extending it | `GET /me/grading-queue` | `lms:grade:manage-assigned` |
| `lms.course-materials` | `student` (also listed by `management-student` and `medical-student`) and every layout extending it | `GET /me/course-materials` | `lms:course-space:read-own` |

The faculty layout lists the module role `lms-instructor` and the student layout `lms-student`, so both widgets are
backed for every role extending those layouts.
