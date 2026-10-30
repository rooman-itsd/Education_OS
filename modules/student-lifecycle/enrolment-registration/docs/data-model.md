# enrolment-registration — data model

Every table is this module's own, named `enrolment_registration_*`, with `organisation_id` and the forced
`tenant_isolation` row-level-security policy. The Alembic version table is
`enrolment_registration_alembic_version`. References to other modules (`person_id`, `programme_id`,
`course_offering_id`, `section_id`, `academic_period_id`, `source_application_id`) are ids only: no foreign keys to
another module's tables.

## Entities

### ProgrammeEnrolment
| Field | Notes |
|---|---|
| id | uuid |
| organisation_id | |
| person_id | student-information Person id |
| student_name | display name, supplied by staff at enrolment |
| programme_id | academic-management programme id |
| roll_number | unique within the organisation, assigned by this module, never reused |
| start_academic_period_id | the term the student starts in |
| status | `active`, `completed`, `withdrawn` |
| source_application_id | optional admissions application id |
| enrolled_at, enrolled_by | |
| ended_at, end_reason | set on completion or withdrawal |

Unique: (organisation_id, roll_number); one `active` enrolment per (organisation_id, person_id, programme_id).

### RollNumberCounter
| Field | Notes |
|---|---|
| organisation_id, year | primary key |
| last_value | the last number issued for that organisation and year |

### RegistrationWindow
| Field | Notes |
|---|---|
| id, organisation_id | |
| academic_period_id | one window per term (unique) |
| opens_at, closes_at | `closes_at` after `opens_at` |
| updated_by, updated_at | |

### CourseRegistration
| Field | Notes |
|---|---|
| id | the `registration_id` every event carries; never changes |
| organisation_id | |
| programme_enrolment_id | foreign key (same module) |
| person_id | copied from the enrolment |
| course_offering_id, section_id, academic_period_id | academic-management ids |
| registration_type | `regular`, `supplementary`, `backlog` |
| status | `confirmed`, `withdrawn` |
| references_verified | false when the offering or section was not known locally when it was checked |
| confirmed_at, confirmed_by | |
| withdrawn_at, withdrawn_by, withdrawal_reason | |
| section_since | date the current section took effect |

Unique: one `confirmed` registration per (organisation_id, person_id, course_offering_id) (partial index).

### Local copies of academic-management (filled only by its events)
| Table | Fields | From |
|---|---|---|
| `term_ref` | academic_period_id, code, name, starts_on, ends_on, is_active | `term.created`, `term.activated` |
| `offering_ref` | course_offering_id, academic_period_id, course_code, course_title, status | `offering.created`, `.updated`, `.status-changed` |
| `section_ref` | section_id, course_offering_id, code, capacity, status | `section.created`, `.updated` |

### ProcessedEvent
| Field | Notes |
|---|---|
| organisation_id, event_id | unique; a consumed event is applied once (delivery is at-least-once) |
| name, processed_at | |

### AuditEntry
| Field | Notes |
|---|---|
| id, organisation_id | |
| actor | user id, or null for consumed events |
| action, entity, entity_id | e.g. `registration_confirmed`, `course_registration`, the registration id |
| detail | JSON |
| occurred_at | |

## Relationships

```
ProgrammeEnrolment (1) ──< CourseRegistration (many)
RegistrationWindow ──> term (by academic_period_id, not a join)
CourseRegistration ──> offering_ref / section_ref (by id; the copy may not exist yet)
```

## Ownership boundaries

- **Owns:** programme enrolments, roll numbers, registration windows, course registrations and their history.
- **Does not own:** persons (student-information), terms, programmes, offerings, sections and their capacity
  (academic-management), exam candidates and results (examinations), fees (fees-accounts).
- **What others keep instead of querying these tables:** academic-management's roster, examinations'
  `registration_ref`, lms' `member_ref` and timetable-attendance's `section_member`, all built from this module's
  events.
