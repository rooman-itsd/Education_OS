/* Education OS service worker (#153; docs/architecture/adr/0008-mobile-pwa.md).
 *
 * It makes the app installable and lets its pages open without a connection. It never stores what the API answers:
 * organisations' and people's data stay on the server, so a shared or lost phone keeps nothing of them.
 *
 *   /api/...          never touched: the browser talks to the network as if there were no worker
 *   /assets/...       cache first: Vite names these by their content, so a stored copy is always right
 *   /icons/...        cache first too (the offline page shows one)
 *   a page (navigate) network first; offline, the copy stored at the last visit, else offline.html
 *   anything else     not touched (other origins such as fonts, POSTs, files outside /assets/)
 *
 * Hand-written: Workbox is not on the approved stack. Bump VERSION when this file's behaviour changes; the new worker
 * deletes the old version's caches when it takes over.
 */
const VERSION = "v1";
const PAGES = `eos-pages-${VERSION}`;
const ASSETS = `eos-assets-${VERSION}`;
const OFFLINE_URL = "/offline.html";
const OFFLINE_ICON = "/icons/icon-192.png";
/** Old builds' files pile up in the asset cache; keep this many, the newest. */
const MAX_ASSETS = 120;

/** What the worker does with a request: "none" (leave it to the network), "asset" or "page". */
function strategyFor(request) {
  if (request.method !== "GET") return "none";
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return "none";
  if (url.pathname === "/api" || url.pathname.startsWith("/api/")) return "none";
  if (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/icons/")) return "asset";
  if (request.mode === "navigate") return "page";
  return "none";
}

/** A page is stored under its path, without query string or hash: /app, /, /admin.html. */
function pageKey(request) {
  return new URL(request.url).pathname;
}

async function trim(cache) {
  const keys = await cache.keys();
  for (const key of keys.slice(0, Math.max(0, keys.length - MAX_ASSETS))) await cache.delete(key);
}

async function asset(request) {
  const cache = await caches.open(ASSETS);
  const stored = await cache.match(request);
  if (stored) return stored;
  const response = await fetch(request);
  if (response.ok) {
    await cache.put(request, response.clone());
    await trim(cache);
  }
  return response;
}

async function page(request) {
  const cache = await caches.open(PAGES);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(pageKey(request), response.clone());
    return response;
  } catch {
    return (await cache.match(pageKey(request))) || (await cache.match(OFFLINE_URL)) || Response.error();
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(PAGES)
      .then((cache) => cache.add(OFFLINE_URL))
      .then(() => caches.open(ASSETS))
      .then((cache) => cache.add(OFFLINE_ICON))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  const keep = [PAGES, ASSETS];
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("eos-") && !keep.includes(k)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const strategy = strategyFor(event.request);
  if (strategy === "asset") event.respondWith(asset(event.request));
  else if (strategy === "page") event.respondWith(page(event.request));
  // "none": no respondWith, so the browser handles the request itself.
});
