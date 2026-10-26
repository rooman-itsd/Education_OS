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
