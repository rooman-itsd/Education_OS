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

### Backfill: `POST /registrations/republish` (run once per organisation after deploy)

A consumer that started after registrations were confirmed has no copy of them. `POST /registrations/republish`
(permission `enrolment-registration:registration:manage`) publishes `course-registration.confirmed` again for every
registration of the caller's organisation that is confirmed now, and returns `{"published": n}`. Run it once per
organisation after deploying 0.2.0, and again whenever a consumer has lost its copy.

- **What is published.** Only `course-registration.confirmed`, with the registration as it is now: current
  `section_id`, original `confirmed_at`, the enrolment's current `student_name` and `roll_number`. It is a new
  event: new envelope id, `occurred_at` the time of the republish.
- **Not published.** Withdrawn registrations and `section-allocation.changed`. A consumer that never saw a
  withdrawn registration holds no row for it, which is already the right state. The confirmation names the current
  section, so a consumer needs no move to reach it. This module keeps no move history to replay, so a consumer that
  starts late places the student in the current section from `confirmed_at`.
- **Consumers already holding the registration.** They apply a confirmation once per `registration_id`
  (timetable-attendance ignores a second one, and academic-management's roster keeps the section it has). lms
  orders by `occurred_at`, so it takes the current section and the active status, which are both true. A
  withdrawal made after the republish occurred later and wins in either arrival order.
- **Safe to repeat.** The call changes nothing and writes no audit row.

academic-management's roster admits a confirmation only into an open offering and an open section with room. When
it is wired to the relay, a republished registration of an offering that is `in_progress` or a full section is
recorded there as rejected. Its owner decides whether a replayed confirmation should bypass those checks.

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
