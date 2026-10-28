# admissions — data model

Tables owned entirely by this module, every one named `admissions_*` (the repo's convention for
a module's own schema; its Alembic version table is `admissions_alembic_version`). No foreign keys
to another module's tables (module-standard rule 2); references to other modules' entities
(`programme_id`, `selection_process_round_id`, `portfolio_item_id`) are ids only, never joined.
Every table carries `organisation_id` with the `tenant_isolation` row-level-security policy.

## Entities

### Application
The aggregate root.

| Field | Notes |
|---|---|
| id | uuid, primary key |
| organisation_id | required on every row; row-level security scopes every query |
| reference_number | generated at submission, unique **within an organisation** |
| applicant (first_name, last_name, email, phone, date_of_birth) | embedded; this module's own copy, not a reference to student-information (no Person exists yet at this stage) |
| programme_id | reference by id into academics; not validated against another module's schema |
| academic_year | |
| selection_process_round_id | nullable reference by id into practice/selection-process |
| portfolio_item_id | nullable reference by id into practice/portfolio |
| status | current `ApplicationStatus` |
| submitted_at, decided_at | |
| created_at, updated_at | |

### ApplicationDocument
| Field | Notes |
|---|---|
| id | uuid |
| application_id | |
| type | identity_proof, academic_record, portfolio_evidence, other |
| document_id | id from platform/documents |
| label | |
| verification_status | pending, verified, rejected |
| verification_note, verified_by, verified_at | nullable |
| uploaded_at | |

### MeritList / MeritListEntry
| Field | Notes |
|---|---|
| MeritList.id, organisation_id, programme_id, academic_year, title, status (draft/published), published_at, created_by, created_at | |
| MeritListEntry: application_id, rank, score (nullable) | 1:many under a MeritList; an application once per list, a rank once per list |

### Offer
| Field | Notes |
|---|---|
| id | uuid |
| application_id | an application has at most one open offer at a time (enforced by a partial unique index) |
| status | open, accepted, declined, expired, withdrawn |
| note, expires_at | nullable |
| offered_by, offered_at | |
| decided_at, decline_reason | nullable |

### AuditEntry
| Field | Notes |
|---|---|
| id, organisation_id | |
| actor | user id for staff actions; the application id for applicant actions |
| action, entity, entity_id | e.g. `status_changed`, `application`, the application id |
| detail | JSON, e.g. previous and new status, reason |
| occurred_at | |

## Relationships

```
Application (1) ──< ApplicationDocument (many)
Application (1) ──< Offer (0..1 open at a time, history kept)
MeritList (1) ──< MeritListEntry (many) ──> Application (by id, not a join)
AuditEntry ──> any of the above (by entity + entity_id, not a join)
```

## Ownership boundaries

- **This module owns:** the Application record (including the applicant's own copy of their
  bio data — not a reference to any Person record, since none exists at this stage),
  ApplicationDocument, MeritList/MeritListEntry, Offer.
- **This module does not own:** the Person/Student record (`student-information`, created
  manually by staff after acceptance), fee invoices (`fees-accounts`, triggered by this module's
  `accepted` event), programme/academic definitions (`academics/*`, referenced by id only),
  portfolio items or selection rounds (`practice/*`, referenced by id only when relevant).
- **What other modules keep instead of querying this module's tables:** `fees-accounts` consumes
  `admissions.application.accepted`; nothing else is currently expected to consume this module's
  events, since `student-information`'s Person creation is a manual staff action, not an event
  subscription.
