# placement-career: data model

Six tables, all prefixed `placement_career_`, created by the Alembic chain in `db/` (revision `placement_career_0001`,
version table `placement_career_alembic_version`). Every table carries `organisation_id` and, on Postgres, the forced
`tenant_isolation` row-level-security policy on `app.organisation_id`. Ids are UUID strings. Students and staff are
platform/identity user ids, never foreign keys; no table points into another module. Dates are Indian business dates
(Asia/Kolkata); timestamps are UTC. Nothing is deleted.

```
company 1──* drive 1──* opening *──1 company
                        opening 1──* application 1──* application_history
audit_entry (any entity, by id)
```

## company
A company the organisation places students with. A record, not a login.

| Column | Type | Notes |
|---|---|---|
| id, organisation_id, created_at | | |
| name | varchar(200) | as entered, trimmed |
| name_key | varchar(200) | lower case, single spaces; unique with `organisation_id` (`uq_placement_career_company_name`) |
| industry, website | varchar(120), varchar(500) | nullable; website an http(s) URL |
| contact_name, contact_email, contact_phone, notes | | nullable; staff only, never on drives, openings or events |
| active | boolean | an inactive company gets no new drives or openings |
| created_by | varchar(36) | identity user |

## drive
A dated campus event of one company. Status `draft`, `scheduled`, `completed` or `cancelled`.

| Column | Type | Notes |
|---|---|---|
| id, organisation_id, created_at | | |
| company_id | → company | does not change once the drive has openings |
| title, description, venue | | |
| scheduled_on, ends_on, registration_closes_on | date | `ends_on` ≥ `scheduled_on` ≥ `registration_closes_on` |
| rounds | JSON list of strings | shown, not tracked |
| eligibility | JSON | `{programmes, graduating_years, min_cgpa, max_active_backlogs, notes}`; shown, never enforced |
| status | varchar(12) | index `(organisation_id, status, scheduled_on)` |
| cancel_reason | text | set on cancel |
| created_by | varchar(36) | |

## opening
A job. Status `draft`, `open`, `closed` or `cancelled`.

| Column | Type | Notes |
|---|---|---|
| id, organisation_id, created_at | | |
| company_id | → company | the drive's company when in a drive |
| drive_id | → drive, nullable | null for an opening outside a drive |
| title, description, location | | |
| ctc_per_annum | numeric(14,2), nullable | rupees, shown to students |
| positions | integer, nullable | at least 1 |
| applications_close_on | date | last day to apply (IST), inclusive; on or before the drive date |
| eligibility | JSON | as on drive |
| status | varchar(12) | index `(organisation_id, status, applications_close_on)` |
| cancel_reason | text | |
| published_at | timestamptz | set on publish |
| created_by | varchar(36) | |

## application
A student's application. Status `applied`, `shortlisted`, `in_process`, `offered`, `accepted`, `declined`,
`rejected` or `withdrawn`. Unique `(opening_id, student_id)` (`uq_placement_career_application_student`): one per
student and opening, a withdrawn one included.

| Column | Type | Notes |
|---|---|---|
| id, organisation_id | | |
| opening_id | → opening | the drive is the opening's |
| student_id | varchar(36) | identity user of the applicant |
| student_name | varchar(200) | the token's `name` claim when applying, empty without one |
| status | varchar(12) | |
| declares_eligible | boolean | always true (required to apply) |
| declared_programme, declared_graduating_year, declared_cgpa (numeric(4,2)), declared_active_backlogs | | the self-declaration, not checked |
| offered_at | timestamptz | set when moved to offered; the application has an offer from then on |
| offer_ctc_per_annum (numeric(14,2)), offer_joining_on (date), offer_notes | | the offer, all nullable |
| reason | text | why it was rejected; shown to the student |
| applied_at, updated_at | timestamptz | |

`student_placed` is not stored: it is true when the student has an `accepted` application in the organisation.

## application_history
One line per status an application reached, numbered from 1 per application (unique `(application_id, sequence)`).
Columns: `application_id` → application, `sequence`, `status`, `actor_id` (the student for applied and withdrawn, the
officer otherwise), `at`. Rendered as `history[{status, at, by}]` on `GET /applications/{id}`.

## audit_entry
Who changed what: `actor`, `action`, `entity`, `entity_id`, `occurred_at`. Actions: `company.created`,
`company.updated`, `company.deactivated`, `company.reactivated`; `drive.created`, `.updated`, `.scheduled`,
`.rescheduled`, `.completed`, `.cancelled`; `opening.created`, `.updated`, `.published`, `.closed`, `.cancelled`;
`application.submitted`, `.shortlisted`, `.in_process`, `.offered`, `.accepted`, `.declined`, `.rejected`,
`.withdrawn`. Ids only, never a declaration, an offer or a contact. Index `(organisation_id, entity, entity_id)`.
Stands in for the audit SDK until it ships.
