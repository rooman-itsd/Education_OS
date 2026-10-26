import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { BrowserRouter } from "../../src/admin/lib/router";

/** The signed-in admin the Dashboard sees; each test sets it before rendering. */
const auth = vi.hoisted(() => ({ value: { status: "signed-in", preview: false, session: null as unknown } }));
vi.mock("../../src/admin/lib/auth", () => ({
  useAuth: () => auth.value,
  isAdmin: () => true,
}));

import { DashboardPage } from "../../src/admin/pages/DashboardPage";

const me = (over: Record<string, unknown>) => ({
  id: "u1",
  name: "Root",
  email: "root@platform.example.com",
  organisation_id: null,
  roles: [],
  is_super_admin: false,
  permissions: [],
  impersonated_by: null,
  ...over,
});

function stubPending(orgs: unknown[]) {
  const f = vi.fn((url: string) =>
    url.endsWith("?status=pending_approval") || url.endsWith("?status=pending_verification")
      ? Promise.resolve({ ok: true, status: 200, statusText: "", json: async () => (url.endsWith("?status=pending_approval") ? orgs : []) } as Response)
      : Promise.reject(new Error(`unexpected ${url}`)),
  );
  vi.stubGlobal("fetch", f);
  return f;
}

const tile = () => screen.getByText("Pending Approvals").closest("a, div") as HTMLElement;

beforeAll(() => {
  // jsdom has neither; the Dashboard's charts use them (same stubs as admin.test.tsx).
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
  window.matchMedia ??= ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener() {},
    removeListener() {},
    addEventListener() {},
    removeEventListener() {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Dashboard: Pending Approvals", () => {
  it("super admin: the tile counts organisations awaiting approval and the approval queue is shown", async () => {
    auth.value = { status: "signed-in", preview: false, session: { me: me({ is_super_admin: true }), organisation: null, entitlement: null } };
    const f = stubPending([
      { id: "o1", name: "Riverside Sports College", slug: "riverside", academy_type: "sports-college", requested_academy_type: null, country: null, status: "pending_approval", status_reason: null, created_at: "2026-10-20T09:00:00+00:00", plan: "trial" },
    ]);
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>,
    );
    expect(await screen.findByText("Riverside Sports College")).toBeTruthy();
    expect(screen.getByRole("region", { name: "Organisations awaiting approval" })).toBeTruthy();
    expect(screen.getByText("Organisations awaiting approval", { selector: "span:not([id])" })).toBeTruthy();
    expect(screen.queryByText("12 urgent")).toBeNull();
    expect(f).toHaveBeenCalled();
  });

  it("organisation admin: keeps the original tile and shows no organisation queue", () => {
    auth.value = { status: "signed-in", preview: false, session: { me: me({ roles: ["org-admin"], organisation_id: "org-1" }), organisation: { id: "org-1", name: "Riverside", academy_type: "sports-college" }, entitlement: null } };
    const f = stubPending([]);
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>,
    );
    expect(screen.getByText("12 urgent")).toBeTruthy();
    expect(tile()).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Organisations awaiting approval" })).toBeNull();
    expect(f).not.toHaveBeenCalled();
  });

  it("preview (no API): keeps the sample tile even for a super admin, and calls nothing", () => {
    auth.value = { status: "signed-in", preview: true, session: { me: me({ is_super_admin: true }), organisation: null, entitlement: null } };
    const f = stubPending([]);
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>,
    );
    expect(screen.getByText("12 urgent")).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Organisations awaiting approval" })).toBeNull();
    expect(f).not.toHaveBeenCalled();
  });
});
