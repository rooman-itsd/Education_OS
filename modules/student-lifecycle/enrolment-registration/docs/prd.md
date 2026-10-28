# enrolment-registration — PRD

**Domain:** student-lifecycle · **Tier:** common · **Owner:** Praveen (@praveen-rooman) · **Issue:** #105

## 1. Purpose

enrolment-registration records two facts every academic module depends on:

1. **Programme enrolment:** a person is a student of a programme from a starting term, under a roll number.
2. **Course registration:** in a given term, an enrolled student is registered for a course offering, in one of
   its sections.

It is the source of truth for "who is registered for what". academic-management builds its course roster from
this module's events, examinations derives exam candidates from them, lms decides course membership from them,
and timetable-attendance knows who sits in which section. None of them writes registrations themselves.

## 2. Users / actors

| Actor | Role | Relationship |
|---|---|---|
| Registration staff (academic office) | `registration-staff` | Enrols students, opens registration windows, registers students (one at a time or in bulk), withdraws registrations and moves students between sections |
| Management (VC, Registrar) | `management` | Reads enrolments and registrations |
| Organisation admin | `org-admin` | Reads enrolments and registrations |
| Department admin | `department-admin` | Reads enrolments and registrations |
| Examination staff | `examination-staff` | Reads registrations; sees the `registered-candidates` widget |
| Other modules | (events) | Consume this module's events; never call it to decide who is registered |

## 3. Scope

**In scope (this release)**
- Programme enrolment with an organisation-unique roll number; withdraw and complete.
- A registration window per term (opens, closes).
- Course registration for a course offering and section, of type `regular`, `supplementary` or `backlog`;
  one person at a time or many in one request.
- Withdrawing a registration; moving it to another section of the same offering with an effective date.
- A report of registered candidates per course offering for a term (backs the widget).
- Events for every change, and local copies of academic-management's terms, offerings and sections.

**Out of scope (this release)**
- Student self-service registration (staff register students).
- Electives and elective groups (academic-management's `elective_group` question is unresolved).
- Registration holds (fee, library, document or disciplinary).
- Tuition invoices (fees-accounts raises fees by its own means).
- Defining terms, programmes, courses, offerings or sections: that is `academics/academic-management`.
- The person record: that is `student-lifecycle/student-information`.
- Exam eligibility and candidates: that is `academics/examinations`.

## 4. Capabilities

1. Enrol a person in a programme; the module assigns the roll number.
2. List and search enrolments; read one; withdraw one (which withdraws its confirmed registrations); complete one.
3. Set or change the registration window of a term; read it.
4. Register an enrolled student for a course offering and section.
5. Register many enrolled students for one offering and section in one request, with a result per student.
6. List and filter registrations by term, offering, section, person, type and status; read one.
7. Withdraw a registration; move a registration to another section.
8. Report registered candidates per offering for a term.

## 5. Important workflows

**Enrolment.** After admissions accepts an application, staff create the person in student-information and then
enrol that person here: programme, starting term, display name, and optionally the admissions application id.
The module assigns the roll number. A person has at most one active enrolment per programme.

**Opening registration.** Staff set the term's window (`opens_at`, `closes_at`). Regular registrations are accepted
only while the window is open. Supplementary and backlog registrations ignore the window: they happen around exam
cycles, not at the start of term.

**Registering.** Staff pick an offering and a section and register one student or a batch. Each registration checks,
in order, the rules in §6 and either confirms the registration (and publishes
`course-registration.confirmed`) or reports why not. A batch never fails as a whole: each student gets a result.

**Changes.** Withdrawing a registration keeps it (status `withdrawn`) and publishes `course-registration.withdrawn`.
Moving a student to another section keeps the same registration id and publishes `section-allocation.changed` with
the effective date.

**Leaving the programme.** Withdrawing an enrolment withdraws every confirmed registration under it, each with its
own `course-registration.withdrawn` event, then publishes `programme-enrolment.withdrawn`.

## 6. Business rules

1. A registration needs an **active** programme enrolment of the same person in the same organisation.
2. One **confirmed** registration per person per course offering. A withdrawn one does not count.
3. **The roster's admission checks, applied here first.** academic-management's roster refuses a registration
   unless the offering is `open`, the section is `open`, and the section is not full. This module applies the same
   three checks using its local copies of academic-management's data, so the two modules never disagree about who
   is registered. A check whose data is not known locally yet (no event received) is skipped, and the registration
   is marked `references_verified: false`.
4. A **section change** stays within the same offering and is subject to the section checks of rule 3.
5. **Regular** registrations need the term's window to be open. **Supplementary** and **backlog** do not.
6. The **registration id never changes** for the life of a registration, and a registration is never deleted.
7. **Roll numbers** are unique within the organisation and never reused: `<PREFIX><YEAR>-<5 digits>`, for example
   `RN2026-00042`, numbered per organisation and year.
8. A withdrawn or completed enrolment cannot be changed again.

## 7. Integrations

- **academics/academic-management** (both directions). Publishes terms, offerings and sections, which this module
  keeps as local copies (§8 of `data-model.md`); consumes this module's three course-registration events into its
  roster. The event names and the fields its roster code requires are fixed by that code.
- **academics/examinations, academics/lms, academics/timetable-attendance** consume the course-registration events.
- **student-lifecycle/student-information** owns the person. This module stores `person_id` and a display name the
  staff supply; it never calls student-information.
- **student-lifecycle/admissions** is referenced only by an optional application id on the enrolment.
- **platform/audit**: every change is written to this module's audit table until audit has a service.

See `integration-points.md` for each consumer's open question and the answer this contract gives.

## 8. Permissions

| Key | Lets the holder |
|---|---|
| `enrolment-registration:enrolment:read` | list and read programme enrolments |
| `enrolment-registration:enrolment:manage` | enrol, withdraw and complete |
| `enrolment-registration:registration:read` | list and read registrations, windows and the registered-candidates report |
| `enrolment-registration:registration:manage` | set windows; register, withdraw and move registrations |

Roles: `registration-staff` holds all four; `org-admin`, `management` and `department-admin` hold both read keys;
`examination-staff` holds `registration:read`.

## 9. Audit / state changes

Every enrolment, completion, withdrawal, window change, registration, registration withdrawal and section change
writes an audit row in the same transaction, and publishes the matching event where `events.yaml` names one.

## 10. Tenant considerations

- Every table carries `organisation_id` with the forced `tenant_isolation` policy.
- Roll numbers and the one-confirmed-registration rule are unique **within** an organisation.
- Event payloads never carry `organisation_id`: it travels on the envelope (platform/event-bus contract). Consumed
  events are applied only to the organisation on their envelope.

## 11. Decisions taken without a reply (reviewers may change them)

Issue #105 asks for a contract review. These were decided from what is on `main`; each is easy to change before
the backend is merged.

| # | Question | Decision | Who may change it |
|---|---|---|---|
| D1 | Who registers students? No `registrar` dashboard role exists; the Registrar is part of `management` | New module role `registration-staff` with every key; `management`, `org-admin`, `department-admin` read | Faizan |
| D2 | Who owns roll numbers? academic-management and timetable-attendance expect one; student-information stores none | This module, assigned at enrolment and carried in `course-registration.confirmed` | Faizan |
| D3 | How do we stay consistent with the roster's three checks while no event relay exists? | Local copies of academic-management's data; check when known, accept and flag when not | Shivani |
| D4 | Electives in this release? | No: one registration per offering | Faizan, Shivani |
| D5 | Registration windows and holds? | Windows yes, per term, for regular registrations; holds no | Faizan |
| D6 | Supplementary and backlog registration (examinations Q1) | `registration_type`: `regular`, `supplementary`, `backlog` | Shivani, Akshata |
| D7 | Tuition invoices by event (fees-accounts open question 2) | Not in this release | Gokula Lakshmi |
| D8 | `organisation_id` inside payloads? Some modules include it | No: the event-bus contract and academic-management's consumer both put it on the envelope | Faizan |
| D9 | "Semester" (admin console sample) or "term"? | "Term", as academic-management's contract says | Faizan |

## 12. Acceptance criteria for issue #105

- [ ] Contracts publish the three course-registration events with every field academic-management's roster reads.
- [ ] Every table has `organisation_id` and the forced row-level-security policy; the cross-tenant leak test passes.
- [ ] Registration enforces rules 1 to 5; a batch reports a result per student.
- [ ] Widget `enrolment-registration.registered-candidates` is exported with tests and shows on the Examination Staff
      dashboard.
- [ ] Registered in `apps/backend` and `apps/frontend`; `env.example`, README and CHANGELOG complete.
