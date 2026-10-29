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

Not yet built (follow-ups): the approval email (`platform/notification` with the SMTP adapter in
`integrations/messaging-providers`), and the CMS pages and announcements of this module's contract.

Tests: `pnpm --filter @eos/web-portal-cms test` (Vitest, jsdom, Testing Library).

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
| `frontend/src/api/` | Public API client fetching billing plans and institution types |
| `backend/` | Backend scaffold (business logic delegated to core platform services) |

---

## Porting this module to another repo

Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
