# web-portal-cms — screen inventory

## Public (the platform's own website; built in `frontend/src/public/`)

| Screen | Purpose | Calls |
|---|---|---|
| Home and features (`#/`, `#/features`), **built** | Education OS presenting itself to academies | none (copy in `content.ts`) |
| Plans & pricing (`#/signup`), **built** | The plan list; every organisation starts on the free trial | `GET /plans` (`platform/billing`, direct) |
| Create your organisation (`#/register`), **built** | Academy package picker and the organisation + administrator form | `GET /academy-types`, `POST /register` (`platform/tenancy`, direct) |
| Check your email, **built** | Asks the administrator to confirm the address | `POST /register/verify` (`platform/tenancy`, direct) |
| Email verification landing (`#/verify?token=…`), **built** | Confirms the emailed link or a pasted token | `POST /register/verify` (`platform/tenancy`, direct) |
| Waiting for approval, **built** | Shown once tenancy returns `pending_approval` | none |

An organisation's own pages and announcements are not shown here: they need a signed-in member (PRD §11 D1).

## Staff (CMS console, planned; this release ships the API)

| Screen | Purpose | Permission |
|---|---|---|
| Pages list | Drafts and published pages (`status` filter) | `web-portal-cms:page:manage` |
| Page editor | Create, edit, publish, unpublish, delete | `web-portal-cms:page:manage` |
| Announcements list | Drafts, published, scheduled and expired announcements | `web-portal-cms:announcement:manage` |
| Announcement editor | Create, edit (with display window), publish, unpublish, delete | `web-portal-cms:announcement:manage` |

## Dashboard widgets

| Widget id | Dashboard | Kind | Permission | Data |
|---|---|---|---|---|
| `web-portal-cms.announcements` | Applicant | list | `web-portal-cms:announcement:read` | `GET /announcements` |

It lists the organisation's currently visible announcements, newest first: title, a plain-text excerpt and the
date. Any signed-in member holds the read key (implicit `member` role), so the widget can be placed on other
dashboards without a new permission.
