# student-information — user stories

## Registrar / student-information staff
- As a registrar, I can create a Person record for someone the organisation has confirmed as a
  student, so there is one authoritative record other modules can reference.
- As a registrar, I can search for an existing person by name, email or identity document number
  before creating a new record, so I don't create a duplicate.
- As a registrar, I can change a person's status with a reason (e.g. suspend, graduate, withdraw),
  so the organisation has an accurate, auditable lifecycle record.
- As a registrar, I can attach identity and supporting documents to a person's record, so
  verification evidence is kept against the right person.
- As a registrar, I can issue an ID card for an active person and revoke it later with a reason,
  so lost or superseded cards are tracked.

## Admissions staff
- As admissions staff who has been granted the permission, I can create a Person record for an
  applicant once their application is accepted, recording where they came from (`source`), so the
  handoff from admissions to the student record is traceable without admissions and
  student-information sharing a database.

## Student / learner
- As a student, I can view my own profile and contact details, so I can confirm what the
  organisation holds about me.
- As a student, I can update my own contact details (email, phone, address) where the
  organisation's permission grants allow it, so my record stays current.

## Other modules (consumers)
- As any module that needs to show a person's name or status, I can consume
  `student-information.person.*` events to keep a cached, read-only copy next to my own
  `person_id` reference, so I never need to call across module boundaries for every read.

## Explicitly not a user story here
- "As a prospective student, I sign up on the public website and get a student record" is
  deliberately **not** a story for this module. Public sign-up creates an organisation and its
  Organisation Admin (`web-portal-cms` + `platform/tenancy`); it never creates a Person record.
