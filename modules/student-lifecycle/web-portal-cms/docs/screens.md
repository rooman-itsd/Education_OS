# web-portal-cms — screen inventory

Week 1 scope is contracts and PRD only; no frontend code is built yet. This is the planned screen
list the contracts above are designed to support.

## Public

| Screen | Purpose | Calls |
|---|---|---|
| Home / public pages | Published CMS pages | `GET /pages`, `GET /pages/{slug}` (this module) |
| Announcements / notices | Published announcements | `GET /announcements` (this module) |
| Pricing / sign-up landing | Marketing copy plus the plan list | `GET /pages/{slug}` (this module, `scope=public`), `GET /plans` (`platform/billing`, direct call) |
| Sign-up form | Organisation + admin details, academy type, plan choice | `GET /academy-types` (`platform/tenancy`, direct), `POST /register` (`platform/tenancy`, direct) |
| Sign-up confirmation | "Check your email" | None — static/CMS content |
| Email verification landing | Confirms the emailed link | `POST /register/verify` (`platform/tenancy`, direct) |
| Waiting for approval | Shown after verification, before super-admin approval | None — static/CMS content |

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
