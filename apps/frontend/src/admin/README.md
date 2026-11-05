# Admin dashboard (`apps/frontend/src/admin`)

The super admin and organisation admin screens (ARCHITECTURE.md, "Organisations, plans"). This is
the design delivered for the client, served as a separate page of `@eos/frontend` so the existing
role-dashboard app (`index.html`, `src/App.tsx`) is untouched.

```
pnpm --filter @eos/frontend dev     # then open http://localhost:5173/admin.html
```

Routes are in the URL hash: `admin.html#/dashboard`, `#/admissions`, `#/users`, `#/roles`,
`#/dashboards`, `#/modules`, `#/modules/<id>`, `#/audit-logs`, `#/profile`, `#/access`, `#/login`.

## Signing in

Sign-in uses the identity API and token of the main app (`lib/auth.tsx`). A super admin sees the
platform view; an organisation admin sees their own organisation. Module screens still show sample
data until each module's backend is built.

- **Super admin:** the account the API creates from `EOS_SUPER_ADMIN_EMAIL` and
  `EOS_SUPER_ADMIN_PASSWORD` when it starts.
- **Organisation admin:** register an organisation (`POST /api/v1/tenancy/register`), verify it,
  and approve it as the super admin; then sign in with the admin email and password used to
  register.
- **Preview:** with no API running, or with `admin.html?preview=1`, the login page is a demo and any
  credentials sign in to sample data.

## Organisation approval (super admin)

New organisations register on the public site (`/#/register`) and verify their administrator's
email; they then wait for the platform's super admin. Only a signed-in super admin (live API, not
preview) sees, on the Dashboard:

- the **Pending Approvals** tile with the number of organisations awaiting approval (verified ones);
- the **Organisations awaiting approval** panel (`components/organisations/OrganisationApprovalQueue.tsx`):
  review an organisation, then approve it (optional reason) or reject it (reason required).
  Organisations whose administrator has not verified their email yet are listed as *Waiting for
  email verification* and cannot be decided on.

It calls `platform/tenancy` (`lib/organisationsAdmin.ts`): `GET /admin/organisations?status=pending_approval`
and `?status=pending_verification`, `GET /admin/organisations/{id}`, `POST /admin/organisations/{id}/approve`
and, for a rejection, `PUT /admin/organisations/{id}/status` with `{ status: "archived", reason }`. They need
`platform:organisations:read` / `manage` (super admin only). Approving makes the organisation
`active`, and its organisation admin can sign in. The buttons follow the status the drawer fetched,
so an organisation decided on elsewhere shows *No longer awaiting approval* (the API's 409 is handled
the same way). A 401 signs the super admin out. Organisation admins never see the queue.

## Layout

| Path | What |
|---|---|
| `main.tsx`, `App.tsx` | Entry (loaded by `apps/frontend/admin.html`) and routes |
| `pages/`, `components/`, `data/`, `types/` | The design's screens, shared UI, mock data |
| `assets/` | Photos and logos, bundled only with `admin.html` (`lib/assets.ts`) |
| `lib/router.tsx` | The react-router-dom API the screens use, on the URL hash |
| `lib/icons.tsx` | The lucide icons used, generated from lucide-react 1.52.0 (ISC) |
| `lib/charts.tsx` | The Recharts API the histogram uses, drawn as SVG with Recharts' layout rules |
| `admin.source.css` | The design's stylesheet (Tailwind 4 source) |
| `admin.css` | **Generated** from `admin.source.css` and the class names in this folder |

## Approved stack

The design was built with Tailwind, Recharts, lucide-react and react-router-dom, none of which
`@eos/frontend` may depend on (`docs/architecture/approved-stack.yaml`). Here it runs on React 18,
TypeScript and Vite only:

- styling is the plain CSS Tailwind generated for these exact class names (`admin.css`), so
  components keep their class names and render the same;
- routing, icons and charts are the small local modules in `lib/`, with the same APIs.

## Changing styles

`admin.css` contains only the utilities the current class names use. A class name that is not
already used somewhere in this folder has no CSS until `admin.css` is regenerated with the Tailwind
4.3.3 compiler from `admin.source.css` (outside this repo; Tailwind is not a dependency here).
Prefer classes that already appear in the design, or plain CSS in `admin.source.css` and
`admin.css`.

## Audit log

`#/audit-logs` (`pages/AuditPage.tsx`, `lib/auditAdmin.ts`) reads `platform/audit`'s `GET /audit/records`, 50 at a
time, newest first, with "Load more". An organisation admin sees their organisation's trail; a super admin sees the
platform's own records (approvals, impersonation, cross-organisation reads) and can choose an organisation to read its
trail, which the API itself records as a super admin action. The columns are what a record holds: when, the actor's
current name (or "System"), module, action, entity and summary, with a badge on a redacted record; search and the
module filter work on the records loaded. Records are append-only, so the page has no edit or delete. Export waits for
`POST /records/export`, which the API does not serve yet. In preview mode the page shows labelled sample events.


## Organisations and Subscriptions (super admin)

`#/organisations` (`pages/OrganisationsPage.tsx`) lists every organisation from `GET /tenancy/admin/organisations`
with its status, plan and trial, filtered on the page by status, plan, academy type and a search. Clicking a name shows
its details (`GET /tenancy/admin/organisations/{id}`: status reason, subscription, entitled modules, scheduled deletion).
A super admin can **suspend** an active organisation and **reactivate** a suspended one (`PUT …/{id}/status`); the
reason is required, and tenancy records it in the audit trail (`infra/runbooks/suspend-a-tenant.md` says when).
Registrations are approved on the Dashboard. Deleting, purging, exporting and impersonating stay API-only.

`#/subscriptions` (`pages/SubscriptionsPage.tsx`) lists the organisations that have a plan, with the published plans
from `GET /billing/plans`. A super admin can **change the plan** or **extend a trial** to the end of a chosen day
(`PUT /billing/admin/subscriptions/{id}`), each with a required reason that billing records.

Both pages and their sidebar entries are for a super admin only (an organisation admin sees neither; the API refuses
them anyway). Preview mode shows labelled samples and calls nothing.
