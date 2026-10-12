# admissions — PRD

**Domain:** student-lifecycle · **Tier:** common · **Owner:** Praveen (@praveen-rooman)

## 1. Purpose

admissions runs the application funnel for one academic cycle: a prospective applicant submits an
application, the organisation verifies documents and eligibility, decides through a merit list or
a selection process, extends an offer, and the applicant accepts or declines it. Once an applicant
accepts, admissions' job is done — `student-information` (via an authorised staff action) and
`finance-operations/fees-accounts` (via the event this module publishes) take over from there.

## 2. Users / actors

| Actor | Relationship |
|---|---|
| Applicant (public, no account) | Submits an application and tracks it by reference number and email. Never has an organisation login — see §6. |
| Admissions staff | Reviews documents, decides eligibility, generates and publishes merit lists, extends offers. Holds `admissions:*` permissions. |
| Department admin | Approves/reviews decisions for their department's programmes where the organisation's role grants require it. |
| Finance staff (`fees-accounts`, other module) | Consumes `admissions.application.accepted` to raise a fee invoice. Never calls this module's API. |
| Registrar (`student-information`, other module) | On seeing an accepted application, a staff member manually creates the Person/Student record there, referencing this application as `source`. Not an automatic integration — see §6. |

## 3. Scope

**In scope**
- Public, anonymous application submission and status tracking (reference number + email).
- Document checklist and upload references (via `platform/documents`) per application.
- Staff review: document verification, eligibility decision.
- Merit list generation and publishing for a programme and academic cycle.
- Offer issuance by staff, and offer accept/decline by the applicant (anonymous, verified by
  reference number + email, same as submission).
- Publishing events so `fees-accounts` and (eventually, by staff action) `student-information`
  know an application was accepted.

**Explicitly out of scope**
- Creating an organisation, a plan, or an Organisation Admin account — that is
  `web-portal-cms`'s sign-up page + `platform/tenancy` + `platform/billing`. Nothing here is
  reachable from, or related to, organisation onboarding.
- Creating a Person/Student record — that is `student-information`, done by an authorised staff
  member as a separate, manual action. This module never calls `student-information`'s API and
  never creates a login account for the applicant (see §6).
- Programme enrolment, semester registration, section allocation — that is
  `enrolment-registration` (out of scope for Issue #62 entirely).
- Fee invoicing and payment — `finance-operations/fees-accounts` (a consumer of this module's
  events, not a dependency of this module).
- Portfolio review and selection rounds themselves — `practice/portfolio` and
  `practice/selection-process` own those; this module only references their outcomes by id when a
  programme's admission path uses them (see §7).

## 4. Capabilities

1. Submit an application anonymously (no account required).
2. Track an application's status and pending documents by reference number + email.
3. Attach supporting documents to an application (applicant, while in `submitted` or
   `under_review`; verified by reference number + email).
4. Staff: list/search/read applications in the organisation; move an application through status
   transitions (`under_review`, `eligible`, `ineligible`, `rejected`, staff-initiated `withdrawn`).
5. Staff: verify or reject an individual document.
6. Staff: generate and publish a merit list for a programme and academic cycle.
7. Staff: extend an offer on an application.
8. Applicant: accept or decline an offer (anonymous, verified by reference number + email).
9. Publish domain events at every meaningful state change.

## 5. Important workflows

**Submission (anonymous).**
`POST /applications` is public. The applicant provides their own name, email, phone, programme
and academic cycle inline — there is no identity account, before or after submission, in this
release. The response includes a `reference_number` the applicant must keep to track their
application; no separate login is issued.

**Tracking (anonymous).**
`GET /applications/track?reference_number=&email=` is public and returns the application's
current status and any pending document requirements. The reference number alone is not enough —
the email must match, so a guessed reference number cannot leak another applicant's status.

**Document upload (anonymous, while open).**
The applicant uploads a file through `platform/documents` first, then attaches the resulting
`document_id` here via `POST /applications/{reference_number}/documents`, authenticated the same
way as tracking (reference number + email in the body).

**Staff review.**
Staff move an application `submitted → under_review → eligible/ineligible` as documents are
verified and eligibility is checked. An `ineligible` or `rejected` decision is terminal.

**Merit list / offer.**
For an eligible pool, staff generate a merit list for a programme and cycle, then extend offers
(`POST /applications/{id}/offer`) to applicants, in merit order or by whatever process the
organisation runs manually. Some programmes decide by a selection round instead
(`practice/selection-process`) rather than a merit list; either way, the outcome lands here as an
offer, decided by staff — this module does not call selection-process's API to decide
automatically in this release (see §7).

**Offer decision (anonymous).**
The applicant accepts or declines the offer the same way they track status — reference number +
email. Accepting is the terminal, positive outcome: it raises
`admissions.application.accepted`, which `fees-accounts` consumes to invoice the confirmation
fee, matching the example already given in `docs/architecture/ARCHITECTURE.md`
("fees-accounts... subscribes to admissions.application.accepted and creates a fee invoice").

**Becoming a student (manual, outside this module).**
Once an application is `accepted`, an authorised staff member (admissions staff granted the
permission, or a registrar) creates the Person record directly in `student-information`,
passing a `source` reference back to this application. This is a deliberate manual step, not an
event subscription — matching the decision that students are never created automatically, only
by an authorised higher-level role.

## 6. Business rules

- **No applicant account is created, ever, by this module, before or after a decision.**
  Submission, tracking, document upload and offer decisions are all anonymous and verified by
  `reference_number` + `email`. This was an open question resolved for Issue #62: the
  alternative (an authenticated "applicant" identity session) was considered and explicitly
  declined in favour of this simpler, dependency-free model.
- **Organisation onboarding never touches this module.** An applicant and an Organisation Admin
  are different people solving different problems; nothing here assumes or reads
  `platform/tenancy`'s registration state.
- Every application belongs to exactly one organisation (`organisation_id`), scoped by
  row-level security.
- A `reference_number` is unique per organisation (not globally) and is generated by this module
  at submission, never supplied by the applicant.
- Status transitions are one-directional except that `under_review` may cycle while documents are
  requested and resupplied; `eligible`/`ineligible`/`rejected`/`accepted`/`declined`/`withdrawn`
  are terminal for that application.
- An application may optionally reference a `selection_process_round_id` (by id, no foreign key)
  when the programme's admission path runs through `practice/selection-process`; this module does
  not require that module's contract to exist to publish its own.
- A fee due for an admitted applicant is never computed here; `fees-accounts` computes and raises
  the invoice on `admissions.application.accepted`.

## 7. Integrations

- **platform/documents** — every uploaded file is a reference; this module stores only
  `document_id` and a type/label.
- **platform/audit** — every status change, document verification, offer and decision is
  audited.
- **finance-operations/fees-accounts** (consumer, not a dependency) — subscribes to
  `admissions.application.accepted` to raise an invoice. This module does not call
  fees-accounts' API and does not know whether a fee was raised.
- **student-information** (manual staff action, not a code dependency) — staff create a Person
  record there after acceptance, referencing this application as `source`. No event subscription,
  no synchronous call from either module to the other in this release.
- **practice/portfolio, practice/selection-process** (optional, by reference only) — an
  application may carry an optional id reference to a portfolio item or selection round when the
  programme's path uses them. This module does not call either module's API to make an
  automatic decision in this release; staff make the offer decision regardless of path.

## 8. Permissions

See `contracts/permissions.yaml`. Summary: `admissions:application:read`,
`admissions:application:manage`, `admissions:document:verify`, `admissions:merit-list:manage`,
`admissions:offer:manage`. Public endpoints (submit, track, document upload, offer decision)
require no permission key — they are unauthenticated by design (see §6).

## 9. Audit / state changes

Every status transition, document verification, offer issuance and offer decision is a state
change written to `platform/audit` (once the backend exists) and a published domain event.

## 10. Tenant considerations

- Every table (applications, application documents, merit lists, merit list entries, offers)
  carries `organisation_id` with row-level security.
- `reference_number` uniqueness is enforced within an organisation, not globally.
- The public tracking/upload/decision endpoints still resolve to exactly one organisation's data
  (the application's own `organisation_id`); a reference number from one organisation never
  matches a lookup scoped to another.

## 11. Acceptance criteria for Issue #62 (Week 1)

- [ ] `docs/prd.md` describes purpose, actors, scope, capabilities, workflows, business rules,
      integrations and tenant considerations, with no backend/frontend/database implementation detail.
- [ ] `contracts/openapi.yaml` fully describes every endpoint in §4/§5, including which are public
      (`security: []`) and which require a permission key.
- [ ] `contracts/events.yaml` includes `admissions.application.accepted` exactly as named in
      `docs/architecture/ARCHITECTURE.md`'s existing example.
- [ ] `contracts/permissions.yaml` lists every staff permission key; no key is required for the
      public applicant-facing endpoints.
- [ ] No dependency is introduced on an identity capability that does not exist (no applicant
      account creation anywhere in this module).
- [ ] No cross-module code dependency; `module.yaml` declares no dependency on
      `student-information`, `fees-accounts`, `portfolio` or `selection-process`.
