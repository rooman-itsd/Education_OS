# alumni: data model

Tables of the Alembic chain in `db/` (revision `alumni_0001`, version table `alumni_alembic_version`), mapped in
`backend/src/eos_alumni/infrastructure/models.py`. Every table carries `organisation_id`; on Postgres each has the
`tenant_isolation` row-level-security policy on `app.organisation_id`, forced. Nothing is deleted. Timestamps are UTC;
`started_on` and `ended_on` are Asia/Kolkata calendar dates. People are platform/identity user ids, never foreign keys.

## `alumni_alumnus`

A directory record kept by staff (alumni have no login).

| Column | Type | Notes |
|---|---|---|
| `id` | string(36) | primary key |
| `organisation_id` | string(36) | owner; RLS |
| `created_at` | timestamptz | creation time |
| `full_name` | string(200) | required |
| `graduation_year` | integer | 1900 to the current year |
| `programme`, `current_company`, `current_designation`, `industry`, `city` | string(200) | optional |
| `email`, `phone`, `linkedin_url` | string(200) | contact details: staff, and the assigned mentee through `MentorCard` |
| `is_mentor` | boolean | may be assigned as a mentor |
| `notes` | text | staff only |
| `status` | string(10) | `active` or `archived` |
| `created_by`, `verified_by` | string(36) | the creator, who verifies the record (A2) |
| `verified_at` | timestamptz | the creation time |
| `archived_at`, `archive_reason` | timestamptz, text | set on archive, cleared on restore |

Index `ix_alumni_alumnus_listing (organisation_id, status, created_at)` serves the directory list.

## `alumni_mentoring_assignment`

A mentor assigned to a student.

| Column | Type | Notes |
|---|---|---|
| `id` | string(36) | primary key |
| `organisation_id` | string(36) | owner; RLS |
| `created_at` | timestamptz | orders the list (newest first) |
| `mentor_id` | string(36) | foreign key to `alumni_alumnus.id` |
| `student_id` | string(36) | the student's identity user id; no foreign key, not checked against identity in v1.0 |
| `student_name` | string(200) | a copy taken when the assignment is made, not kept in step |
| `started_on` | date | today or earlier |
| `ended_on` | date | between `started_on` and today |
| `status` | string(10) | `active` or `ended` |
| `focus` | string(200) | shown to the student |
| `assigned_by` | string(36) | the coordinator |
| `end_reason` | text | staff only |

Tenancy rules for `student_id`: every lookup by student is by `(organisation_id, student_id)`. The partial unique index
`uq_alumni_assignment_active_student (organisation_id, student_id) WHERE status = 'active'` keeps one active assignment
per student and organisation; `ix_alumni_assignment_student (organisation_id, student_id)` serves the lookups.

## `alumni_mentoring_session`

An optional record of a mentoring session.

| Column | Type | Notes |
|---|---|---|
| `id` | string(36) | primary key |
| `organisation_id` | string(36) | owner; RLS |
| `created_at` | timestamptz | |
| `assignment_id` | string(36) | foreign key to `alumni_mentoring_assignment.id` |
| `scheduled_at` | timestamptz | not before the assignment's `started_on` (Asia/Kolkata date) |
| `duration_minutes` | integer | 1 to 480, optional |
| `mode` | string(10) | `in_person`, `online` or `phone` |
| `location` | string(500) | a room, an address or a meeting link |
| `topic` | string(200) | |
| `status` | string(10) | `scheduled`, `completed` or `cancelled` |
| `notes` | text | staff only, set on completion |
| `cancel_reason` | text | staff only |
| `created_by` | string(36) | |

Index `ix_alumni_session_assignment_time (assignment_id, scheduled_at)` serves the session list and "upcoming".

## `alumni_audit_entry`

One row per state change, in the same transaction: `actor`, `action` (for example `alumnus.added`,
`assignment.ended`, `session.rescheduled`), `entity`, `entity_id`, `occurred_at`. Ids only, never text. It stands in
for the audit SDK until that ships.
