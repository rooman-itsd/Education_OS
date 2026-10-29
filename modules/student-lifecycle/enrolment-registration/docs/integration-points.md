# enrolment-registration — integration points

Envelope rule: `organisation_id`, `actor` and `occurred_at` travel on the event envelope
(`platform/event-bus/contracts/events.yaml`), never in a payload. Delivery is at-least-once; consumers deduplicate
on the envelope id.

## Events published (contracts/events.yaml)

| Event | Consumers |
|---|---|
| `enrolment-registration.programme-enrolment.created` | none required yet; available to student-information, fees-accounts, reporting |
| `enrolment-registration.programme-enrolment.withdrawn` | same |
| `enrolment-registration.course-registration.confirmed` | academic-management (roster), examinations, lms, timetable-attendance |
| `enrolment-registration.course-registration.withdrawn` | same |
| `enrolment-registration.section-allocation.changed` | academic-management, lms, timetable-attendance |

The three course-registration events carry every field academic-management's roster code reads
(`modules/academics/academic-management/backend/src/eos_academic_management/application/roster.py`); the extra
fields (`academic_period_id`, `registration_type`, `effective_on`, `student_name`, `roll_number`) are optional for
that consumer, which tolerates unknown fields.

## Answers to questions other modules addressed to this module

| Module and question | Answer in this contract |
|---|---|
| academic-management §8.3: event names, payloads, timeline | The three names it proposed, unchanged, version 1, with all its required fields. Published from this module's first backend release |
| academic-management §8.3: do we consume `programme.*`, `curriculum.published`? | Not in this release. We consume `term.*`, `offering.*` and `section.*` |
| examinations Q1: is candidacy derived from registration? Supplementary and backlog? | Yes: one confirmed registration per student per offering, with `registration_type` `regular`, `supplementary` or `backlog`. Registration staff register supplementary and backlog students; the window does not apply to them |
| examinations Q2, lms LQ6, timetable-attendance Q3: which student id? | `person_id`, the student-information Person id (agreed on issue #100). Field name `person_id` in every event |
| lms LQ4: which events define access? | `course-registration.confirmed` adds, `.withdrawn` removes, `section-allocation.changed` moves |
| timetable-attendance Q2: section allocation with effective date | `section-allocation.changed` carries `effective_on` (date); `confirmed` carries `confirmed_at` |
| timetable-attendance Q3: is the display name carried? | Yes, `student_name` on `confirmed` and `section-allocation.changed` |
| fees-accounts open question 2: tuition invoices by event? | Not in this release |

## Events consumed (local copies of academic-management)

| Event | What it updates |
|---|---|
| `academic-management.term.created` | `term_ref` (code, name, dates) |
| `academic-management.term.activated` | `term_ref.is_active` (one active term per organisation) |
| `academic-management.offering.created` | `offering_ref` (term, course code and title); status `planned` (academic-management FR-9: offerings start planned) |
| `academic-management.offering.status-changed` | `offering_ref.status` |
| `academic-management.offering.updated` | recorded only: its payload names changed fields but not their values |
| `academic-management.section.created` | `section_ref` (code, capacity); status `open` |
| `academic-management.section.updated` | `section_ref` capacity and status |

Each is applied once per envelope id (`processed_event`), only for the organisation on the envelope, and only for
payload version 1; other versions are ignored. Until `platform/event-bus` delivers events, these copies stay empty and
registrations are accepted with `references_verified: false` (PRD §6 rule 3).

## Platform services

| Service | Use |
|---|---|
| `platform/audit` | Every state change; written to this module's `audit_entry` table until audit has a service |

## Cross-module API dependencies

None. This module never calls another module's API.

## What the host must provide

Nothing beyond registration in both `modules.enabled.yaml` files; all routes are authenticated staff routes. Event
delivery (`platform/event-bus`) is needed for the local copies to fill.
