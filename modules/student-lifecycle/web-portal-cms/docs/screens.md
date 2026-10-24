# web-portal-cms — screen inventory

The public screens marked **built** exist in `frontend/src/public/`; the rest are planned and the
contracts above are designed to support them.

## Public

| Screen | Purpose | Calls |
|---|---|---|
| Home / public pages | Published CMS pages | `GET /pages`, `GET /pages/{slug}` (this module) |
| Announcements / notices | Published announcements | `GET /announcements` (this module) |
| Plans & pricing (`#/signup`), **built** | The plan list; every organisation starts on the free trial | `GET /plans` (`platform/billing`, direct call) |
| Create your organisation (`#/register`), **built** | Academy package picker (one choice) and the organisation + administrator form. No plan choice: registration always starts the trial | `GET /academy-types`, `POST /register` (`platform/tenancy`, direct) |
| Check your email (after submitting), **built** | Asks the administrator to confirm the address; confirms automatically where the API returns the token (dev mode) | `POST /register/verify` (`platform/tenancy`, direct) |
| Email verification landing (`#/verify?token=…`), **built** | Confirms the emailed link or a pasted token, then removes the token from the address bar | `POST /register/verify` (`platform/tenancy`, direct) |
| Waiting for approval, **built** | Shown once tenancy returns `pending_approval`; the request is now with the platform's super admin | None |

## Staff (CMS console)

| Screen | Purpose | Primary permission |
|---|---|---|
| Pages list | Manage pages for the organisation | `web-portal-cms:page:manage` |
| Page editor | Create/edit/publish a page | `web-portal-cms:page:manage` |
| Announcements list | Manage announcements | `web-portal-cms:announcement:manage` |
| Announcement editor | Create/edit/publish an announcement | `web-portal-cms:announcement:manage` |

## Dashboard widgets

`platform/identity/config/dashboards/applicant.yaml` lists `web-portal-cms.announcements` as a
widget id for the Applicant role. That widget reads `GET /announcements` scoped to the
organisation the applicant applied to — unaffected by this module's sign-up scope, since by the
time an applicant exists the organisation they're applying to already exists. No change to that
dashboard file is made here (owned by the Architecture lead).
