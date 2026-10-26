import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { WidgetProps } from "@eos/ui-kit";
import type { BudgetVsSpendReport, MyGrant } from "../src/api/client";
import { widgets } from "../src/widgets";
import { BudgetVsSpend } from "../src/widgets/BudgetVsSpend";
import { MyGrants } from "../src/widgets/MyGrants";

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
  vi.useRealTimers();
  localStorage.clear();
});

describe("widget declarations", () => {
  const expected: [string, string, string, string, ComponentType<WidgetProps>][] = [
    ["budget-grants.budget-vs-spend", "budget-grants:report:read", "2x1", "panel", BudgetVsSpend],
    ["budget-grants.my-grants", "budget-grants:self:read", "2x1", "list", MyGrants],
  ];

  it("exports the two widgets the role layouts name, in order", () => {
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

const report = (over: Partial<BudgetVsSpendReport> = {}): BudgetVsSpendReport => ({
  financial_year: "2026-27",
  allocated: "1050000.00",
  committed: "200000.00",
  spent: "660000.00",
  by_head: [
    { budget_head_id: "h1", name: "Salaries", allocated: "600000.00", committed: "0.00", spent: "300000.00" },
    { budget_head_id: "h2", name: "Equipment", allocated: "200000.00", committed: "100000.00", spent: "120000.00" },
    { budget_head_id: "h3", name: "Consumables", allocated: "100000.00", committed: "50000.00", spent: "30000.00" },
    { budget_head_id: "h4", name: "Travel", allocated: "100000.00", committed: "50000.00", spent: "200000.00" },
    { budget_head_id: "h5", name: "Maintenance", allocated: "50000.00", committed: "0.00", spent: "10000.00" },
    { budget_head_id: "h6", name: "Contingency", allocated: "0.00", committed: "0.00", spent: "0.00" },
  ],
  grants: { active: 3, sanctioned: "4500000.00", spent: "1200000.00", ucs_due_30_days: 2 },
  ...over,
});

const nothing = (over: Partial<BudgetVsSpendReport> = {}): BudgetVsSpendReport =>
  report({ allocated: "0.00", committed: "0.00", spent: "0.00", by_head: [], grants: { active: 0, sanctioned: "0.00", spent: "0.00", ucs_due_30_days: 0 }, ...over });

describe("budget-grants.budget-vs-spend", () => {
  it("renders a report without by_head instead of unmounting the dashboard", async () => {
    const { by_head: _omitted, ...withoutHeads } = report();
    stubFetch(answer(200, withoutHeads));
    render(<BudgetVsSpend role="finance-staff" />);
    expect(await screen.findByText("₹10,50,000")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows totals, percent used, the heads closest to their limit and grant totals from GET /reports/budget-vs-spend", async () => {
    const fetchMock = stubFetch(answer(200, report()));
    render(<BudgetVsSpend role="finance-staff" />);
    expect(screen.getByLabelText("Loading").getAttribute("aria-busy")).toBe("true");
    expect(await screen.findByText("₹10,50,000.00")).toBeTruthy();
    expect(screen.getByText("₹2,00,000.00")).toBeTruthy();
    expect(screen.getByText("₹6,60,000.00")).toBeTruthy();
    // Available is allocated less committed and spent, worked out in paise.
    expect(screen.getByText("₹1,90,000.00").closest("[data-warn]")).toBeNull();
    // 8,60,000 of 10,50,000 is 81.9%: past the 80% threshold.
    const overall = screen.getByRole("progressbar", { name: "Committed and spent against allocated, 2026-27" });
    expect(overall.getAttribute("aria-valuenow")).toBe("81");
    expect(screen.getByText("81% used")).toBeTruthy();
    const heads = within(screen.getByRole("region", { name: "Budget heads" })).getAllByRole("listitem");
    expect(heads.map((h) => h.textContent)).toEqual([
      "Travel₹2,50,000.00 of ₹1,00,000.00250% usedOver budget",
      "Equipment₹2,20,000.00 of ₹2,00,000.00110% usedOver budget",
      "Consumables₹80,000.00 of ₹1,00,000.0080% usedNearing limit",
      "Salaries₹3,00,000.00 of ₹6,00,000.0050% used",
      "Maintenance₹10,000.00 of ₹50,000.0020% used",
    ]);
    expect(within(heads[0]!).getByText("Over budget").className).toContain("eos-badge--danger");
    expect(within(heads[2]!).getByText("Nearing limit").className).toContain("eos-badge--warning");
    // A head over its allocation fills its bar, never past it.
    expect(within(heads[0]!).getByRole("progressbar").getAttribute("aria-valuenow")).toBe("100");
    expect(screen.getByText("and 1 more head")).toBeTruthy();
    const grants = screen.getByRole("region", { name: "Grants" });
    expect(within(grants).getByText("3")).toBeTruthy();
    expect(within(grants).getByText("₹45,00,000.00")).toBeTruthy();
    expect(within(grants).getByText("₹12,00,000.00")).toBeTruthy();
    expect(within(grants).getByText("2 due").className).toContain("eos-badge--warning");
    expect(screen.getByText("Financial year 2026-27")).toBeTruthy();
    const { url, headers } = lastCall(fetchMock);
    expect(url).toBe("/api/v1/budget-grants/reports/budget-vs-spend");
    expect(headers.Authorization).toBe("Bearer test-token");
  });

  it("asks for grant scope on the Research Office dashboard", async () => {
    const fetchMock = stubFetch(answer(200, report()));
    render(<BudgetVsSpend role="research-office" />);
    expect(await screen.findByText("₹10,50,000.00")).toBeTruthy();
    const { url, headers } = lastCall(fetchMock);
    expect(url).toBe("/api/v1/budget-grants/reports/budget-vs-spend?scope=grants");
    expect(headers.Authorization).toBe("Bearer test-token");
  });

  it.each([
    ["799.99", "79% used", null, null],
    ["800.00", "80% used", "Nearing limit", "eos-badge--warning"],
    ["1000.00", "100% used", "Fully used", "eos-badge--danger"],
    ["1000.01", "100% used", "Over budget", "eos-badge--danger"],
  ])("with ₹%s used of ₹1,000 shows %s and badge %s", async (spent, pct, badge, tone) => {
    stubFetch(answer(200, report({ allocated: "1000.00", committed: "0.00", spent, by_head: [] })));
    render(<BudgetVsSpend role="finance-staff" />);
    expect(await screen.findByText(pct)).toBeTruthy();
    const badges = Array.from(document.querySelectorAll(".eos-budget__overall .eos-badge"));
    if (badge === null) {
      expect(badges).toHaveLength(0);
    } else {
      expect(badges.map((b) => b.textContent)).toEqual([badge]);
      expect(badges[0]!.className).toContain(tone);
    }
  });

  it("marks a negative available amount and spend with nothing allocated", async () => {
    stubFetch(answer(200, report({ allocated: "0.00", committed: "0.00", spent: "5000.00", by_head: [] })));
    render(<BudgetVsSpend role="finance-staff" />);
    expect((await screen.findByText("-₹5,000.00")).closest("[data-warn]")).toBeTruthy();
    expect(screen.getByText("—")).toBeTruthy();
    expect(screen.getByText("Over budget").className).toContain("eos-badge--danger");
  });

  it("shows an empty state when nothing is allocated, committed or spent", async () => {
    stubFetch(answer(200, nothing()));
    render(<BudgetVsSpend role="finance-staff" />);
    expect(await screen.findByText("No budget allocated")).toBeTruthy();
    expect(screen.getByText("Allocations and spend appear here once a budget is set for 2026-27.")).toBeTruthy();
    expect(screen.queryByRole("progressbar")).toBeNull();
  });

  it("shows the grants empty state on the Research Office dashboard", async () => {
    stubFetch(answer(200, nothing()));
    render(<BudgetVsSpend role="research-office" />);
    expect(await screen.findByText("No grants to show")).toBeTruthy();
  });

  it("is not empty while heads exist, even with nothing allocated yet", async () => {
    const heads = [{ budget_head_id: "h1", name: "Salaries", allocated: "0.00", committed: "0.00", spent: "0.00" }];
    stubFetch(answer(200, nothing({ by_head: heads })));
    render(<BudgetVsSpend role="finance-staff" />);
    expect(await screen.findByText("Salaries")).toBeTruthy();
    expect(screen.queryByText("No budget allocated")).toBeNull();
  });

  it("shows a generic error, never the server's message, and retries", async () => {
    const fetchMock = stubFetch(answer(500, { code: "internal", message: "Database unavailable" }), answer(200, report()));
    render(<BudgetVsSpend role="finance-staff" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Could not load budget data.");
    expect(alert.textContent).not.toContain("Database unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("₹10,50,000.00")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shows an error when the service cannot be reached, and retries", async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValueOnce(answer(200, report()));
    vi.stubGlobal("fetch", fetchMock);
    render(<BudgetVsSpend role="finance-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Budget data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("₹10,50,000.00")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("offers no retry when the viewer lacks the permission", async () => {
    stubFetch(answer(403, { code: "forbidden", message: "Forbidden" }));
    render(<BudgetVsSpend role="finance-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});

const myGrants = (): MyGrant[] => [
  {
    id: "g1",
    code: "SERB/CRG/2025/001234",
    title: "Biomechanics of sprint starts",
    funder: "SERB",
    my_role: "principal",
    sanctioned_amount: "2500000.00",
    spent_total: "900000.00",
    balance: "600000.00",
    end_date: "2028-03-31",
    next_uc_due: "2026-11-05",
  },
  {
    id: "g2",
    code: "ICMR/2024/77",
    title: "Nutrition in endurance athletes",
    funder: "ICMR",
    my_role: "co_investigator",
    sanctioned_amount: "1200000.00",
    spent_total: "300000.00",
    balance: "450000.00",
    end_date: "2027-06-30",
    next_uc_due: "2026-10-01",
  },
  {
    id: "g3",
    code: "DST/SR/2026/9",
    title: "Recovery monitoring with wearables",
    funder: "DST",
    my_role: "principal",
    sanctioned_amount: "800000.00",
    spent_total: "0.00",
    balance: "200000.00",
    end_date: "2029-03-31",
    next_uc_due: "2027-04-30",
  },
  {
    id: "g4",
    code: "INT/2023/5",
    title: "Coaching analytics pilot",
    funder: "Sports Authority of India",
    my_role: "co_investigator",
    sanctioned_amount: "300000.00",
    spent_total: "300000.00",
    balance: "0.00",
    end_date: "2026-09-30",
    next_uc_due: null,
  },
];

describe("budget-grants.my-grants", () => {
  beforeEach(() => {
    // Only the clock is faked, so testing-library's waits still run.
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-23T10:00:00"));
  });

  it("lists each grant with funder, amounts and the next certificate due from GET /me/grants", async () => {
    const fetchMock = stubFetch(answer(200, myGrants()));
    render(<MyGrants role="research-scholar" />);
    expect(screen.getByLabelText("Loading").getAttribute("aria-busy")).toBe("true");
    const list = await screen.findByRole("list", { name: "My grants" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(4);
    expect(within(rows[0]!).getByText("Biomechanics of sprint starts")).toBeTruthy();
    expect(within(rows[0]!).getByText("SERB · SERB/CRG/2025/001234 · Principal investigator")).toBeTruthy();
    expect(within(rows[0]!).getByText("Sanctioned ₹25,00,000.00 · Spent ₹9,00,000.00")).toBeTruthy();
    expect(within(rows[0]!).getByText("Next certificate due 5 Nov 2026")).toBeTruthy();
    expect(within(rows[0]!).getByText("₹6,00,000.00")).toBeTruthy();
    expect(within(rows[1]!).getByText("ICMR · ICMR/2024/77 · Co-investigator")).toBeTruthy();
    expect(within(rows[3]!).getByText("No certificate due")).toBeTruthy();
    const { url, headers } = lastCall(fetchMock);
    expect(url).toBe("/api/v1/budget-grants/me/grants");
    expect(headers.Authorization).toBe("Bearer test-token");
  });

  it("flags a certificate due within 30 days as a warning and a past one as overdue", async () => {
    stubFetch(answer(200, myGrants()));
    render(<MyGrants role="research-scholar" />);
    const rows = within(await screen.findByRole("list", { name: "My grants" })).getAllByRole("listitem");
    expect(within(rows[0]!).getByText("Certificate due soon").className).toContain("eos-badge--warning");
    expect(within(rows[1]!).getByText("Certificate overdue").className).toContain("eos-badge--danger");
    expect(rows[2]!.querySelector(".eos-badge")).toBeNull();
    expect(rows[3]!.querySelector(".eos-badge")).toBeNull();
  });

  it("shows an empty state when the viewer is on no grant", async () => {
    stubFetch(answer(200, []));
    render(<MyGrants role="research-scholar" />);
    expect(await screen.findByText("No grants yet")).toBeTruthy();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = stubFetch(answer(503, {}), answer(200, myGrants()));
    render(<MyGrants role="research-scholar" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Budget data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Biomechanics of sprint starts")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("asks the user to sign in again, without a retry, on 401", async () => {
    stubFetch(answer(401, { detail: "Not authenticated" }));
    render(<MyGrants role="research-scholar" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});
