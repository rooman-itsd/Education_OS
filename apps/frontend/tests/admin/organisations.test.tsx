import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BrowserRouter } from "../../src/admin/lib/router";

/** The signed-in user the pages and the sidebar see; each test sets it before rendering. */
const auth = vi.hoisted(() => ({
  value: { status: "signed-in", preview: false, session: null as unknown, signOut: () => {} } as Record<string, unknown>,
}));
vi.mock("../../src/admin/lib/auth", () => ({ useAuth: () => auth.value, isAdmin: () => true }));

import { OrganisationsPage } from "../../src/admin/pages/OrganisationsPage";
import { SubscriptionsPage } from "../../src/admin/pages/SubscriptionsPage";
import { Sidebar } from "../../src/admin/components/layout/Sidebar";

const me = (over: Record<string, unknown>) => ({
  id: "u1", name: "Root", email: "root@platform.example.com", organisation_id: null, roles: [], is_super_admin: false,
  permissions: [], impersonated_by: null, ...over,
});
const superAdmin = () => ({ ...auth.value, preview: false, session: { me: me({ is_super_admin: true }), organisation: null } });
const orgAdmin = () => ({ ...auth.value, preview: false, session: { me: me({ roles: ["org-admin"], organisation_id: "o1" }), organisation: null } });

const org = (id: string, over: Record<string, unknown> = {}) => ({
  id, name: `Org ${id}`, slug: `org-${id}`, academy_type: "engineering-college", requested_academy_type: null, country: "IN",
  status: "active", status_reason: null, created_at: "2026-11-01T09:00:00Z", plan: "standard", trial_ends_at: null, ...over,
});
const ORGS = [
  org("a", { name: "Alpha College", slug: "alpha" }),
  org("b", { name: "Beta Academy", slug: "beta", status: "suspended", status_reason: "Unpaid" }),
  org("c", { name: "Gamma Institute", slug: "gamma", plan: "trial", trial_ends_at: "2099-01-10T23:59:59Z" }),
  org("d", { name: "Delta Pending", slug: "delta", status: "pending_approval", plan: null }),
];
const PLANS = [
  { id: "trial", title: "Trial", price_per_month: 0, currency: "INR", trial_days: 14, published: true },
  { id: "standard", title: "Standard", price_per_month: 25000, currency: "INR", trial_days: null, published: true },
  { id: "premium", title: "Premium", price_per_month: 60000, currency: "INR", trial_days: null, published: true },
];

const respond = (status: number, body: unknown) =>
  Promise.resolve({ ok: status < 400, status, statusText: "", json: async () => body } as Response);

/** fetch routed by path: the organisation list, one organisation, the plans, and the two PUTs. */
function mockApi({ list = { status: 200, body: ORGS as unknown } } = {}) {
  const f = vi.fn((url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (url.endsWith("/tenancy/admin/organisations") && method === "GET") return respond(list.status, list.body);
    if (/\/tenancy\/admin\/organisations\/[^/]+$/.test(url)) {
      return respond(200, { ...ORGS[0], entitlement: { modules: ["a", "b", "c"], subscription_status: "active" } });
    }
    if (url.endsWith("/status") && method === "PUT") return respond(200, { ...ORGS[0], status: "suspended" });
    if (url.endsWith("/billing/plans")) return respond(200, PLANS);
    if (url.includes("/billing/admin/subscriptions/") && method === "PUT") return respond(200, { plan: "premium" });
    return Promise.reject(new Error(`unexpected ${method} ${url}`));
  });
  vi.stubGlobal("fetch", f);
  return f;
}
const calls = (f: ReturnType<typeof mockApi>, method: string) =>
  f.mock.calls.filter(([, init]) => (init?.method ?? "GET") === method).map(([u, init]) => ({ url: String(u), body: init?.body }));
const rows = () => screen.getAllByRole("row").slice(1);
const page = (el: React.ReactElement) => render(<BrowserRouter>{el}</BrowserRouter>);

beforeEach(() => localStorage.setItem("eos.token", "token-1"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("Organisations", () => {
  it("lists every organisation and filters by search, status and plan", async () => {
    auth.value = superAdmin();
    mockApi();
    page(<OrganisationsPage />);
    expect(await screen.findByText("Alpha College")).toBeTruthy();
    expect(rows()).toHaveLength(4);
    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "gam" } });
    expect(rows().map((r) => r.textContent)).toEqual([expect.stringContaining("Gamma Institute")]);
    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "suspended" } });
    expect(rows().map((r) => r.textContent)).toEqual([expect.stringContaining("Beta Academy")]);
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "all" } });
    fireEvent.change(screen.getByLabelText("Plan"), { target: { value: "trial" } });
    expect(rows()).toHaveLength(1);
  });

  it("suspends an active organisation only with a reason, then reloads", async () => {
    auth.value = superAdmin();
    const f = mockApi();
    page(<OrganisationsPage />);
    const alpha = (await screen.findByText("Alpha College")).closest("tr")!;
    fireEvent.click(within(alpha).getByRole("button", { name: "Suspend" }));
    const dialog = screen.getByRole("dialog", { name: "Suspend Alpha College?" });
    const confirm = within(dialog).getByRole("button", { name: "Suspend" }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true); // no reason yet
    fireEvent.change(within(dialog).getByLabelText(/Reason/), { target: { value: "  Invoice unpaid for 60 days  " } });
    expect(confirm.disabled).toBe(false);
    fireEvent.click(confirm);
    expect(await screen.findByText("Alpha College is now suspended.")).toBeTruthy();
    const put = calls(f, "PUT");
    expect(put).toHaveLength(1);
    expect(put[0]!.url).toBe("/api/v1/tenancy/admin/organisations/a/status");
    expect(JSON.parse(String(put[0]!.body))).toEqual({ status: "suspended", reason: "Invoice unpaid for 60 days" });
    expect(calls(f, "GET").filter((c) => c.url.endsWith("/tenancy/admin/organisations"))).toHaveLength(2); // reloaded
  });

  it("offers Reactivate for a suspended organisation and nothing for one awaiting approval", async () => {
    auth.value = superAdmin();
    const f = mockApi();
    page(<OrganisationsPage />);
    const beta = (await screen.findByText("Beta Academy")).closest("tr")!;
    const delta = screen.getByText("Delta Pending").closest("tr")!;
    expect(within(delta).queryByRole("button", { name: /Suspend|Reactivate/ })).toBeNull();
    fireEvent.click(within(beta).getByRole("button", { name: "Reactivate" }));
    const dialog = screen.getByRole("dialog", { name: "Reactivate Beta Academy?" });
    fireEvent.change(within(dialog).getByLabelText(/Reason/), { target: { value: "Paid" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Reactivate" }));
    await screen.findByText("Beta Academy is now active.");
    expect(JSON.parse(String(calls(f, "PUT")[0]!.body))).toEqual({ status: "active", reason: "Paid" });
  });

  it("shows an organisation's details from the API", async () => {
    auth.value = superAdmin();
    mockApi();
    page(<OrganisationsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Alpha College" }));
    expect(await screen.findByLabelText("Details of Alpha College")).toBeTruthy();
    expect(screen.getByLabelText("Details of Alpha College").textContent).toContain("3"); // modules entitled
  });

  it.each([
    [403, "You do not have access to organisations.", false],
    [503, "Organisations are not available yet.", true],
  ])("answers %i with its message (retry offered: %s)", async (status, message, retry) => {
    auth.value = superAdmin();
    mockApi({ list: { status, body: { detail: "x" } } });
    page(<OrganisationsPage />);
    expect(await screen.findByText(message)).toBeTruthy();
    expect(Boolean(screen.queryByRole("button", { name: "Try again" }))).toBe(retry);
  });

  it("an expired session signs out", async () => {
    const signOut = vi.fn();
    auth.value = { ...superAdmin(), signOut };
    mockApi({ list: { status: 401, body: { detail: "expired" } } });
    page(<OrganisationsPage />);
    await vi.waitFor(() => expect(signOut).toHaveBeenCalled());
  });

  it("tells an organisation admin it is for super admins and calls nothing", () => {
    auth.value = orgAdmin();
    const f = mockApi();
    page(<OrganisationsPage />);
    expect(screen.getByText("Only a super admin manages organisations.")).toBeTruthy();
    expect(f).not.toHaveBeenCalled();
  });

  it("shows labelled samples in preview mode and calls nothing", () => {
    auth.value = { ...auth.value, preview: true, session: { me: me({}), organisation: null } };
    const f = mockApi();
    page(<OrganisationsPage />);
    expect(screen.getByText("Sample data")).toBeTruthy();
    expect(rows().length).toBeGreaterThan(0);
    expect((screen.getAllByRole("button", { name: "Suspend" })[0] as HTMLButtonElement).disabled).toBe(true);
    expect(f).not.toHaveBeenCalled();
  });
});

describe("Subscriptions", () => {
  it("lists organisations that have a plan, with plan titles, and filters by plan", async () => {
    auth.value = superAdmin();
    mockApi();
    page(<SubscriptionsPage />);
    expect(await screen.findByText("Alpha College")).toBeTruthy();
    expect(rows()).toHaveLength(3); // Delta Pending has no plan yet
    expect(rows()[0]!.textContent).toContain("Standard");
    fireEvent.change(screen.getByLabelText("Plan"), { target: { value: "trial" } });
    expect(rows().map((r) => r.textContent)).toEqual([expect.stringContaining("Gamma Institute")]);
  });

  it("changes a plan with a reason", async () => {
    auth.value = superAdmin();
    const f = mockApi();
    page(<SubscriptionsPage />);
    const alpha = (await screen.findByText("Alpha College")).closest("tr")!;
    expect(within(alpha).queryByRole("button", { name: "Extend trial" })).toBeNull(); // not on a trial
    fireEvent.click(within(alpha).getByRole("button", { name: "Change plan" }));
    const dialog = screen.getByRole("dialog", { name: "Change Alpha College's plan" });
    fireEvent.change(within(dialog).getByLabelText("New plan"), { target: { value: "premium" } });
    fireEvent.change(within(dialog).getByLabelText(/Reason/), { target: { value: "Signed the annual contract" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Change plan" }));
    expect(await screen.findByText("Alpha College is now on Premium.")).toBeTruthy();
    const put = calls(f, "PUT");
    expect(put[0]!.url).toBe("/api/v1/billing/admin/subscriptions/a");
    expect(JSON.parse(String(put[0]!.body))).toEqual({ plan: "premium", reason: "Signed the annual contract" });
  });

  it("extends a trial to the end of the chosen day", async () => {
    auth.value = superAdmin();
    const f = mockApi();
    page(<SubscriptionsPage />);
    const gamma = (await screen.findByText("Gamma Institute")).closest("tr")!;
    fireEvent.click(within(gamma).getByRole("button", { name: "Extend trial" }));
    const dialog = screen.getByRole("dialog", { name: "Extend Gamma Institute's trial" });
    fireEvent.change(within(dialog).getByLabelText("New last day of the trial"), { target: { value: "2099-02-01" } });
    fireEvent.change(within(dialog).getByLabelText(/Reason/), { target: { value: "Waiting for the purchase order" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Extend trial" }));
    await screen.findByText(/trial now ends on 1 Feb 2099/);
    expect(JSON.parse(String(calls(f, "PUT")[0]!.body))).toEqual({
      trial_ends_at: "2099-02-01T23:59:59+00:00",
      reason: "Waiting for the purchase order",
    });
  });

  it("shows the API's reason when a change is refused, and keeps the dialog open", async () => {
    auth.value = superAdmin();
    const f = vi.fn((url: string, init?: RequestInit) => {
      if (url.endsWith("/tenancy/admin/organisations")) return respond(200, ORGS);
      if (url.endsWith("/billing/plans")) return respond(200, PLANS);
      if ((init?.method ?? "GET") === "PUT") return respond(404, { detail: "no subscription" });
      return Promise.reject(new Error(url));
    });
    vi.stubGlobal("fetch", f);
    page(<SubscriptionsPage />);
    const alpha = (await screen.findByText("Alpha College")).closest("tr")!;
    fireEvent.click(within(alpha).getByRole("button", { name: "Change plan" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(/Reason/), { target: { value: "x" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Change plan" }));
    expect(await within(dialog).findByText("no subscription")).toBeTruthy();
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("tells an organisation admin it is for super admins and calls nothing", () => {
    auth.value = orgAdmin();
    const f = mockApi();
    page(<SubscriptionsPage />);
    expect(screen.getByText("Only a super admin manages subscriptions.")).toBeTruthy();
    expect(f).not.toHaveBeenCalled();
  });
});

describe("Sidebar", () => {
  const sidebar = () =>
    render(
      <BrowserRouter>
        <Sidebar collapsed={false} onToggleCollapse={() => {}} mobileOpen={false} onCloseMobile={() => {}} />
      </BrowserRouter>,
    );

  it("shows Organisations and Subscriptions to a super admin", () => {
    auth.value = superAdmin();
    sidebar();
    expect(screen.getByRole("link", { name: /Organisations/ })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Subscriptions/ })).toBeTruthy();
  });

  it("hides them from an organisation admin", () => {
    auth.value = orgAdmin();
    sidebar();
    expect(screen.queryByRole("link", { name: /^Organisations$/ })).toBeNull();
    expect(screen.queryByRole("link", { name: /Subscriptions/ })).toBeNull();
    expect(screen.getByRole("link", { name: /Audit Log/ })).toBeTruthy();
  });
});
