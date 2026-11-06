import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { BrowserRouter } from "../../src/admin/lib/router";

/** The signed-in admin the Dashboard sees; each test sets it before rendering. */
const auth = vi.hoisted(() => ({ value: { status: "signed-in", preview: false, session: null as unknown } as Record<string, unknown> }));
vi.mock("../../src/admin/lib/auth", () => ({ useAuth: () => auth.value, isAdmin: () => true }));

import { DashboardPage, activityTime } from "../../src/admin/pages/DashboardPage";

const me = (over: Record<string, unknown>) => ({
  id: "u1", name: "Root", email: "root@platform.example.com", organisation_id: null, roles: [], is_super_admin: false,
  permissions: [], impersonated_by: null, ...over,
});
const orgAdmin = () => ({
  status: "signed-in", preview: false,
  session: { me: me({ roles: ["org-admin"], organisation_id: "org-1" }), organisation: { id: "org-1", name: "Riverside", academy_type: "sports-college" }, entitlement: null },
});
const record = (id: string, over: Record<string, unknown> = {}) => ({
  id, organisation_id: "org-1", actor: "a1", actor_name: "Asha Rao", module: "hostel", action: "allocation.created",
  entity_type: "allocation", entity_id: "x", summary: `Room ${id}`, context: {}, occurred_at: "2026-11-02T09:30:00Z", redacted: false, ...over,
});
const respond = (status: number, body: unknown) =>
  Promise.resolve({ ok: status < 400, status, statusText: "", json: async () => body } as Response);

/** The audit list answers `audit`; the super admin's approval queue answers empty. */
function stub(audit: { status: number; body: unknown }) {
  const f = vi.fn((url: string) =>
    url.includes("/audit/records?") ? respond(audit.status, audit.body)
      : url.includes("/tenancy/admin/organisations?status=") ? respond(200, [])
        : Promise.reject(new Error(`unexpected ${url}`)),
  );
  vi.stubGlobal("fetch", f);
  return f;
}
const panel = () => screen.getByText("Recent Activity").closest("section") as HTMLElement;
const page = () => render(<BrowserRouter><DashboardPage /></BrowserRouter>);

beforeAll(() => {
  // jsdom has neither; the Dashboard's charts use them (as in dashboard-approval.test.tsx).
  globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;
  window.matchMedia ??= ((query: string) => ({
    matches: false, media: query, onchange: null, addListener() {}, removeListener() {}, addEventListener() {},
    removeEventListener() {}, dispatchEvent: () => false,
  })) as typeof window.matchMedia;
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("Dashboard: Recent Activity", () => {
  it("shows the five newest audit records for an organisation admin, with no sample badge", async () => {
    auth.value = orgAdmin();
    const f = stub({ status: 200, body: { items: ["1", "2", "3", "4", "5", "6"].map((i) => record(i)), total: 6 } });
    page();
    expect(await within(panel()).findByText("Room 1")).toBeTruthy();
    expect(within(panel()).getAllByRole("listitem")).toHaveLength(5);
    expect(within(panel()).queryByText("Room 6")).toBeNull();
    expect(within(panel()).getAllByText("Asha Rao · hostel")).toHaveLength(5);
    expect(within(panel()).queryByText("Sample")).toBeNull();
    expect(within(panel()).getByText("The newest changes in your organisation")).toBeTruthy();
    expect(f.mock.calls.map(([u]) => String(u))).toContain("/api/v1/audit/records?limit=50&offset=0");
  });

  it("names the action when a record has no summary, and the system when there is no actor", async () => {
    auth.value = orgAdmin();
    stub({ status: 200, body: { items: [record("1", { summary: null, actor: null, actor_name: undefined, module: "billing", action: "invoice.issued" })], total: 1 } });
    page();
    expect(await within(panel()).findByText("invoice.issued")).toBeTruthy();
    expect(within(panel()).getByText("System · billing")).toBeTruthy();
  });

  it("says so when there is nothing yet", async () => {
    auth.value = orgAdmin();
    stub({ status: 200, body: { items: [], total: 0 } });
    page();
    expect(await within(panel()).findByText("No activity yet.")).toBeTruthy();
  });

  it("says it is not available when the audit API refuses or is missing", async () => {
    auth.value = orgAdmin();
    stub({ status: 503, body: { detail: "down" } });
    page();
    expect(await within(panel()).findByText("Recent activity is not available right now.")).toBeTruthy();
    expect(within(panel()).queryAllByRole("listitem")).toHaveLength(0);
  });

  it("tells a super admin these are the platform's actions", async () => {
    auth.value = { status: "signed-in", preview: false, session: { me: me({ is_super_admin: true }), organisation: null, entitlement: null } };
    stub({ status: 200, body: { items: [record("p", { organisation_id: null, summary: "Approved Riverside" })], total: 1 } });
    page();
    expect(await within(panel()).findByText("Approved Riverside")).toBeTruthy();
    expect(within(panel()).getByText(/Platform actions/)).toBeTruthy();
  });

  it("keeps the labelled sample events in preview mode and calls nothing", () => {
    auth.value = { status: "signed-in", preview: true, session: { me: me({ roles: ["org-admin"] }), organisation: null, entitlement: null } };
    const f = stub({ status: 200, body: { items: [], total: 0 } });
    page();
    expect(within(panel()).getByText("Sample")).toBeTruthy();
    expect(within(panel()).getAllByRole("listitem").length).toBeGreaterThan(0);
    expect(f).not.toHaveBeenCalled();
  });
});

describe("activityTime", () => {
  it("shows the clock time for today and the day otherwise", () => {
    const now = new Date("2026-11-06T15:00:00");
    expect(activityTime("2026-11-06T09:05:00", now)).toBe("09:05");
    expect(activityTime("2026-11-02T09:05:00", now)).toBe("2 Nov");
    expect(activityTime(null, now)).toBe("–");
    expect(activityTime("not a date", now)).toBe("–");
  });
});
