import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Entitlement, Invoice, Plan, Subscription, User } from "../src/api/client";
import { money, longDate } from "../src/api/client";
import { widgets } from "../src/widgets";
import { Invoices } from "../src/widgets/Invoices";
import { PlanAndTrial } from "../src/widgets/PlanAndTrial";
import { share, UsageVsLimits } from "../src/widgets/UsageVsLimits";

const plans: Plan[] = [
  { id: "trial", title: "Trial", description: "", price_per_month: 0, currency: "INR", trial_days: 30, limits: { users: 25, students: 500, storage_gb: 2 }, published: true },
  { id: "standard", title: "Standard", description: "", price_per_month: 24999, currency: "INR", trial_days: null, limits: { users: 500, students: 10000, storage_gb: 100 }, published: true },
  { id: "premium", title: "Premium", description: "", price_per_month: 49999, currency: "INR", trial_days: null, limits: { users: 5000, students: 100000, storage_gb: 1000 }, published: true },
];
const subscription: Subscription = { id: "s1", organisation_id: "o1", plan: "trial", status: "trialing", trial_ends_at: "2026-11-11T08:00:00+00:00", current_period_ends_at: null, pending_plan: null };
const entitlement: Entitlement = { plan: "trial", modules: ["academics/lms", "campus-life/hostel"], upgradable_modules: ["finance-operations/fees-accounts"], limits: { users: 25, students: 500, storage_gb: 2 } };
const users: User[] = [
  { id: "u1", roles: ["org-admin"], status: "active" },
  { id: "u2", roles: ["student"], status: "active" },
  { id: "u3", roles: ["student"], status: "disabled" },
];
const invoice: Invoice = {
  id: "inv1",
  organisation_id: "o1",
  plan: "standard",
  amount: 24999,
  currency: "INR",
  status: "paid",
  issued_at: "2026-10-23T08:00:00+00:00",
  period_start: "2026-10-23T08:00:00+00:00",
  period_end: "2026-11-22T08:00:00+00:00",
  payment_reference: "abc",
  document_id: null,
};

type Route = { status: number; body: unknown } | ((init?: RequestInit) => { status: number; body: unknown });

/** A fetch that answers by path suffix; anything else is a 404. Records every call. */
function routes(map: Record<string, Route>) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    const path = new URL(url, "http://test").pathname;
    const key = Object.keys(map).find((k) => path.endsWith(k));
    const r = key ? map[key]! : { status: 404, body: { detail: "Not Found" } };
    const { status, body } = typeof r === "function" ? r(init) : r;
    return { ok: status < 400, status, statusText: "", json: async () => body };
  });
}

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("registration", () => {
  it("exports the three Organisation Admin widgets with the keys the catalogue grants org-admin", () => {
    const ids = widgets.map((w) => w.id);
    expect(ids).toEqual(["billing.plan-and-trial", "billing.usage-vs-limits", "billing.invoices"]);
    for (const w of widgets) {
      expect(w.permission).toBe("billing:subscription:read");
      expect(w.kind).toBeTruthy();
    }
  });
});

describe("billing.plan-and-trial", () => {
  it("names the plan, its status and when the trial ends, and offers the other plans to the org admin", async () => {
    const fetchMock = routes({ "/billing/subscription": { status: 200, body: subscription }, "/billing/plans": { status: 200, body: plans } });
    vi.stubGlobal("fetch", fetchMock);
    render(<PlanAndTrial role="org-admin" />);
    expect(await screen.findByText("Trial")).toBeTruthy();
    expect(screen.getByText(/Free · Trial ends 11 Nov 2026/)).toBeTruthy();
    const list = screen.getByRole("list", { name: "Available plans" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(2);
    expect(within(list).getByText("₹24,999 per month · up to 500 users")).toBeTruthy();
    const calls = fetchMock.mock.calls.map((c) => c[0] as string);
    expect(calls).toContain("/api/v1/billing/subscription");
    expect(((fetchMock.mock.calls[0]![1] as RequestInit).headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("hides the plan change from roles other than the org admin", async () => {
    vi.stubGlobal("fetch", routes({ "/billing/subscription": { status: 200, body: subscription }, "/billing/plans": { status: 200, body: plans } }));
    render(<PlanAndTrial role="management" />);
    expect(await screen.findByText("Trial")).toBeTruthy();
    expect(screen.queryByRole("list", { name: "Available plans" })).toBeNull();
  });

  it("starts the upgrade from the Switch button and follows the payment url when there is one", async () => {
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign, reload: vi.fn() });
    const fetchMock = routes({
      "/billing/subscription": { status: 200, body: subscription },
      "/billing/plans": { status: 200, body: plans },
      "/billing/subscription/upgrade": (init) => ({ status: 201, body: { activated: false, payment_url: "/api/v1/billing/pay/ref1", reference: "ref1", sent: init?.body } }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PlanAndTrial role="org-admin" />);
    fireEvent.click(await screen.findByRole("button", { name: "Switch to Standard" }));
    await vi.waitFor(() => expect(assign).toHaveBeenCalledWith("/api/v1/billing/pay/ref1"));
    const post = fetchMock.mock.calls.find((c) => (c[0] as string).endsWith("/subscription/upgrade"))!;
    expect((post[1] as RequestInit).method).toBe("POST");
    expect(JSON.parse((post[1] as RequestInit).body as string)).toEqual({ plan: "standard" });
  });

  it("reloads the dashboard when the upgrade is applied at once", async () => {
    const reload = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign: vi.fn(), reload });
    vi.stubGlobal(
      "fetch",
      routes({
        "/billing/subscription": { status: 200, body: subscription },
        "/billing/plans": { status: 200, body: plans },
        "/billing/subscription/upgrade": { status: 201, body: { activated: true, payment_url: null, reference: "ref2" } },
      }),
    );
    render(<PlanAndTrial role="org-admin" />);
    fireEvent.click(await screen.findByRole("button", { name: "Switch to Premium" }));
    await vi.waitFor(() => expect(reload).toHaveBeenCalled());
    expect(screen.getByRole("status").textContent).toContain("Switched to Premium");
  });

  it("says the data is not available while billing is not mounted (404), and offers no retry on 403", async () => {
    vi.stubGlobal("fetch", routes({}));
    render(<PlanAndTrial role="org-admin" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Billing data is not available yet.");
    expect(within(alert).getByRole("button", { name: "Try again" })).toBeTruthy();
    cleanup();
    vi.stubGlobal("fetch", routes({ "/billing/subscription": { status: 403, body: { detail: "forbidden" } }, "/billing/plans": { status: 200, body: plans } }));
    render(<PlanAndTrial role="org-admin" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});

describe("billing.usage-vs-limits", () => {
  it("counts active users against the plan limit and modules on against the profile", async () => {
    vi.stubGlobal("fetch", routes({ "/tenancy/organisation/entitlement": { status: 200, body: entitlement }, "/identity/users": { status: 200, body: users } }));
    render(<UsageVsLimits role="org-admin" />);
    expect(await screen.findByText("2 of 25 users")).toBeTruthy();
    expect(screen.getByText("2 of 3 modules")).toBeTruthy();
    expect(screen.getByText("1 more on a higher plan")).toBeTruthy();
    expect(screen.getByRole("progressbar", { name: "Users used" }).getAttribute("aria-valuenow")).toBe("8");
  });

  it("marks a limit that is reached", async () => {
    const full = users.concat(Array.from({ length: 30 }, (_, i) => ({ id: `x${i}`, roles: ["student"], status: "active" })));
    vi.stubGlobal("fetch", routes({ "/tenancy/organisation/entitlement": { status: 200, body: entitlement }, "/identity/users": { status: 200, body: full } }));
    render(<UsageVsLimits role="org-admin" />);
    expect(await screen.findByText("32 of 25 users")).toBeTruthy();
    expect(screen.getByText("At the plan limit")).toBeTruthy();
    expect(screen.getByRole("progressbar", { name: "Users used" }).getAttribute("aria-valuenow")).toBe("100");
  });

  it("share() clamps and treats a missing limit as none", () => {
    expect(share(5, 25)).toBe(20);
    expect(share(50, 25)).toBe(100);
    expect(share(5, 0)).toBeNull();
    expect(share(5, undefined)).toBeNull();
  });
});

describe("billing.invoices", () => {
  it("lists invoices newest first with plan, amount, period and status", async () => {
    vi.stubGlobal("fetch", routes({ "/billing/invoices": { status: 200, body: [invoice] }, "/billing/plans": { status: 200, body: plans } }));
    render(<Invoices role="org-admin" />);
    expect(await screen.findByText("Standard · ₹24,999")).toBeTruthy();
    expect(screen.getByText("23 Oct 2026 to 22 Nov 2026")).toBeTruthy();
    expect(screen.getByText("Paid")).toBeTruthy();
  });

  it("shows an empty state on a trial", async () => {
    vi.stubGlobal("fetch", routes({ "/billing/invoices": { status: 200, body: [] }, "/billing/plans": { status: 200, body: plans } }));
    render(<Invoices role="org-admin" />);
    expect(await screen.findByText("No invoices yet")).toBeTruthy();
  });

  it("formats money and dates safely", () => {
    expect(money(24999, "INR")).toBe("₹24,999");
    expect(longDate("not-a-date")).toBe("—");
    expect(longDate(null)).toBe("—");
  });
});
