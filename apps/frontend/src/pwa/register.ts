// Registers the service worker (apps/frontend/public/sw.js, #153) for both pages: the dashboard shell (main.tsx) and the
// admin console (admin/main.tsx). Only in a production build: in development a worker would keep serving yesterday's
// files while someone edits them, and tests have no worker at all.

export interface ServiceWorkerHost {
  serviceWorker?: { register: (url: string, options?: { scope?: string }) => Promise<unknown> };
}

/** Returns true when it asked the browser to register the worker. Failures are logged, never thrown: the app works
 *  without a worker, only not offline. */
export function registerServiceWorker(
  production: boolean = import.meta.env.PROD,
  nav: ServiceWorkerHost = navigator,
  win: Pick<Window, "addEventListener"> = window,
): boolean {
  if (!production || !nav.serviceWorker) return false;
  const sw = nav.serviceWorker;
  win.addEventListener("load", () => {
    sw.register("/sw.js", { scope: "/" }).catch((e: unknown) => console.warn("service worker not registered", e));
  });
  return true;
}
