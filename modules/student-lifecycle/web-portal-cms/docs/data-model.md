# web-portal-cms — data model

One schema (`web_portal_cms`), owned entirely by this module. No cross-schema foreign keys
(module-standard rule 2). This module stores no copy of `Organisation`, `Plan`, `Person` or
`Application` — those remain exclusively owned by `platform/tenancy`, `platform/billing`,
`student-information` and `admissions` respectively.

## Entities

### Page
| Field | Notes |
|---|---|
| id | uuid |
| organisation_id | **nullable** — see the module-standard rule 11 exception below |
| slug | unique within its scope (per organisation, or among `public`-scope pages) |
| title, body, seo_description | |
| type | standard, landing, signup_marketing, terms |
| published, published_at | |
| created_at, updated_at | |

### Announcement
| Field | Notes |
|---|---|
| id | uuid |
| organisation_id | required — announcements always belong to an organisation that already exists |
| title, body | |
| starts_at, ends_at | nullable display window |
| published, published_at | |
| created_at, updated_at | |

## The `organisation_id` exception on Page

Module-standard rule 11 requires `organisation_id` and row-level security on every table. `Page`
is the one deliberate, narrow exception: a `scope=public` page (the sign-up page's own marketing
copy, terms of service) is read by a visitor who has no organisation yet, so it cannot carry an
`organisation_id`. This mirrors `platform/tenancy`'s own `organisation` table, which the
architecture already documents as "the one schema whose tables are not themselves tenant-scoped,
because they define the tenants." Here, `public`-scope pages are content that exists *before* any
tenant does. Every other `Page` row (type `standard`/`landing`, scope `organisation`) and every
`Announcement` row carries `organisation_id` with RLS as normal.

## Relationships

None — both entities are standalone within this module's schema. Neither references
`platform/tenancy`'s `Organisation`, `platform/billing`'s `Plan`, `student-information`'s
`Person`, or `admissions`' `Application` by id or otherwise; this module has no relationship to
any of them in its data model.

## Ownership boundaries

- **This module owns:** CMS pages and announcements, including the sign-up page's own marketing
  content.
- **This module does not own:** the organisation record, the admin account, plans, subscriptions
  (all `platform/tenancy` + `platform/billing`), or any Person/Application data. Nothing in this
  schema references those entities even by id — the sign-up flow is a client-side composition of
  three independent public APIs (this module's content, billing's plans, tenancy's registration),
  not a server-side join or shared record.
