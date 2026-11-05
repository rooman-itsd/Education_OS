// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";
import { registerServiceWorker } from "../src/pwa/register";

/**
 * public/sw.js runs in the browser's worker scope, so it is loaded here with a fake `self`, `caches` and `fetch` and
 * driven through its install, activate and fetch listeners. What matters most: the API is never cached.
 */

const ORIGIN = "https://educationos.example.com";
const SW = readFileSync(new URL("../public/sw.js", import.meta.url), "utf8");

class FakeCache {
  store = new Map<string, Response>();
  private key(r: Request | string) {
    return new URL(typeof r === "string" ? r : r.url, ORIGIN).toString();
  }
  async match(r: Request | string) {
    return this.store.get(this.key(r))?.clone();
  }
  async put(r: Request | string, res: Response) {
    this.store.set(this.key(r), res);
  }
  async add(url: string) {
    this.store.set(this.key(url), new Response(`stored ${url}`));
  }
  async keys() {
    return [...this.store.keys()].map((k) => new Request(k));
  }
  async delete(r: Request | string) {
    return this.store.delete(this.key(r));
  }
}

function load({ online = true } = {}) {
  const caches = new Map<string, FakeCache>();
  const cacheStorage = {
    open: async (name: string) => caches.get(name) ?? (caches.set(name, new FakeCache()), caches.get(name)!),
    keys: async () => [...caches.keys()],
    delete: async (name: string) => caches.delete(name),
  };
  const net = { online };
  const fetch = vi.fn(async (r: Request) => {
    if (!net.online) throw new TypeError("Failed to fetch");
    return new Response(`network ${new URL(r.url).pathname}`, { status: 200 });
  });
  const listeners: Record<string, (e: unknown) => void> = {};
  const self = {
    location: new URL(ORIGIN),
    addEventListener: (type: string, fn: (e: unknown) => void) => (listeners[type] = fn),
    skipWaiting: vi.fn(async () => {}),
    clients: { claim: vi.fn(async () => {}) },
  };
  new Function("self", "caches", "fetch", "Response", "Request", "URL", SW)(self, cacheStorage, fetch, Response, Request, URL);

  /** Dispatch a fetch event; undefined means the worker left the request to the browser. */
  const request = async (path: string, init: RequestInit & { mode?: RequestMode } = {}) => {
    let answer: Promise<Response> | undefined;
    const req = new Request(new URL(path, ORIGIN), { method: init.method ?? "GET" });
    Object.defineProperty(req, "mode", { value: init.mode ?? "cors" });
    listeners.fetch!({ request: req, respondWith: (p: Promise<Response>) => (answer = p) });
    return answer ? await answer : undefined;
  };
  const lifecycle = async (type: "install" | "activate") => {
    let done: Promise<unknown> = Promise.resolve();
    listeners[type]!({ waitUntil: (p: Promise<unknown>) => (done = p) });
    await done;
  };
  return { caches, fetch, net, request, lifecycle, self };
}

describe("service worker", () => {
  it("never answers or stores an API request, online or offline", async () => {
    const sw = load();
    await sw.lifecycle("install");
    expect(await sw.request("/api/v1/identity/auth/me")).toBeUndefined();
    expect(await sw.request("/api/v1/billing/subscription", { mode: "navigate" })).toBeUndefined();
    expect(await sw.request("/api")).toBeUndefined();
    sw.net.online = false;
    expect(await sw.request("/api/v1/audit/records?limit=5")).toBeUndefined();
    const stored = [...sw.caches.values()].flatMap((c) => [...c.store.keys()]);
    expect(stored.some((k) => k.includes("/api"))).toBe(false);
    expect(sw.fetch).not.toHaveBeenCalled(); // the browser, not the worker, made those requests
  });

  it("leaves POSTs and other origins to the browser", async () => {
    const sw = load();
    expect(await sw.request("/app", { method: "POST", mode: "navigate" })).toBeUndefined();
    expect(await sw.request("https://fonts.googleapis.com/css2?family=Inter")).toBeUndefined();
  });

  it("stores the offline page and its icon on install, and takes over at once", async () => {
    const sw = load();
    await sw.lifecycle("install");
    expect(await sw.caches.get("eos-pages-v1")!.match("/offline.html")).toBeTruthy();
    expect(await sw.caches.get("eos-assets-v1")!.match("/icons/icon-192.png")).toBeTruthy();
    expect(sw.self.skipWaiting).toHaveBeenCalled();
  });

  it("serves built assets from the cache after the first load", async () => {
    const sw = load();
    const first = await sw.request("/assets/index-abc123.js");
    expect(await first!.text()).toBe("network /assets/index-abc123.js");
    sw.net.online = false;
    const again = await sw.request("/assets/index-abc123.js");
    expect(await again!.text()).toBe("network /assets/index-abc123.js");
    expect(sw.fetch).toHaveBeenCalledTimes(1);
  });

  it("loads pages from the network, and offline shows the last stored copy, else the offline page", async () => {
    const sw = load();
    await sw.lifecycle("install");
    expect(await (await sw.request("/app?x=1", { mode: "navigate" }))!.text()).toBe("network /app");
    sw.net.online = false;
    expect(await (await sw.request("/app", { mode: "navigate" }))!.text()).toBe("network /app"); // stored under /app
    expect(await (await sw.request("/admin.html", { mode: "navigate" }))!.text()).toBe("stored /offline.html");
  });

  it("deletes the caches of an older version when it takes over, and only its own", async () => {
    const sw = load();
    for (const name of ["eos-pages-v0", "eos-assets-v0", "another-app-cache"]) sw.caches.set(name, new FakeCache());
    await sw.lifecycle("install");
    await sw.lifecycle("activate");
    expect([...sw.caches.keys()].sort()).toEqual(["another-app-cache", "eos-assets-v1", "eos-pages-v1"]);
    expect(sw.self.clients.claim).toHaveBeenCalled();
  });
});

describe("registerServiceWorker", () => {
  const host = () => {
    const register = vi.fn(async () => ({}));
    const handlers: Record<string, () => void> = {};
    return {
      register,
      nav: { serviceWorker: { register } },
      win: { addEventListener: (t: string, fn: () => void) => (handlers[t] = fn) } as unknown as Window,
      load: () => handlers.load?.(),
    };
  };

  it("registers /sw.js for the whole site after the page loads, in a production build", () => {
    const h = host();
    expect(registerServiceWorker(true, h.nav, h.win)).toBe(true);
    expect(h.register).not.toHaveBeenCalled();
    h.load();
    expect(h.register).toHaveBeenCalledWith("/sw.js", { scope: "/" });
  });

  it("does nothing in development or where the browser has no service workers", () => {
    const h = host();
    expect(registerServiceWorker(false, h.nav, h.win)).toBe(false);
    expect(registerServiceWorker(true, {}, h.win)).toBe(false);
    h.load();
    expect(h.register).not.toHaveBeenCalled();
  });
});

describe("manifest", () => {
  it("is installable: name, start URL, standalone, and 192 and 512 icons, one maskable", () => {
    const m = JSON.parse(readFileSync(new URL("../public/manifest.webmanifest", import.meta.url), "utf8"));
    expect(m).toMatchObject({ name: "Education OS", start_url: "/app", display: "standalone" });
    const sizes = m.icons.map((i: { sizes: string; purpose: string }) => `${i.sizes} ${i.purpose}`);
    expect(sizes).toEqual(expect.arrayContaining(["192x192 any", "512x512 any", "512x512 maskable"]));
    for (const icon of m.icons) expect(readFileSync(new URL(`../public${icon.src}`, import.meta.url)).length).toBeGreaterThan(1000);
  });
});
