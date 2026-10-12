# student-information — data model

One schema (`student_information`), owned entirely by this module. No cross-schema foreign keys
(module-standard rule 2); every reference to another module's entity is by id only.

## Entities

### Person
The aggregate root. One row per person with a learner relationship to the organisation.

| Field | Notes |
|---|---|
| id | uuid, primary key |
| organisation_id | required on every row; row-level security scopes every query to it |
| first_name, last_name, preferred_name | |
| date_of_birth | nullable |
| gender | free text, nullable |
| identity_number | nullable; unique **within an organisation** when present |
| contact (email, phone, address) | embedded or a 1:1 table |
| guardians | 1:many — name, relation, phone, email |
| identity_user_id | nullable reference to a `platform/identity` user id; set only when sign-in access is granted |
| status | current value of `PersonStatus`; the authoritative current state |
| status_effective_date | |
| source | optional `{module, entity, id}` — where the person originated (e.g. an accepted admissions application). Cached for traceability only, never joined |
| created_at, updated_at | |

### StatusHistoryEntry
Append-only. One row per status change; never updated or deleted.

| Field | Notes |
|---|---|
| id | uuid |
| person_id | references Person within this schema |
| organisation_id | |
| status, reason, effective_date | |
| changed_by | the acting user's id (from platform/identity, by reference) |
| changed_at | |

### PersonDocument
A reference to a file stored by `platform/documents`; this module never stores file bytes.

| Field | Notes |
|---|---|
| id | uuid |
| person_id | |
| organisation_id | |
| type | identity_proof, address_proof, photograph, prior_transcript, other |
| document_id | id from platform/documents |
| label | optional free text |
| uploaded_by, uploaded_at | |

### IdentityCard
A logical record of an issued card. The physical/PDF artifact is a `platform/documents` reference.

| Field | Notes |
|---|---|
| id | uuid |
| person_id | |
| organisation_id | |
| card_number | |
| status | issued, revoked, expired |
| document_id | the generated card artifact |
| issued_by, issued_at | |
| revoked_by, revoked_at, revoked_reason | nullable |

## Relationships

```
Person (1) ──< StatusHistoryEntry (many)
Person (1) ──< PersonDocument (many)
Person (1) ──< IdentityCard (many)
```

All relationships are within this module's own schema. `identity_user_id` and `source.id` are
references by id into other modules/services — resolved by calling their published API when
needed, never by a database join.

## Ownership boundaries

- **This module owns:** the Person record itself, its status and status history, its attached
  document references, and its ID cards.
- **This module does not own:** login credentials (`platform/identity`), raw file storage
  (`platform/documents`), the admissions funnel or application data (`admissions`), programme
  enrolment (`enrolment-registration`, out of scope for Issue #62 regardless), academic records
  (`academics/*`), or fee invoices (`finance-operations/fees-accounts`).
- **What other modules keep instead of querying this module's tables:** a cached copy of
  `person_id`, name and status, refreshed by consuming `student-information.person.*` events
  (ADR-0003). No module reads this schema directly; all access is through the published API or
  events.
