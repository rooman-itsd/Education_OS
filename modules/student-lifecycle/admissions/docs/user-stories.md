# admissions — user stories

## Applicant (public, no account)
- As an applicant, I can submit an application with my own details, programme and academic year,
  without creating an account, so applying has no sign-up friction.
- As an applicant, I can track my application's status using my reference number and email, so I
  don't need to remember a password.
- As an applicant, I can upload supporting documents against my application the same way, so I
  don't need an account to complete my application.
- As an applicant, I can accept or decline an offer the same way, so the whole funnel works
  without me ever holding a login.

## Admissions staff
- As admissions staff, I can list and search applications in my organisation, so I can work
  through the queue.
- As admissions staff, I can verify or reject an uploaded document with a note, so applicants know
  what's missing.
- As admissions staff, I can move an application through review, eligibility and rejection
  states with a reason, so the decision trail is clear.
- As admissions staff, I can generate a merit list for a programme and academic year, then publish
  it, so it becomes visible.
- As admissions staff, I can extend an offer on an eligible application, so the applicant can
  accept or decline it.

## Department admin
- As a department admin, I can see applications and merit lists for my department's programmes,
  so I can review decisions without running the whole funnel myself.

## Other modules (consumers, not callers)
- As `fees-accounts`, I can consume `admissions.application.accepted` to raise a confirmation fee
  invoice, without ever calling admissions' API or reading its tables.
- As a registrar using `student-information`, I can create a Person record once I see (through my
  own tools, not an automatic subscription) that an application was accepted, referencing it as
  `source` — a manual, authorised action, never automatic.

## Explicitly not a user story here
- "As an applicant, I sign in to see my dashboard" is **not** a story for this module in this
  release — submission, tracking and offer decisions are all anonymous by design (see
  `docs/prd.md` §6). If an authenticated applicant experience is wanted later, it is a separate,
  explicit decision and a new dependency on `platform/identity`, not something this module assumes.
