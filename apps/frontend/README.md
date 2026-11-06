# apps/frontend

The web frontend: React + TypeScript + Vite. Package `@eos/frontend`.

Responsive web client (also served as PWA). Composes module frontends. No business logic.

## Dashboard shell

`src/dashboard/` renders the role-based dashboard:

1. `layouts.ts` reads every `platform/identity/config/dashboards/<role>.yaml` at build time.
2. `modules.ts` registers the widgets of every module, platform service and integration listed in
   `config/modules.enabled.yaml` (development override; the institution profile is the source once
   identity ships, ADR-0004).
3. `Dashboard.tsx` resolves the role's widget ids, hides those the viewer lacks permission
   for, and renders the rest in a 4-column grid (2 on tablet, 1 on phone). An id with no
   registered widget shows a "Not built yet" card so gaps are visible.

Until `platform/identity` ships, the role comes from `?role=<id>` (switcher in the top bar)
and every permission is granted. See `App.tsx`.

```
pnpm install                      # repo root, once
pnpm --filter @eos/frontend dev        # http://localhost:5173/?role=student
pnpm --filter @eos/frontend test
pnpm --filter @eos/frontend build
```

## Installable app (PWA)

The build is an installable web app ([ADR-0008](../../docs/architecture/adr/0008-mobile-pwa.md), #153):
`public/manifest.webmanifest`, the icons in `public/icons/` (made from the brand emblem by
`tools/scripts/make-pwa-icons.mjs`), and a hand-written service worker, `public/sw.js`, registered only in a
production build (`src/pwa/register.ts`). Pages open offline from the copy stored at the last visit, else
`public/offline.html`; built files are cache first; **requests to `/api/` are never handled or stored**, so no
organisation's or person's data stays on a device (`tests/pwa.test.ts` holds the worker to that). When `sw.js`
changes its behaviour, bump its `VERSION`: the new worker deletes the old caches. Push notifications are not part of
v1.0.
