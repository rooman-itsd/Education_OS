# web-portal-cms

**Domain:** student-lifecycle  
**Kind:** feature  
**Status:** in progress (public site and registration built; CMS for issue #106)  
**Owner:** Praveen (@praveen-rooman)

Public website, CMS marketing pages, announcements, and the organisation sign-up & approval experience.

---

## Scope
Two parts: the platform's public website with the organisation sign-up pages, and each organisation's CMS
(pages and announcements written by its editors and read by its signed-in members; the Applicant dashboard's
`web-portal-cms.announcements` widget). Reading the CMS needs a signed-in member of the organisation; anonymous
reading is a later step (docs/prd.md §11, decision D1). The sign-up page composes `platform/billing`'s existing `GET /plans` and
`platform/tenancy`'s existing `GET /academy-types` / `POST /register` / `POST /register/verify`
directly — this module does not duplicate registration or plan logic, and never creates an
organisation, a plan, a Person/Student record, or an admissions application.

Explicitly not this module's responsibility: organisation registration and entitlement
(`platform/tenancy`), plans/subscriptions (`platform/billing`), creating a Person/Student record
(`student-information`, a manual staff action), or the admissions funnel (`admissions`, its own
anonymous flow). See [docs/prd.md](docs/prd.md) for the full scope.

## Public website and organisation registration

The public site is served at `/` (`frontend/src/public/PublicSite.tsx`, mounted by
`apps/frontend/src/main.tsx`); the dashboard app is at `/app`. Routes are in the URL hash:

| Route | Page |
|---|---|
| `#/` | Home |
| `#/features` | Features: the module catalogue with an honest status for each |
| `#/signup` | Plans & pricing (`GET /billing/plans`) |
| `#/register` | Create your organisation: academy package picker and form (`POST /tenancy/register`) |
| `#/verify?token=…` | Where the verification email's link lands (`POST /tenancy/register/verify`) |

How an organisation goes live (ADR-0005; registration itself is `platform/tenancy`'s):

1. **Register** at `#/register`: choose the academy package (one per organisation), enter the
   organisation and its first administrator. Tenancy creates the organisation as
   `pending_verification`, together with its organisation admin account.
2. **Verify the email.** Where the API returns the token (`EOS_DEV_MODE=true`, local and staging)
   the page confirms it at once; otherwise the administrator pastes the emailed token or opens the
   `#/verify?token=…` link. The organisation becomes `pending_approval`.
3. **Super admin approval.** The request goes to the platform's super admin only, never to another
   organisation. The super admin approves it through `platform/tenancy`'s approve endpoint; the
   "Organisations awaiting approval" queue on the admin console dashboard (`admin.html`) is a separate
   PR (#270). Approving makes the organisation `active`.
4. **Sign in.** Only then can the organisation admin sign in at `/app`; before approval sign-in is
   refused. Each organisation has its own admin; there is one super admin for the whole platform.

Not yet built (follow-up): the approval email (`platform/notification` with the SMTP adapter in
`integrations/messaging-providers`).

## CMS: pages and announcements (issue #106)

Each organisation's editors (`web-portal-cms-editor`, `org-admin`) write pages and announcements as drafts and
publish them; every signed-in member of the organisation reads what is published (announcements only inside their
display window) through the implicit `member` role. Drafts and out-of-window announcements answer 404 to readers.
Bodies are plain text and are never rendered as HTML. The decisions behind this are in
[docs/prd.md](docs/prd.md) §11.

| Widget | Dashboard | Kind | Permission | Data |
|---|---|---|---|---|
| `web-portal-cms.announcements` | Applicant | list | `web-portal-cms:announcement:read` | `GET /announcements` |

**What the host must provide:** registration in both `modules.enabled.yaml` files (done). Anonymous reading of an
organisation's content needs the gateway to let `/api/v1/web-portal-cms/public/{org_slug}/*` through, the same
change already requested for admissions; until then reading needs a signed-in member.

## Run and test
```
.venv\Scripts\python.exe -m pytest modules/student-lifecycle/web-portal-cms/backend/tests
pnpm --filter @eos/web-portal-cms test
pnpm --filter @eos/web-portal-cms typecheck
cd modules/student-lifecycle/web-portal-cms/db && alembic upgrade head    # uses EOS_DATABASE_URL
pnpm --filter e2e exec playwright test dashboards/applicant.spec.ts      # the Applicant journey
```

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

## Layout
| Path | Purpose |
|---|---|
| `docs/` | PRD, features reference, user stories, screens |
| `contracts/` | OpenAPI specs, events, permissions |
| `frontend/src/public/` | Public site shell (`PublicSite.tsx`), pages (`HomePage`, `FeaturesPage`, `SignUpPage`), components, and styles (`public.css`) |
| `frontend/src/api/` | `public-client.ts` (billing plans, tenancy registration) and `client.ts` (the CMS, for widgets) |
| `frontend/src/widgets/` | `web-portal-cms.announcements` |
| `backend/` | The CMS: domain rules, models, service and routes (`eos_web_portal_cms`) with tests |
| `db/` | Alembic chain (`web_portal_cms_alembic_version`): pages, announcements, audit, each with row-level security |

---

## Porting this module to another repo

Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
