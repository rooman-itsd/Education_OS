import { cleanup, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import App from "../../src/admin/App";

beforeAll(() => {
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
  window.matchMedia ??= ((query: string) => ({
    matches: false, media: query, onchange: null, addListener() {}, removeListener() {}, addEventListener() {},
    removeEventListener() {}, dispatchEvent: () => false,
  })) as typeof window.matchMedia;
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
  sessionStorage.clear();
  window.location.hash = "";
});

describe("admin sign-in page", () => {
  it("names its two fields with real labels, not only placeholders", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ status: "ok" }), { status: 200, headers: { "Content-Type": "application/json" } })));
    render(<App />);
    const email = await screen.findByLabelText("Institutional Email");
    expect(email.getAttribute("type")).toBe("email");
    expect(screen.getByLabelText("Password").getAttribute("type")).toBe("password");
  });
});

/**
 * jsdom does no layout or cascade, so these read the stylesheets for the two rules a real-browser pass found broken: the
 * keyboard focus ring used `var(--primary-light)`, which nothing defines, so the browser dropped the whole outline and no
 * control of the admin console showed focus; and the primary button was white on the coral #f65b66 (3.2:1).
 */
describe("admin console stylesheets", () => {
  for (const file of ["admin.css", "admin.source.css"]) {
    const css = readFileSync(resolve(process.cwd(), "src/admin", file), "utf8");

    it(`${file}: the focus ring only uses variables that are defined`, () => {
      const start = css.search(/button:focus-visible,\s*a:focus-visible\s*\{/);
      expect(start).toBeGreaterThanOrEqual(0);
      const rule = css.slice(start, css.indexOf("}", start));
      expect(rule).toMatch(/outline:\s*2px solid/);
      for (const [, name, fallback] of rule.matchAll(/var\((--[\w-]+)(,[^)]*)?\)/g)) {
        const defined = new RegExp(`${name}\\s*:`).test(css);
        expect(defined || Boolean(fallback), `${name} is used by the focus ring and is neither defined nor given a fallback`).toBe(true);
      }
    });

    it(`${file}: the primary sign-in button uses the strong coral and the sidebar a white ring`, () => {
      expect(css).toMatch(/\.eos-login-primary\s*\{\s*background-color:\s*#d23443/);
      expect(css).toMatch(/aside button:focus-visible, aside a:focus-visible\s*\{\s*outline-color:\s*#fff/);
    });
  }
});
