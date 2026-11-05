# ADR-0008: Mobile through an installable web app (PWA), no native app for v1.0

- **Status:** proposed (the lead decides)
- **Date:** 2026-11-05
- **Deciders:** Faizan (lead), with apps and infrastructure (Srujan)

## Context
Students, staff and parents mostly reach Education OS from phones. #153 asks for mobile readiness: an installable
app, a shell that opens without a connection, push notifications, and a recorded decision on React Native.

The frontend is one React build (`apps/frontend`) served as static files: the dashboard shell (`index.html`, the
public site at `/` and the app at `/app`) and the admin console (`admin.html`). Every screen is already responsive.
The data belongs to organisations and their people (DPDP): a phone is often shared, and phones get lost.

## Decision
1. **v1.0 ships an installable progressive web app** from the existing build, with no second codebase:
   - `apps/frontend/public/manifest.webmanifest`: the name, start URL `/app`, standalone display, brand colours and icons
     (192, 512 and a maskable 512, plus a 180 icon for iOS), rendered from the brand emblem by
     `tools/scripts/make-pwa-icons.mjs`;
   - `apps/frontend/public/sw.js`, a hand-written service worker (Workbox is not on the approved stack), registered
     only in a production build (`src/pwa/register.ts`).
2. **What works offline is the app itself, never the data.** Pages are network first, falling back to the copy stored
   at the last visit, else `offline.html`. Built files (`/assets/`) and icons are cache first. **Requests to `/api/`
   are never handled or stored by the worker**: nothing an organisation or a person owns stays on the device. Unit
   tests enforce it (`apps/frontend/tests/pwa.test.ts`).
3. **No React Native (or other native app) for v1.0.** Revisit once there is usage data showing a need a PWA cannot
   meet, for example background location, deep device integration, or app-store distribution an institution requires.
4. **No push notifications for v1.0.** They need a server side that does not exist: VAPID keys, a subscription store
   per user and organisation, a sender in platform/notification, and consent. Email (platform/notification) stays the
   channel. Push is a later ADR with platform/notification.
5. nginx serves `sw.js` and `manifest.webmanifest` with `Cache-Control: no-cache` (and the manifest's media type, which
   nginx's own list lacks), so a change reaches installed apps the day it is deployed (`infra/docker/nginx.*.conf`).

## Consequences
- One codebase and one release for desktop and phone; installing is "Add to Home screen" from the site.
- Offline means the app opens and says it needs a connection. Reading or changing data offline is not supported, by
  design, until there is a decision on which data may be kept on a device and how it is wiped.
- iOS supports installed web apps with limits (push only from iOS 16.4, storage the system may clear); acceptable
  while push is out of scope.
- `sw.js` carries a `VERSION`; a change in its behaviour bumps it, and the new worker deletes the old caches.
- The nginx change is a repository file: the hosts pick it up when their vhost is next installed.

## Alternatives considered
- **React Native app**: a second codebase, app-store releases and reviews, and native modules for little gain while
  every screen is a dashboard of server data. Rejected for v1.0 (decision 3).
- **Workbox or vite-plugin-pwa**: less code to write, but not on the approved stack; the worker is small enough to
  write and test by hand.
- **Caching API answers for offline reading**: rejected for now, as it keeps personal data on devices (decision 2).
