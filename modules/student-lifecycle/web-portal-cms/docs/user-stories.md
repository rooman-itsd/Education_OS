# web-portal-cms — user stories

## Public visitor
- As a visitor, I can read an organisation's published pages and announcements without an
  account, so the public site works like any website.
- As a prospective organisation, I can see the available plans (from `platform/billing`) and
  academy types (from `platform/tenancy`) on the sign-up page, so I can choose before committing.
- As a prospective organisation, I can submit my organisation's sign-up — organisation details,
  academy type, chosen plan, and my own admin details — and have it go straight to
  `platform/tenancy`'s registration, so one submission creates both the organisation and my
  Organisation Admin account.
- As a prospective organisation, I see a confirmation page telling me to verify my email, then a
  "waiting for approval" page, so I know what happens next without needing to call anyone.

## CMS editor (organisation staff)
- As a CMS editor, I can create, edit and publish a page for my own organisation's public site, so
  I can keep the site current without a deploy.
- As a CMS editor, I can create and publish an announcement, so time-sensitive notices reach
  visitors quickly.
- As a CMS editor, I can unpublish a page or announcement without deleting it, so I can take
  something down temporarily.

## Explicitly not a user story here
- "As a student, I sign up on the public website" is **not** a story for this module. Organisation
  sign-up never creates a student, a Person record, or an admissions application — those are
  `student-information` (staff-created) and `admissions` (its own anonymous application flow),
  entirely separate from this page.
- "As a visitor, I register my organisation through a web-portal-cms API" is also not accurate:
  the actual registration call goes to `platform/tenancy`'s existing `POST /register`, not to any
  endpoint this module owns.
