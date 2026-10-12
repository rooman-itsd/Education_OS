# student-information — PRD

**Domain:** student-lifecycle · **Tier:** common · **Owner:** Praveen (@praveen-rooman)

## 1. Purpose

student-information is the **Person system of record** for Education OS. It holds one durable
record per person who has a relationship with the organisation as a learner — from the moment an
authorised staff member creates the record through every status change over that person's
lifetime (active, suspended, graduated, withdrawn, alumnus).

Every other module that needs to know "who is this person" refers to this module's `person_id`
and reads this module's published events to keep its own cached copy of name/contact/status
current (ADR-0003). No other module stores a competing copy of the Person entity.

## 2. Users / actors

| Actor | Relationship |
|---|---|
| Student / learner | The subject of the record. Views and updates their own contact details where the organisation allows it. |
| Registrar / student-information staff | Creates and maintains records, changes status, issues ID cards. Holds `student-information:*` permissions. |
| Admissions staff | May be granted `student-information:person:write` to convert an accepted applicant into a Person record (a business process, not a code dependency — see §6). |
| Department admin, faculty, finance, facilities, campus-life staff (read-only, other modules) | Resolve a cached copy of name/status via events; never query this module's database directly. |
| Super admin | No organisation-level access; may inspect via platform-level tooling only (out of scope here). |

## 3. Scope

**In scope**
- The Person record: identity and contact details, guardian/emergency contact, date of birth.
- Status and status history (pending, active, suspended, graduated, withdrawn, alumnus).
- Identity and supporting documents attached to a person (scans/files, referenced via
  `platform/documents`; this module stores only the reference and metadata).
- ID card issuance and revocation (a logical record; the physical/PDF artifact is generated and
  stored through `platform/documents`).
- Search and lookup to prevent duplicate records (by name, email, or identity document number).

**Explicitly out of scope**
- Creating accounts or credentials — that is `platform/identity`.
- Organisation registration, plan selection, or Organisation Admin account creation — that is
  `platform/tenancy` + `platform/billing`, surfaced through `web-portal-cms`'s sign-up page.
  student-information never creates an organisation and is never involved in organisation onboarding.
- The admissions funnel itself (application, merit list, offer) — that is `modules/student-lifecycle/admissions`.
  An applicant's biographical data lives in admissions' own `Application` entity until a Person
  record is created here.
- Programme enrolment, semester registration, section allocation — that is
  `modules/student-lifecycle/enrolment-registration` (out of scope for Issue #62 entirely).
- Academic records, grades, attendance — `modules/academics/*`.
- Fee invoices and payments — `modules/finance-operations/fees-accounts`.

## 4. Capabilities

1. Create a Person record (authorised staff only — see business rule in §6).
2. Read / search / list Person records within the caller's organisation.
3. Update a Person's profile fields.
4. Change a Person's status, with a reason, and view the full status history.
5. Attach, list and remove documents against a Person (references to `platform/documents`).
6. Issue and revoke an ID card for a Person.
7. Publish domain events so other modules can keep a cached, read-only copy of the fields they need.

## 5. Important workflows

**Record creation (staff-driven).**
An authorised role (registrar, or admissions staff once granted the permission) creates a Person
record directly through `POST /people`. There is no automatic trigger from any other module's
event in this release — see §9 for why. There is no public or anonymous path to this endpoint.

**Status change.**
Staff call `PUT /people/{id}/status` with the new status and a reason. Every change is appended to
an immutable status history and raises `student-information.person.status-changed`. There is no
"undo"; a wrong change is corrected by a further status change with its own reason.

**Document attachment.**
Staff or the person themselves (where the organisation's permission grants allow it) upload a file
through `platform/documents` and attach the resulting `document_id` here with a type
(identity-proof, address-proof, photograph, prior-transcript, other).

**ID card issuance.**
Staff issue a card for an active person. The module records the logical card (number, status,
issued/revoked) and references the generated artifact's `document_id`. Revoking a card does not
delete its history.

**Duplicate prevention.**
Before creating a record, staff (or the calling module) can search by name, email or identity
document number (`GET /people?q=` / `?identity_number=`) to avoid raising a duplicate. The API
also returns `409` if an identity document number already exists in the organisation.

## 6. Business rules

- **A Person record is created only by an authorised role, never by a public sign-up.** This
  module exposes no public/anonymous endpoint. (Decision for Issue #62: `web-portal-cms`'s
  sign-up page is for organisation onboarding only — organisation, plan and Organisation Admin —
  and never creates a student or Person record.)
- A Person always belongs to exactly one organisation (`organisation_id`), enforced by row-level
  security; there is no cross-organisation visibility, not even for a person who happens to share
  an email with someone in another organisation.
- Status values: `pending` (record created, not yet confirmed active — e.g. awaiting document
  verification), `active`, `suspended`, `graduated`, `withdrawn`, `alumnus`. There is no
  `applicant` status: a person who has not yet been confirmed as a student belongs to admissions'
  own `Application` entity, not to this module (keeps the "one schema per module" boundary clean).
- Every status change requires a reason and is retained forever in status history; history rows
  are never edited or deleted.
- An identity document number (e.g. national ID / passport number), if provided, must be unique
  within the organisation.
- A Person record optionally carries a `source` reference (`module`, `entity`, `id` — e.g.
  `{ module: "admissions", entity: "application", id: "<uuid>" }`) recording where the person
  originated, for traceability only. This is a cached, read-only reference by ID — never a
  database foreign key into another module's schema (module-standard rule 2).

## 7. Integrations

- **platform/identity** — a Person record is not itself a login account; where a linked user
  account exists it is referenced by `identity_user_id` (nullable), set by staff when they grant
  the person sign-in access. Account creation itself remains identity's job.
- **platform/documents** — every file (identity proof, ID card artifact) is a reference to a
  document stored and served by this platform service. student-information never handles raw
  file storage.
- **platform/audit** — every create, update, status change, document action and card
  issue/revoke is an audited state change (module-standard rule 8 / RULES.md DoD).
- **Other modules (admissions, academics, finance-operations, campus-life, etc.)** — consume this
  module's published events (`student-information.person.*`) to keep a cached copy of the fields
  they need (name, status) next to their own `person_id` reference. No other module calls this
  module's write endpoints directly in this release; none of their contracts currently declare
  that dependency, so none is assumed here (see §9).
- **admissions** (not yet contracted) — the expected future integration is that admissions staff,
  on accepting an application, call `POST /people` here with a `source` reference back to the
  application. Because `admissions/contracts/openapi.yaml` does not yet exist as a reviewed
  contract, this module does not depend on it; the `source` field is generic enough to support it
  once admissions is published, without a contract change here.

## 8. Permissions

See `contracts/permissions.yaml` for the full catalogue. Summary:
`student-information:person:read`, `student-information:person:write`,
`student-information:status:manage`, `student-information:document:manage`,
`student-information:id-card:manage`. No roles are mapped here — role-to-permission composition
is profile data owned by the Architecture lead (ADR-0004).

## 9. Audit / state changes

Every one of the following is a state change that must be written to `platform/audit` once the
backend exists (week 2+), and is a published domain event: person created, person profile
updated, status changed, document attached/removed, ID card issued/revoked.

## 10. Tenant considerations

- Every table this module creates (people, status history, person documents, id cards) will carry
  `organisation_id` with row-level security on `app.organisation_id`, per module-standard rule 11.
- Every event envelope carries `organisation_id`.
- Search and list endpoints are always scoped to the caller's organisation; `404`, not `403`, is
  returned for a valid ID that belongs to a different organisation (matches the `NotFound`
  convention used elsewhere in the repo, e.g. `facility-booking`).
- Identity document number uniqueness is enforced **within an organisation**, not globally.

## 11. Acceptance criteria for Issue #62 (Week 1)

- [ ] `docs/prd.md` (this file) describes purpose, actors, scope, capabilities, workflows,
      business rules, integrations and tenant considerations, and does not include backend,
      frontend, or database implementation detail.
- [ ] `contracts/openapi.yaml` fully describes every endpoint in §4/§5 with request/response
      schemas, following the repository's existing OpenAPI conventions.
- [ ] `contracts/events.yaml` lists every event in §9 with a payload shape, following the
      `<module>.<entity>.<past-verb>` naming convention.
- [ ] `contracts/permissions.yaml` lists every permission key in §8, following the
      `<module>:<resource>:<action>` convention, with no invented role mappings.
- [ ] No cross-module code dependency is introduced; `module.yaml`'s `depends_on` and
      `consumes_events` remain limited to what this module actually needs this week.
- [ ] No endpoint, schema or business rule assumes a person is created through public sign-up.
