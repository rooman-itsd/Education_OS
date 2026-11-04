import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BrowserRouter } from "../../src/admin/lib/router";

/** The signed-in admin the Audit page sees; each test sets it before rendering. */
const auth = vi.hoisted(() => ({
  value: { status: "signed-in", preview: false, session: null as unknown, signOut: () => {} } as Record<string, unknown>,
}));
vi.mock("../../src/admin/lib/auth", () => ({ useAuth: () => auth.value, isAdmin: () => true }));

import { actorLabel, happenedToday } from "../../src/admin/lib/auditAdmin";
import { AuditPage } from "../../src/admin/pages/AuditPage";

const me = (over: Record<string, unknown>) => ({
  id: "u1", name: "Root", email: "root@platform.example.com", organisation_id: null, roles: [], is_super_admin: false,
  permissions: [], impersonated_by: null, ...over,
});
const record = (id: string, over: Record<string, unknown> = {}) => ({
  id, organisation_id: null, actor: "a1b2c3d4-0000", actor_name: "Root", module: "tenancy", action: "organisation.approved",
  entity_type: "organisation", entity_id: "org-1", summary: "Approved Riverside", context: {},
  occurred_at: "2026-11-02T09:30:00+00:00", redacted: false, ...over,
});
const ORGS = [
  { id: "org-2", name: "Zeta Music Academy", slug: "zeta", academy_type: "music-academy", status: "active" },
  { id: "org-1", name: "Alpha Sports College", slug: "alpha", academy_type: "sports-college", status: "active" },
];

const respond = (status: number, body: unknown) =>
  Promise.resolve({ ok: status < 400, status, statusText: "", json: async () => body } as Response);

/** fetch routed by path; `pages` answers the audit list in order (the last repeats). */
function mockApi({ pages = [{ status: 200, body: { items: [record("r1")], total: 1 } }] as { status: number; body: unknown }[] } = {}) {
  let n = 0;
  const f = vi.fn((url: string, _init?: RequestInit) => {
    if (url.includes("/audit/records?")) {
      const p = pages[Math.min(n++, pages.length - 1)]!;
      return respond(p.status, p.body);
    }
    if (url.endsWith("/tenancy/admin/organisations")) return respond(200, ORGS);
    return Promise.reject(new Error(`unexpected ${url}`));
  });
  vi.stubGlobal("fetch", f);
  return f;
}
const auditCalls = (f: ReturnType<typeof mockApi>) => f.mock.calls.map(([u]) => String(u)).filter((u) => u.includes("/audit/records?"));
const rows = () => screen.getAllByRole("row").slice(1).map((r) => r.textContent ?? "");
const renderPage = () =>
  render(
    <BrowserRouter>
      <AuditPage />
    </BrowserRouter>,
  );

beforeEach(() => localStorage.setItem("eos.token", "token-1"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("Audit page: real records", () => {
  it("an organisation admin sees their organisation's records with the session token, and no sample label", async () => {
    auth.value = { ...auth.value, preview: false, session: { me: me({ roles: ["org-admin"], organisation_id: "org-1" }), organisation: { name: "Alpha Sports College" } } };
    const f = mockApi({ pages: [{ status: 200, body: { items: [record("r1", { organisation_id: "org-1", redacted: true })], total: 1 } }] });
    renderPage();
    expect(await screen.findByText("Approved Riverside")).toBeTruthy();
    expect(rows()[0]).toContain("Root");
    expect(rows()[0]).toContain("organisation.approved");
    expect(rows()[0]).toContain("organisation: org-1");
    expect(rows()[0]).toContain("Redacted");
    expect(screen.queryByText("Sample data")).toBeNull();
    expect(screen.getByText(/Your organisation’s trail: Alpha Sports College/)).toBeTruthy();
    expect(screen.queryByLabelText("Whose trail")).toBeNull(); // only a super admin chooses
    expect(auditCalls(f)).toEqual(["/api/v1/audit/records?limit=50&offset=0"]);
    expect(((f.mock.calls[0]![1] as RequestInit).headers as Record<string, string>).Authorization).toBe("Bearer token-1");
  });

  it("a super admin starts on the platform's records and can open one organisation's trail", async () => {
    auth.value = { ...auth.value, preview: false, session: { me: me({ is_super_admin: true }), organisation: null } };
    const f = mockApi({
      pages: [
        { status: 200, body: { items: [record("p1")], total: 1 } },
        { status: 200, body: { items: [record("o1", { module: "hostel", action: "allocation.created", summary: "Room 12" })], total: 1 } },
      ],
    });
    renderPage();
    expect(await screen.findByText("Approved Riverside")).toBeTruthy();
    expect(screen.getByText(/platform’s own records/)).toBeTruthy();
    const choose = screen.getByLabelText("Whose trail") as HTMLSelectElement;
    expect(await screen.findByRole("option", { name: "Alpha Sports College" })).toBeTruthy();
    expect([...choose.options].map((o) => o.textContent)).toEqual(["Platform (super admin actions)", "Alpha Sports College", "Zeta Music Academy"]);
    fireEvent.change(choose, { target: { value: "org-1" } });
    expect(await screen.findByText("Room 12")).toBeTruthy();
    expect(screen.getByText(/Reading it is itself recorded/)).toBeTruthy();
    expect(auditCalls(f)).toEqual(["/api/v1/audit/records?limit=50&offset=0", "/api/v1/audit/records?limit=50&offset=0&organisation_id=org-1"]);
  });

  it("loads the next page on request, and filters the loaded records by search and module", async () => {
    auth.value = { ...auth.value, preview: false, session: { me: me({ roles: ["org-admin"], organisation_id: "org-1" }), organisation: null } };
    const first = Array.from({ length: 50 }, (_, i) => record(`r${i}`, { summary: `Change ${i}` }));
    const f = mockApi({
      pages: [
        { status: 200, body: { items: first, total: 51 } },
        { status: 200, body: { items: [record("r50", { module: "hostel", action: "allocation.created", summary: "Room 12" })], total: 51 } },
      ],
    });
    renderPage();
    expect(await screen.findByText("Change 0")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Load 1 more" }));
    expect(await screen.findByText("Room 12")).toBeTruthy();
    expect(auditCalls(f)[1]).toBe("/api/v1/audit/records?limit=50&offset=50");
    expect(screen.queryByRole("button", { name: /Load .* more/ })).toBeNull(); // all 51 loaded
    fireEvent.change(screen.getByLabelText("Module"), { target: { value: "hostel" } });
    expect(rows()).toHaveLength(1);
    fireEvent.change(screen.getByLabelText("Module"), { target: { value: "All" } });
    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "change 4" } });
    expect(rows()).toEqual(expect.arrayContaining([expect.stringContaining("Change 4")]));
    expect(rows().every((r) => r.includes("Change 4"))).toBe(true);
  });

  it("says when there are no records yet", async () => {
    auth.value = { ...auth.value, preview: false, session: { me: me({ roles: ["org-admin"], organisation_id: "org-1" }), organisation: null } };
    mockApi({ pages: [{ status: 200, body: { items: [], total: 0 } }] });
    renderPage();
    expect(await screen.findByText("No audit records yet.")).toBeTruthy();
  });

  it.each([
    [403, "You do not have access to audit records.", false],
    [503, "Audit records are not available yet.", true],
    [500, "Could not load audit records. Try again in a moment.", true],
  ])("answers %i with its message (retry offered: %s)", async (status, message, retry) => {
    auth.value = { ...auth.value, preview: false, session: { me: me({ roles: ["org-admin"], organisation_id: "org-1" }), organisation: null } };
    mockApi({ pages: [{ status, body: { detail: "x" } }] });
    renderPage();
    expect(await screen.findByText(message)).toBeTruthy();
    expect(Boolean(screen.queryByRole("button", { name: "Try again" }))).toBe(retry);
  });

  it("an expired session signs out instead of showing an error", async () => {
    const signOut = vi.fn();
    auth.value = { ...auth.value, preview: false, signOut, session: { me: me({ roles: ["org-admin"], organisation_id: "org-1" }), organisation: null } };
    mockApi({ pages: [{ status: 401, body: { detail: "expired" } }] });
    renderPage();
    await vi.waitFor(() => expect(signOut).toHaveBeenCalled());
  });
});

describe("Audit page: preview mode", () => {
  it("shows the labelled sample events and calls no API", async () => {
    auth.value = { ...auth.value, preview: true, session: { me: me({ roles: ["org-admin"] }), organisation: null } };
    const f = mockApi();
    renderPage();
    expect(screen.getByText("Sample data")).toBeTruthy();
    expect(rows().length).toBeGreaterThan(0);
    expect(f).not.toHaveBeenCalled();
  });
});

describe("helpers", () => {
  it("names the actor by current name, short id, or the system", () => {
    expect(actorLabel({ actor: "a1b2c3d4-0000", actor_name: "Root" })).toBe("Root");
    expect(actorLabel({ actor: "a1b2c3d4-0000" })).toBe("User a1b2c3d4");
    expect(actorLabel({ actor: null })).toBe("System");
    expect(happenedToday("2026-11-03T10:00:00", new Date("2026-11-03T18:00:00"))).toBe(true);
    expect(happenedToday("2026-11-02T10:00:00", new Date("2026-11-03T18:00:00"))).toBe(false);
    expect(happenedToday(null)).toBe(false);
  });
});
