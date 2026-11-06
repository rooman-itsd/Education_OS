import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Calendar, DueStats, FilingSummary } from "../src/api/client";
import { widgets } from "../src/widgets";
import { CalendarWidget, range } from "../src/widgets/CalendarWidget";
import { DueWidget } from "../src/widgets/DueWidget";
import { dueLabel } from "../src/widgets/shared";

const filing = (over: Partial<FilingSummary>): FilingSummary => ({
  filing_id: "f1",
  obligation_title: "Annual return",
  authority: "State Council",
  period_label: "2025-26",
  due_on: "2026-11-10",
  status: "in_preparation",
  overdue: false,
  ...over,
});

const due = (over: Partial<DueStats> = {}): DueStats => ({
  scope: "mine",
  due_soon_days: 30,
  due_soon: 1,
  overdue: 1,
  soonest: [
    filing({ filing_id: "late", obligation_title: "Fire safety return", due_on: "2026-11-01", overdue: true }),
    filing({ filing_id: "soon", obligation_title: "Annual return", due_on: "2026-11-15" }),
  ],
  ...over,
});

function answer(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({ ok: status < 400, status, statusText: "", json: async () => body });
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

describe("regulatory-reports widgets", () => {
  it("are exported with the ids and permissions the layouts and the contract expect", () => {
    const dueWidget = widgets.find((w) => w.id === "regulatory-reports.due");
    const calendar = widgets.find((w) => w.id === "regulatory-reports.compliance-calendar");
    expect(dueWidget?.permission).toBe("regulatory-reports:stats:read");
    expect(dueWidget?.component).toBe(DueWidget);
    expect(calendar?.permission).toBe("regulatory-reports:data:read");
    expect(calendar?.component).toBe(CalendarWidget);
  });

  it("words how soon a filing is due", () => {
    const today = new Date(2026, 10, 5);
    expect(dueLabel({ due_on: "2026-11-03", overdue: true }, today)).toEqual({ text: "Overdue by 2 days", tone: "danger" });
    expect(dueLabel({ due_on: "2026-11-05", overdue: false }, today)).toEqual({ text: "Due today", tone: "danger" });
    expect(dueLabel({ due_on: "2026-11-06", overdue: false }, today)).toEqual({ text: "Due in 1 day", tone: "warning" });
    expect(dueLabel({ due_on: "2026-11-30", overdue: false }, today)).toEqual({ text: "Due in 25 days", tone: "info" });
  });
});

describe("regulatory-reports.due", () => {
  it("shows my overdue and due-soon filings from GET /stats/due with the session token", async () => {
    const fetchMock = answer(200, due());
    vi.stubGlobal("fetch", fetchMock);
    render(<DueWidget role="research-office" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Fire safety return")).toBeTruthy();
    expect(screen.getByText("1 overdue · 1 due in the next 30 days")).toBeTruthy();
    expect(screen.getAllByText("State Council · 2025-26")).toHaveLength(2);
    expect(screen.getByRole("list", { name: "Filings due" }).querySelectorAll("li")).toHaveLength(2);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/regulatory-reports/stats/due?scope=mine");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("switches to all filings, and says so when the role may not see them", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => due() })
      .mockResolvedValueOnce({ ok: false, status: 403, statusText: "", json: async () => ({}) });
    vi.stubGlobal("fetch", fetchMock);
    render(<DueWidget role="research-office" />);
    await screen.findByText("Fire safety return");
    fireEvent.click(screen.getByRole("button", { name: "All" }));
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect((fetchMock.mock.calls[1] as [string])[0]).toBe("/api/v1/regulatory-reports/stats/due?scope=all");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("shows an empty state with the window when nothing is due", async () => {
    vi.stubGlobal("fetch", answer(200, due({ due_soon: 0, overdue: 0, soonest: [] })));
    render(<DueWidget role="governance" />);
    expect(await screen.findByText("Nothing due")).toBeTruthy();
    expect(screen.getByText("Filings due in the next 30 days or overdue appear here.")).toBeTruthy();
  });

  it("says the data is not available yet while the API is not mounted (404), and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 404, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => due() });
    vi.stubGlobal("fetch", fetchMock);
    render(<DueWidget role="governance" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Regulatory report data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Fire safety return")).toBeTruthy();
  });
});

describe("regulatory-reports.compliance-calendar", () => {
  it("asks for the next 90 days and lists filings with their status in words", async () => {
    const cal: Calendar = {
      from: "2026-11-05",
      to: "2027-02-03",
      items: [
        filing({ filing_id: "a", obligation_title: "Fire safety return", due_on: "2026-11-01", overdue: true }),
        filing({ filing_id: "b", obligation_title: "Annual return", status: "under_review" }),
      ],
    };
    const fetchMock = answer(200, cal);
    vi.stubGlobal("fetch", fetchMock);
    render(<CalendarWidget role="management" />);
    expect(await screen.findByText("Annual return")).toBeTruthy();
    expect(screen.getByText("Overdue")).toBeTruthy();
    expect(screen.getByText("Under review")).toBeTruthy();
    const [from, to] = range();
    expect((fetchMock.mock.calls[0] as [string])[0]).toBe(`/api/v1/regulatory-reports/calendar?from=${from}&to=${to}`);
  });

  it("covers 90 days from today", () => {
    expect(range(new Date(2026, 10, 5))).toEqual(["2026-11-05", "2027-02-03"]);
  });

  it("shows an empty state, and refuses retry when access is refused (403)", async () => {
    vi.stubGlobal("fetch", answer(200, { from: "2026-11-05", to: "2027-02-03", items: [] }));
    render(<CalendarWidget role="management" />);
    expect(await screen.findByText("No filings due")).toBeTruthy();
    cleanup();
    vi.stubGlobal("fetch", answer(403, {}));
    render(<CalendarWidget role="management" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});
