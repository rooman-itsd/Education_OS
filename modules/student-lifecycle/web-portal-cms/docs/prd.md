# web-portal-cms — PRD

**Domain:** student-lifecycle · **Tier:** common · **Owner:** Praveen (@praveen-rooman) · **Issues:** #62 (contracts),
#98 (registration), #106 (CMS backend and announcements widget)

## 1. Purpose

web-portal-cms has two parts:

1. **The platform's public website and organisation sign-up** (built in #236 and #98): Education OS presenting
   itself to academies, the plans page, and the registration and email-verification pages. Its content is part of
   the frontend code; it composes `platform/billing` (plans) and `platform/tenancy` (registration) and never
   re-implements them.
2. **Each organisation's CMS** (#106): pages and announcements an organisation's editors write and publish for the
   people of that organisation — applicants, students, faculty and staff — who read them after signing in. The
   Applicant dashboard shows the organisation's current announcements (`web-portal-cms.announcements`).

## 2. Users / actors

| Actor | Relationship |
|---|---|
| Public visitor | Browses the platform's marketing site and plans; no account |
| Prospective organisation (academy) | Registers through `platform/tenancy` from the sign-up pages; becomes the Organisation Admin once approved |
| Member of an organisation (any signed-in user: applicant, student, faculty, staff, management) | Reads that organisation's published pages and current announcements |
| CMS editor (`web-portal-cms-editor`) and Organisation Admin (`org-admin`) | Write, publish, unpublish and delete their organisation's pages and announcements |
| Super admin | Approves new organisations (`platform/tenancy`); not a CMS actor |

## 3. Scope

**In scope**
- The platform's marketing site, plans page, registration and verification pages (built; unchanged by #106).
- Per-organisation CMS pages (`standard`, `landing`, `terms`) and announcements with an optional display window;
  drafts, publish and unpublish, delete.
- Reading published content for any signed-in member of the organisation; the announcements widget.

**Out of scope (this release)**
- Organisation registration, plans and accounts: `platform/tenancy` and `platform/billing` own them.
- Anonymous reading of an organisation's pages and announcements (see §11 D1).
- Rich text or HTML bodies (§11 D3); an approval workflow, page-view analytics and tenders (§11 D8).
- Creating a Person, Student or admissions Application of any kind.
- The staff CMS screens (`docs/screens.md`): this release ships the API and the widget.

## 4. Capabilities

1. Serve the marketing site, plans, registration and verification pages (built).
2. Editors create pages as drafts, edit them (slug fixed), publish, unpublish and delete them.
3. Editors create announcements as drafts with an optional display window, edit, publish, unpublish and delete them.
4. Editors list drafts, published items or everything; members list and read only what is visible to them.
5. Show the organisation's current announcements on the Applicant dashboard.

## 5. Important workflows

**Organisation sign-up (built in #98).**

```
Visitor opens the plans page → GET /plans (platform/billing, public)
  → "Create your organisation" → GET /academy-types, POST /register (platform/tenancy, public)
  → "Check your email" → POST /register/verify (platform/tenancy, public)
  → organisation is pending_approval → the super admin approves → active; the Organisation Admin can sign in
```

The frontend calls billing and tenancy directly; web-portal-cms adds no endpoint for registration.

**Publishing an announcement.** An editor creates a draft (title, body, optional `starts_at` and `ends_at`), then
publishes it. Members see it from `starts_at` (or at once) until `ends_at` (or indefinitely). Unpublishing hides it;
deleting removes it. Each change is audited; publishing and unpublishing publish an event.

**Publishing a page.** The same, with a slug unique within the organisation and no display window.

**Reading.** A signed-in member lists the organisation's published pages and visible announcements, and opens one.
A draft, or an announcement outside its window, does not exist for them (404).

## 6. Business rules

1. **This is organisation sign-up, not student or applicant sign-up.** Nothing here creates a Person
   (`student-information`) or an Application (`admissions`).
2. **No second source of truth** for organisations or plans.
3. Every page and announcement belongs to exactly one organisation; there is no platform-level CMS content.
4. A page's slug matches `^[a-z0-9-]{1,120}$`, is unique within the organisation, and cannot be changed after
   creation.
5. An announcement's `ends_at`, when both are set, is after its `starts_at`.
6. An announcement is **visible** when it is published and `starts_at ≤ now < ends_at` (a missing bound is open).
   A page is visible when it is published.
7. Without `manage` permission, only visible items exist: drafts and out-of-window announcements answer 404.
8. Publishing a published item, or unpublishing a draft, is refused (409); editing does not change publish state.
9. Bodies are plain text, at most 20,000 characters for a page and 5,000 for an announcement; titles at most 200.

## 7. Integrations

- **platform/billing**, **platform/tenancy** (existing contracts, not modified): called directly by the sign-up
  pages.
- **platform/audit**: every CMS change is written to this module's audit table until audit has a service.
- **platform/identity**: every organisation user holds the implicit `member` role, which grants the read keys.
- **student-information, admissions**: no integration.

## 8. Permissions

| Key | Lets the holder |
|---|---|
| `web-portal-cms:page:read` | list and read published pages |
| `web-portal-cms:page:manage` | create, edit, publish, unpublish, delete pages; see drafts |
| `web-portal-cms:announcement:read` | list and read visible announcements |
| `web-portal-cms:announcement:manage` | create, edit, publish, unpublish, delete announcements; see drafts and out-of-window ones |

Roles: `member` (implicit, every organisation user) holds both read keys; `web-portal-cms-editor` and `org-admin`
hold all four. The registration pages need no key: they call tenancy's public endpoints.

## 9. Audit / state changes

Page and announcement create, update, publish, unpublish and delete are audited; publish and unpublish (and deleting
a published item) publish an event.

## 10. Tenant considerations

- Both tables carry `organisation_id` (not null) with the forced `tenant_isolation` policy; a member of one
  organisation never sees another's content.
- Slugs are unique within an organisation, not globally.
- Event payloads never carry `organisation_id`: it travels on the envelope.

## 11. Decisions (#106, taken from what is on `main`; reviewers may change them)

| # | Decision | Why |
|---|---|---|
| D1 | Reading needs a signed-in member of the organisation; the read keys go to the implicit `member` role. Anonymous reads (for example `/public/{org_slug}/announcements`) come later | The host gateway refuses tokenless requests to feature modules, and an anonymous request names no organisation; no per-organisation public site exists yet |
| D2 | No pre-organisation pages: the `scope=public` parameter and the `signup_marketing` page type are removed; every page has `organisation_id` | A null `organisation_id` can never pass row-level security; the marketing and terms copy is already in `frontend/src/public/content.ts` |
| D3 | Bodies are plain text, displayed as text with line breaks; never HTML | No HTML sanitiser is on `docs/architecture/approved-stack.yaml`; plain text rules out stored XSS |
| D4 | Editors list drafts with `status=draft\|published\|all` | The editor needs to find unpublished work |
| D5 | Without `manage`, drafts and out-of-window announcements answer 404 | Unpublished content must not leak, not even its existence |
| D6 | Event payloads carry ids and title only: no `organisation_id`, no body | platform/event-bus envelope rule; bodies can be long |
| D7 | Deleting a published item publishes its `unpublished` event first | Consumers holding a copy drop it |
| D8 | Approval workflow, page views and tenders (super admin console sample) are out of scope | Not part of issue #106 |

## 12. Acceptance criteria for issue #106

- [ ] Both tables have `organisation_id` and the forced row-level-security policy; the cross-tenant leak test passes.
- [ ] Readers never see drafts or out-of-window announcements; editors can.
- [ ] Widget `web-portal-cms.announcements` is exported with tests and shows on the Applicant dashboard.
- [ ] Registered in `apps/backend` and `apps/frontend`; `env.example`, README and CHANGELOG complete.
- [ ] The registration pages keep working unchanged.
