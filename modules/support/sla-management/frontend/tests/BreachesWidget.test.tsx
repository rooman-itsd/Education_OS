import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { BreachSummary } from "../src/api/client";
import { widgets } from "../src/widgets";
import { BreachesWidget, describeFailure, overdueLabel } from "../src/widgets/BreachesWidget";
import { SlaManagementApiError } from "../src/api/client";

const summary = (over: Partial<BreachSummary> = {}): BreachSummary => ({
  scope: "mine",
  breached_open: 2,
  at_risk: 1,
  breached_last_24h: 3,
  most_overdue: [
    { clock_id: "c1", ticket_id: "t1", ticket_number: "HD-000003", kind: "resolution", priority: "urgent", assignee_id: null, due_at: "2026-11-02T08:40:00+00:00", overdue_business_minutes: 130 },
    { clock_id: "c2", ticket_id: "t2", ticket_number: "HD-000001", kind: "response", priority: "high", assignee_id: null, due_at: "2026-11-02T10:00:00+00:00", overdue_business_minutes: 10 },
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
  localStorage.clear();
});

describe("sla-management.breaches widget", () => {
  it("is exported with the id and permission the Support Staff layout and the contract expect", () => {
    const w = widgets.find((x) => x.id === "sla-management.breaches");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("sla-management:clock:read");
    expect(w?.kind).toBe("list");
    expect(w?.size).toBe("1x1");
    expect(w?.component).toBe(BreachesWidget);
  });

  it("shows counts and the most overdue clocks from GET /stats/breaches?scope=mine with the session token", async () => {
    const fetchMock = answer(200, summary());
    vi.stubGlobal("fetch", fetchMock);
    render(<BreachesWidget role="support-staff" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("HD-000003 · Resolution")).toBeTruthy();
    expect(screen.getByText("2 breached")).toBeTruthy();
    expect(screen.getByText("1 at risk")).toBeTruthy();
    expect(screen.getByText("3 in the last 24 h")).toBeTruthy();
    expect(screen.getByText("2 h 10 min over")).toBeTruthy();
    expect(screen.getByText("10 min over")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows.map((r) => r.textContent?.match(/HD-\d+/)?.[0])).toEqual(["HD-000003", "HD-000001"]);
    expect(screen.getByRole("list", { name: "Most overdue" })).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/sla-management/stats/breaches?scope=mine");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("switches to every ticket", async () => {
    const fetchMock = answer(200, summary());
    vi.stubGlobal("fetch", fetchMock);
    render(<BreachesWidget role="support-staff" />);
    await screen.findByText("HD-000003 · Resolution");
    fireEvent.click(screen.getByRole("tab", { name: "All tickets" }));
    await screen.findByText("HD-000003 · Resolution");
    expect((fetchMock.mock.calls[1] as [string])[0]).toBe("/api/v1/sla-management/stats/breaches?scope=all");
  });

  it("shows an empty state when nothing is breached or at risk", async () => {
    vi.stubGlobal("fetch", answer(200, summary({ breached_open: 0, at_risk: 0, breached_last_24h: 0, most_overdue: [] })));
    render(<BreachesWidget role="support-staff" />);
    expect(await screen.findByText("Nothing breached or at risk")).toBeTruthy();
    expect(screen.getByText("Your tickets are within their SLA targets.")).toBeTruthy();
    expect(screen.getByText("0 breached")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 500, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => summary() });
    vi.stubGlobal("fetch", fetchMock);
    render(<BreachesWidget role="support-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load SLA breaches");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("HD-000003 · Resolution")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("says the data is not available yet while the API is not mounted (404), and can retry", async () => {
    vi.stubGlobal("fetch", answer(404, { detail: "Not Found" }));
    render(<BreachesWidget role="support-staff" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("SLA data is not available yet.");
    expect(alert.textContent).not.toContain("connection");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("says the data is not available yet on a network failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<BreachesWidget role="support-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("SLA data is not available yet.");
  });

  it("offers no retry when access is refused (403) or the session ended (401)", async () => {
    vi.stubGlobal("fetch", answer(403, { detail: { code: "forbidden" } }));
    render(<BreachesWidget role="support-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    expect(describeFailure(new SlaManagementApiError(401, ""))).toEqual({ title: "Sign in again to see this.", retry: false });
    expect(describeFailure(new SlaManagementApiError(502, "")).retry).toBe(true);
    expect(describeFailure(new SlaManagementApiError(503, "")).title).toBe("SLA data is not available yet.");
  });

  it("words how late a clock is", () => {
    expect(overdueLabel(undefined)).toBe("Breached");
    expect(overdueLabel(0)).toBe("Breached");
    expect(overdueLabel(1)).toBe("1 min over");
    expect(overdueLabel(60)).toBe("1 h over");
    expect(overdueLabel(61)).toBe("1 h 1 min over");
  });
});
