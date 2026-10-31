import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cents, endsIn, money, recurringByCurrency, statusBreakdown, type PlanReport, type SubscriptionReport } from "../src/api/client";
import { widgets } from "../src/widgets";
import { RevenueByPlan } from "../src/widgets/RevenueByPlan";
import { SubscriptionsByPlan } from "../src/widgets/SubscriptionsByPlan";
import { TrialsExpiring } from "../src/widgets/TrialsExpiring";

const counts = (c: Partial<PlanReport["subscriptions"]>): PlanReport["subscriptions"] => ({ trialing: 0, active: 0, past_due: 0, read_only: 0, cancelled: 0, ...c });

const REPORT: SubscriptionReport = {
  generated_at: "2026-10-31T10:00:00+00:00",
  trial_window_days: 14,
  paid_window_days: 30,
  plans: [
    { plan: "trial", title: "Trial", currency: "INR", subscriptions: counts({ trialing: 4, read_only: 1 }), total: 5, monthly_recurring: "0.00", paid_last_30_days: "0.00" },
    { plan: "standard", title: "Standard", currency: "INR", subscriptions: counts({ active: 2, past_due: 1 }), total: 3, monthly_recurring: "49998.00", paid_last_30_days: "24999.00" },
    { plan: "premium", title: "Premium", currency: "INR", subscriptions: counts({ cancelled: 1 }), total: 1, monthly_recurring: "0.00", paid_last_30_days: "49999.00" },
    { plan: "enterprise", title: "Enterprise", currency: "INR", subscriptions: counts({}), total: 0, monthly_recurring: "0.00", paid_last_30_days: "0.00" },
  ],
  trials_expiring: [
    { organisation_id: "o1", organisation_name: "Morning Music", plan: "trial", trial_ends_at: "2026-10-31T12:00:00+00:00", days_left: 0 },
    { organisation_id: "o2", organisation_name: null, plan: "trial", trial_ends_at: "2026-11-03T12:00:00+00:00", days_left: 3 },
    { organisation_id: "o3", organisation_name: "Slow Dance", plan: "trial", trial_ends_at: "2026-11-10T12:00:00+00:00", days_left: 10 },
  ],
};

function answer(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({ ok: status < 400, status, statusText: "", json: async () => body });
}
const rows = () => screen.getAllByRole("listitem").map((li) => li.textContent ?? "");

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("super admin widgets: registration", () => {
  it.each(["billing.trials-expiring", "billing.revenue-by-plan", "billing.subscriptions-by-plan"])(
    "%s is exported on the super admin's revenue key, as super-admin.yaml expects",
    (id) => {
      const w = widgets.find((x) => x.id === id);
      expect(w?.permission).toBe("platform:revenue:read");
      expect(w?.kind).toBe("list");
    },
  );
});

describe("helpers", () => {
  it("parses decimal strings to exact cents and sums recurring revenue per currency", () => {
    expect(cents("49998.00")).toBe(4999800);
    expect(cents("0.10") + cents("0.20")).toBe(30); // 0.1 + 0.2 in floats is 0.30000000000000004
    expect(cents("not money")).toBe(0);
    expect(recurringByCurrency([...REPORT.plans, { ...REPORT.plans[1]!, plan: "usd", currency: "USD", monthly_recurring: "10.50" }])).toEqual([
      { currency: "INR", cents: 4999800 },
      { currency: "USD", cents: 1050 },
    ]);
  });

  it("describes statuses and days left", () => {
    expect(statusBreakdown(counts({ trialing: 4, active: 2, read_only: 1 }))).toBe("4 trialing · 2 active · 1 read-only");
    expect(statusBreakdown(counts({}))).toBe("");
    expect([endsIn(0), endsIn(1), endsIn(5)]).toEqual(["ends today", "ends tomorrow", "ends in 5 days"]);
  });
});

describe("billing.trials-expiring", () => {
  it("lists trials soonest first, names them, and reads the report with the session token", async () => {
    const fetchMock = answer(200, REPORT);
    vi.stubGlobal("fetch", fetchMock);
    render(<TrialsExpiring role="super-admin" />);
    expect(await screen.findByText("Morning Music")).toBeTruthy();
    const r = rows();
    expect(r[0]).toContain("ends today");
    expect(r[0]).toContain("Trial ·");
    expect(r[1]).toContain("Unnamed organisation");
    expect(r[1]).toContain("ends in 3 days");
    expect(r[2]).toContain("Slow Dance");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/billing/admin/reports/subscriptions");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("says when no trial ends in the window", async () => {
    vi.stubGlobal("fetch", answer(200, { ...REPORT, trials_expiring: [] }));
    render(<TrialsExpiring role="super-admin" />);
    expect(await screen.findByText("No trials ending in the next 14 days")).toBeTruthy();
  });
});

describe("billing.revenue-by-plan", () => {
  it("totals monthly recurring revenue and lists only plans that earn", async () => {
    vi.stubGlobal("fetch", answer(200, REPORT));
    render(<RevenueByPlan role="super-admin" />);
    expect(await screen.findByText(`${money(49998, "INR")} a month`)).toBeTruthy();
    const r = rows();
    expect(r).toHaveLength(2); // Standard (active) and Premium (paid in the window); not Trial or Enterprise
    expect(r[0]).toContain("Standard");
    expect(r[0]).toContain(`2 active · ${money(24999, "INR")} paid in 30 days`);
    expect(r[0]).toContain(`${money(49998, "INR")}/mo`);
    expect(r[1]).toContain("Premium");
  });

  it("says when nothing is paid", async () => {
    vi.stubGlobal("fetch", answer(200, { ...REPORT, plans: [REPORT.plans[0], REPORT.plans[3]] }));
    render(<RevenueByPlan role="super-admin" />);
    expect(await screen.findByText("No paid subscriptions yet")).toBeTruthy();
  });
});

describe("billing.subscriptions-by-plan", () => {
  it("lists the plans in use with their totals and status breakdown", async () => {
    vi.stubGlobal("fetch", answer(200, REPORT));
    render(<SubscriptionsByPlan role="super-admin" />);
    expect(await screen.findByText("Trial")).toBeTruthy();
    expect(rows()).toEqual(["Trial4 trialing · 1 read-only5", "Standard2 active · 1 past due3", "Premium1 cancelled1"]);
  });

  it("says when nobody is subscribed", async () => {
    vi.stubGlobal("fetch", answer(200, { ...REPORT, plans: [REPORT.plans[3]] }));
    render(<SubscriptionsByPlan role="super-admin" />);
    expect(await screen.findByText("No subscriptions yet")).toBeTruthy();
  });
});

describe("error states, as the other widgets", () => {
  it.each([
    [403, "You do not have access to this."],
    [503, "Billing data is not available yet."],
  ])("answers %i with %s in every super admin widget", async (status, text) => {
    for (const W of [TrialsExpiring, RevenueByPlan, SubscriptionsByPlan]) {
      vi.stubGlobal("fetch", answer(status, {}));
      render(<W role="super-admin" />);
      expect(await screen.findByText(text)).toBeTruthy();
      cleanup();
    }
  });
});
