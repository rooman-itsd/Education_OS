import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { WidgetProps } from "@eos/ui-kit";
import type { CollectionsReport, CollectionVsTargetReport, MyDues, OutstandingReport } from "../src/api/client";
import { widgets } from "../src/widgets";
import { CollectionsToday } from "../src/widgets/CollectionsToday";
import { CollectionVsTarget } from "../src/widgets/CollectionVsTarget";
import { FeeDue, FeeDues } from "../src/widgets/Dues";
import { OutstandingDues } from "../src/widgets/OutstandingDues";

function answer(status: number, body: unknown) {
  return { ok: status < 400, status, statusText: "", json: async () => body };
}

/** Stubs fetch with one response per call, in order. */
function stubFetch(...responses: ReturnType<typeof answer>[]) {
  const fetchMock = vi.fn();
  for (const r of responses) fetchMock.mockResolvedValueOnce(r);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function lastCall(fetchMock: ReturnType<typeof vi.fn>) {
  const [url, init] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1] as [string, RequestInit];
  return { url, headers: init.headers as Record<string, string> };
}

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("widget declarations", () => {
  const expected: [string, string, string, string, ComponentType<WidgetProps>][] = [
    ["fees-accounts.fee-due", "fees-accounts:self:read", "1x1", "list", FeeDue],
    ["fees-accounts.fee-dues", "fees-accounts:self:read", "2x1", "list", FeeDues],
    ["fees-accounts.collections-today", "fees-accounts:report:read", "1x1", "panel", CollectionsToday],
    ["fees-accounts.outstanding-dues", "fees-accounts:report:read", "2x1", "panel", OutstandingDues],
    ["fees-accounts.collection-vs-target", "fees-accounts:report:read", "2x1", "panel", CollectionVsTarget],
  ];

  it("exports the five widgets the role layouts name, in order", () => {
    expect(widgets.map((w) => w.id)).toEqual(expected.map((e) => e[0]));
  });

  it.each(expected)("registers %s with permission %s, size %s, kind %s and its component", (id, permission, size, kind, component) => {
    const w = widgets.find((x) => x.id === id);
    expect(w).toBeTruthy();
    expect(w?.permission).toBe(permission);
    expect(w?.size).toBe(size);
    expect(w?.kind).toBe(kind);
    expect(w?.component).toBe(component);
    expect(w?.title).toBeTruthy();
  });
});

const dues = (over: Partial<MyDues> = {}): MyDues => ({
  total_due: "62500.00",
  overdue: "12500.00",
  next_due_date: "2026-11-05",
  invoices: [
    { id: "i1", number: "INV-2026-0041", title: "B.Sc. Sports Science · Instalment 1", balance: "12500.00", due_date: "2026-10-01", overdue: true, can_pay_online: true },
    { id: "i2", number: "INV-2026-0042", title: "B.Sc. Sports Science · Instalment 2", balance: "25000.00", due_date: "2026-11-05", overdue: false, can_pay_online: true },
    { id: "i3", number: "INV-2026-0043", title: "Hostel fee", balance: "15000.00", due_date: "2026-12-01", overdue: false, can_pay_online: false },
    { id: "i4", number: "INV-2026-0044", title: "Transport fee", balance: "10000.00", due_date: "2027-01-05", overdue: false, can_pay_online: true },
  ],
  ...over,
});

const noDues: MyDues = { total_due: "0.00", overdue: "0.00", next_due_date: null, invoices: [] };

describe.each([
  ["fees-accounts.fee-due", FeeDue, 3],
  ["fees-accounts.fee-dues", FeeDues, 4],
] as const)("%s", (_id, Widget, rows) => {
  it("shows loading, then the dues from GET /me/dues with the session token", async () => {
    const fetchMock = stubFetch(answer(200, dues()));
    render(<Widget role="student" />);
    expect(screen.getByLabelText("Loading").getAttribute("aria-busy")).toBe("true");
    expect(await screen.findByText("₹62,500.00")).toBeTruthy();
    // Overdue amount highlighted in a danger badge, next due date in words.
    expect(screen.getByText("₹12,500.00 overdue").className).toContain("eos-badge--danger");
    expect(screen.getAllByText("5 Nov 2026").length).toBeGreaterThan(0);
    const list = screen.getByRole("list", { name: "Fees due" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(rows);
    expect(within(items[0]!).getByText("B.Sc. Sports Science · Instalment 1")).toBeTruthy();
    expect(within(items[0]!).getByText("INV-2026-0041 · Due 1 Oct 2026")).toBeTruthy();
    expect(within(items[0]!).getByText("₹12,500.00")).toBeTruthy();
    expect(within(items[0]!).getByText("Overdue").className).toContain("eos-badge--danger");
    expect(within(items[1]!).queryByText("Overdue")).toBeNull();
    const { url, headers } = lastCall(fetchMock);
    expect(url).toBe("/api/v1/fees-accounts/me/dues");
    expect(headers.Authorization).toBe("Bearer test-token");
  });

  it("shows an empty state when nothing is due", async () => {
    stubFetch(answer(200, noDues));
    render(<Widget role="student" />);
    expect(await screen.findByText("No fees due")).toBeTruthy();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("says nothing is overdue when the overdue amount is zero", async () => {
    stubFetch(answer(200, dues({ overdue: "0.00", invoices: dues().invoices.map((i) => ({ ...i, overdue: false })) })));
    render(<Widget role="student" />);
    expect(await screen.findByText("Nothing overdue")).toBeTruthy();
    expect(document.querySelector(".eos-badge--danger")).toBeNull();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = stubFetch(answer(503, {}), answer(200, dues()));
    render(<Widget role="student" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Fee data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("₹62,500.00")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("offers no retry when the viewer lacks the permission", async () => {
    stubFetch(answer(403, { code: "forbidden", message: "Forbidden" }));
    render(<Widget role="student" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});

describe("fees-accounts.fee-due (compact)", () => {
  it("lists the first three dues and says how many more there are", async () => {
    stubFetch(answer(200, dues()));
    render(<FeeDue role="applicant" />);
    expect(await screen.findByText("and 1 more")).toBeTruthy();
    expect(screen.queryByText("Transport fee")).toBeNull();
  });
});

const collections = (over: Partial<CollectionsReport> = {}): CollectionsReport => ({
  date: "2026-10-22",
  total: "150000.00",
  count: 12,
  previous_day_total: "120000.00",
  by_mode: [
    { mode: "online", amount: "90000.00", count: 8 },
    { mode: "cash", amount: "40000.00", count: 3 },
    { mode: "demand_draft", amount: "20000.00", count: 1 },
  ],
  by_fee_head: [{ fee_head_id: "h1", name: "Tuition", amount: "150000.00" }],
  ...over,
});

describe("fees-accounts.collections-today", () => {
  it("shows today's total, count, change and split by mode from GET /reports/collections", async () => {
    const fetchMock = stubFetch(answer(200, collections()));
    render(<CollectionsToday role="finance-staff" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("₹1,50,000.00")).toBeTruthy();
    expect(screen.getByText("12")).toBeTruthy();
    expect(screen.getByText("₹1,20,000.00")).toBeTruthy();
    expect(screen.getByText("Up 25% on the previous day").className).toContain("eos-badge--success");
    const rows = within(screen.getByRole("list", { name: "Collections by payment mode" })).getAllByRole("listitem");
    expect(rows.map((r) => r.textContent)).toEqual([
      "Online8 payments₹90,000.00",
      "Cash3 payments₹40,000.00",
      "Demand draft1 payment₹20,000.00",
    ]);
    const { url, headers } = lastCall(fetchMock);
    expect(url).toBe("/api/v1/fees-accounts/reports/collections");
    expect(headers.Authorization).toBe("Bearer test-token");
  });

  it("marks a fall on the previous day as a warning", async () => {
    stubFetch(answer(200, collections({ total: "60000.00", previous_day_total: "120000.00" })));
    render(<CollectionsToday role="finance-staff" />);
    expect((await screen.findByText("Down 50% on the previous day")).className).toContain("eos-badge--warning");
  });

  it("shows an empty state when nothing has been collected today", async () => {
    stubFetch(answer(200, collections({ total: "0.00", count: 0, by_mode: [], by_fee_head: [] })));
    render(<CollectionsToday role="finance-staff" />);
    expect(await screen.findByText("No collections yet today")).toBeTruthy();
    expect(screen.getByText("Previous day: ₹1,20,000.00")).toBeTruthy();
  });

  it("shows an error, not a crash, when the service cannot be reached, and retries", async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValueOnce(answer(200, collections()));
    vi.stubGlobal("fetch", fetchMock);
    render(<CollectionsToday role="finance-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Fee data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("₹1,50,000.00")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

const outstanding = (over: Partial<OutstandingReport> = {}): OutstandingReport => ({
  as_of: "2026-10-22",
  outstanding: "1000000.00",
  overdue: "400000.00",
  people_with_dues: 85,
  ageing: [
    { bucket: "not_due", amount: "600000.00", count: 50 },
    { bucket: "0-30", amount: "250000.00", count: 25 },
    { bucket: "31-60", amount: "100000.00", count: 8 },
    { bucket: "61-90", amount: "50000.00", count: 1 },
    { bucket: "90+", amount: "0.00", count: 0 },
  ],
  top_fee_heads: [
    { fee_head_id: "h1", name: "Tuition", amount: "700000.00" },
    { fee_head_id: "h2", name: "Hostel", amount: "300000.00" },
  ],
  ...over,
});

describe("fees-accounts.outstanding-dues", () => {
  it("shows totals, ageing buckets and top fee heads from GET /reports/outstanding", async () => {
    const fetchMock = stubFetch(answer(200, outstanding()));
    render(<OutstandingDues role="finance-staff" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("₹10,00,000.00")).toBeTruthy();
    expect(screen.getByText("₹4,00,000.00").closest("[data-warn]")).toBeTruthy();
    expect(screen.getByText("85")).toBeTruthy();
    const ageing = screen.getByRole("region", { name: "Ageing" });
    const bars = within(ageing).getAllByRole("progressbar");
    expect(bars.map((b) => [b.getAttribute("aria-label"), b.getAttribute("aria-valuenow")])).toEqual([
      ["Not yet due", "60"],
      ["0–30 days overdue", "25"],
      ["31–60 days overdue", "10"],
      ["61–90 days overdue", "5"],
      ["Over 90 days overdue", "0"],
    ]);
    expect(within(ageing).getByText("1 invoice")).toBeTruthy();
    const heads = within(screen.getByRole("region", { name: "Top fee heads" })).getAllByRole("listitem");
    expect(heads.map((h) => h.textContent)).toEqual(["Tuition₹7,00,000.00", "Hostel₹3,00,000.00"]);
    expect(screen.getByText("As of 22 Oct 2026")).toBeTruthy();
    const { url, headers } = lastCall(fetchMock);
    expect(url).toBe("/api/v1/fees-accounts/reports/outstanding");
    expect(headers.Authorization).toBe("Bearer test-token");
  });

  it("shows an empty state when nobody owes anything", async () => {
    stubFetch(answer(200, outstanding({ outstanding: "0.00", overdue: "0.00", people_with_dues: 0, ageing: [], top_fee_heads: [] })));
    render(<OutstandingDues role="finance-staff" />);
    expect(await screen.findByText("No outstanding dues")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = stubFetch(answer(500, { code: "internal", message: "Database unavailable" }), answer(200, outstanding()));
    render(<OutstandingDues role="finance-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Database unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("₹10,00,000.00")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

const target = (over: Partial<CollectionVsTargetReport> = {}): CollectionVsTargetReport => ({
  academic_year: "2026-27",
  target_total: "2000000.00",
  collected_total: "1500000.00",
  periods: [
    { period: "2026-06", target: "1000000.00", collected: "1100000.00" },
    { period: "2026-07", target: "1000000.00", collected: "400000.00" },
  ],
  ...over,
});

describe("fees-accounts.collection-vs-target", () => {
  it("shows collected against target in total and per month from GET /reports/collection-vs-target", async () => {
    const fetchMock = stubFetch(answer(200, target()));
    render(<CollectionVsTarget role="management" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("₹15,00,000.00")).toBeTruthy();
    expect(screen.getByText("₹20,00,000.00")).toBeTruthy();
    expect(screen.getByText("75%")).toBeTruthy();
    expect(screen.getByRole("progressbar", { name: "Collected against target, 2026-27" }).getAttribute("aria-valuenow")).toBe("75");
    const months = within(screen.getByRole("list", { name: "Collected against target by month" })).getAllByRole("listitem");
    expect(months.map((m) => m.textContent)).toEqual([
      "Jun 2026₹11,00,000.00 of ₹10,00,000.00 · 110%",
      "Jul 2026₹4,00,000.00 of ₹10,00,000.00 · 40%",
    ]);
    // A month over target fills its bar, never past it.
    expect(within(months[0]!).getByRole("progressbar").getAttribute("aria-valuenow")).toBe("100");
    expect(within(months[1]!).getByRole("progressbar").getAttribute("aria-valuenow")).toBe("40");
    const { url, headers } = lastCall(fetchMock);
    expect(url).toBe("/api/v1/fees-accounts/reports/collection-vs-target");
    expect(headers.Authorization).toBe("Bearer test-token");
  });

  it("shows an empty state when no targets are set", async () => {
    stubFetch(answer(200, target({ target_total: "0.00", collected_total: "0.00", periods: [] })));
    render(<CollectionVsTarget role="management" />);
    expect(await screen.findByText("No collection targets set")).toBeTruthy();
    expect(screen.getByText("Set targets for 2026-27 to compare collections against them.")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = stubFetch(answer(502, { detail: "Bad Gateway" }), answer(200, target()));
    render(<CollectionVsTarget role="management" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Fee data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("₹15,00,000.00")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("asks the user to sign in again, without a retry, on 401", async () => {
    stubFetch(answer(401, { detail: "Not authenticated" }));
    render(<CollectionVsTarget role="management" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});
