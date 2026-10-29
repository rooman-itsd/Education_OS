# web-portal-cms — data model

Tables owned entirely by this module, named `web_portal_cms_*` (the repo's convention for a module's own schema; the
Alembic version table is `web_portal_cms_alembic_version`). Every table carries `organisation_id` (not null) with
the forced `tenant_isolation` row-level-security policy. No foreign key to another module's tables; this module
stores no copy of `Organisation`, `Plan`, `Person` or `Application`.

## Entities

### Page
| Field | Notes |
|---|---|
| id | uuid |
| organisation_id | required |
| slug | `^[a-z0-9-]{1,120}$`; unique within the organisation; fixed after creation |
| title | at most 200 |
| type | `standard`, `landing`, `terms` |
| body | plain text, at most 20,000 |
| seo_description | optional, at most 300 |
| published, published_at | `published_at` is the last time it was published |
| created_by, updated_by, created_at, updated_at | |

### Announcement
| Field | Notes |
|---|---|
| id | uuid |
| organisation_id | required |
| title | at most 200 |
| body | plain text, at most 5,000 |
| starts_at, ends_at | optional display window; `ends_at` after `starts_at` |
| published, published_at | |
| created_by, updated_by, created_at, updated_at | |

### AuditEntry
| Field | Notes |
|---|---|
| id, organisation_id | |
| actor | user id |
| action, entity, entity_id | e.g. `published`, `announcement`, the announcement id |
| detail | JSON (title, slug) |
| occurred_at | |

Deleting a page or announcement removes its row; its audit rows stay.

## Relationships

None between the two entities, and none to another module's data.

## Ownership boundaries

- **Owns:** each organisation's CMS pages and announcements.
- **Does not own:** organisations, admin accounts, plans, subscriptions (`platform/tenancy`, `platform/billing`),
  Person or Application data. The marketing site and registration pages hold no data of their own: their copy is
  in `frontend/src/public/content.ts` and they call tenancy and billing directly.
