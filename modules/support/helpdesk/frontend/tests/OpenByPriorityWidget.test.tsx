import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { OpenByPriority } from "../src/api/client";
import { widgets } from "../src/widgets";
import { OpenByPriorityWidget } from "../src/widgets/OpenByPriorityWidget";

const counts = (over: Partial<OpenByPriority> = {}): OpenByPriority => ({
  scope: "my_queues",
  total_open: 5,
  rows: [
    { priority: "urgent", open: 1, unassigned: 1, assigned_to_me: 0, on_hold: 0, oldest_created_at: "2026-10-20T08:00:00+00:00" },
    { priority: "high", open: 3, unassigned: 1, assigned_to_me: 2, on_hold: 1, oldest_created_at: "2026-10-19T08:00:00+00:00" },
    { priority: "medium", open: 0, unassigned: 0, assigned_to_me: 0, on_hold: 0, oldest_created_at: null },
    { priority: "low", open: 1, unassigned: 0, assigned_to_me: 1, on_hold: 0, oldest_created_at: "2026-10-18T08:00:00+00:00" },
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

describe("helpdesk.open-by-priority widget", () => {
  it("is exported with the id and permission the Support Staff layout and the contract expect", () => {
    const w = widgets.find((x) => x.id === "helpdesk.open-by-priority");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("helpdesk:ticket:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(OpenByPriorityWidget);
  });

  it("lists every priority, urgent first, from GET /stats/open-by-priority with the session token", async () => {
    const fetchMock = answer(200, counts());
    vi.stubGlobal("fetch", fetchMock);
    render(<OpenByPriorityWidget role="support-staff" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Urgent")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows.map((r) => r.textContent?.match(/Urgent|High|Medium|Low/)?.[0])).toEqual([
      "Urgent",
      "High",
      "Medium",
      "Low",
    ]);
    expect(screen.getByText("3 open")).toBeTruthy();
    expect(screen.getByText("1 unassigned · 2 assigned to you · 1 on hold")).toBeTruthy();
    expect(screen.getByText("0 open")).toBeTruthy(); // a priority with no open tickets keeps its row
    expect(screen.getByRole("list", { name: "Open tickets by priority" })).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/helpdesk/stats/open-by-priority");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("shows an empty state when nothing is open", async () => {
    const empty = counts({
      total_open: 0,
      rows: counts().rows.map((r) => ({ ...r, open: 0, unassigned: 0, assigned_to_me: 0, on_hold: 0 })),
    });
    vi.stubGlobal("fetch", answer(200, empty));
    render(<OpenByPriorityWidget role="support-staff" />);
    expect(await screen.findByText("No open tickets")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 503, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => counts() });
    vi.stubGlobal("fetch", fetchMock);
    render(<OpenByPriorityWidget role="support-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load open tickets");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Urgent")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
