import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ActionItemStats, ActionItemSummary } from "../src/api/client";
import { widgets } from "../src/widgets";
import { ActionItemsWidget } from "../src/widgets/ActionItemsWidget";
import { dueLabel, statusLabel } from "../src/widgets/shared";

const item = (over: Partial<ActionItemSummary>): ActionItemSummary => ({
  id: "a1",
  title: "Revise the feedback form",
  owner_id: "u1",
  due_on: "2026-11-10",
  status: "open",
  overdue: false,
  ...over,
});

const stats = (over: Partial<ActionItemStats> = {}): ActionItemStats => ({
  open: 3,
  in_progress: 1,
  overdue: 1,
  due_soon: 2,
  due_soon_days: 14,
  soonest: [
    item({ id: "late", title: "Update the SSR annexures", due_on: "2026-11-01", overdue: true }),
    item({ id: "soon", title: "Revise the feedback form", due_on: "2026-11-15", status: "in_progress" }),
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

describe("iqac-accreditation widgets", () => {
  it("are exported with the id and permission the Governance layout and the contract expect", () => {
    expect(widgets.map((w) => w.id)).toEqual(["iqac-accreditation.action-items"]);
    expect(widgets[0]?.permission).toBe("iqac-accreditation:stats:read");
    expect(widgets[0]?.component).toBe(ActionItemsWidget);
  });

  it("words how soon an action item is due", () => {
    const today = new Date(2026, 10, 5);
    expect(dueLabel({ due_on: "2026-11-03", overdue: true }, today)).toEqual({ text: "Overdue by 2 days", tone: "danger" });
    expect(dueLabel({ due_on: "2026-11-05", overdue: false }, today)).toEqual({ text: "Due today", tone: "danger" });
    expect(dueLabel({ due_on: "2026-11-06", overdue: false }, today)).toEqual({ text: "Due in 1 day", tone: "warning" });
    expect(dueLabel({ due_on: "2026-11-30", overdue: false }, today)).toEqual({ text: "Due in 25 days", tone: "info" });
    expect(statusLabel("in_progress")).toBe("In progress");
  });
});

describe("iqac-accreditation.action-items", () => {
  it("shows the counts and the soonest items from GET /stats/action-items with the session token", async () => {
    const fetchMock = answer(200, stats());
    vi.stubGlobal("fetch", fetchMock);
    render(<ActionItemsWidget role="governance" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Update the SSR annexures")).toBeTruthy();
    expect(screen.getByText("3 open · 1 in progress · 1 overdue")).toBeTruthy();
    expect(screen.getByText("2 due in the next 14 days")).toBeTruthy();
    expect(screen.getByText("In progress")).toBeTruthy();
    expect(screen.getByRole("list", { name: "Action items" }).querySelectorAll("li")).toHaveLength(2);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/iqac-accreditation/stats/action-items");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("shows an empty state when nothing is open", async () => {
    vi.stubGlobal("fetch", answer(200, stats({ open: 0, in_progress: 0, overdue: 0, due_soon: 0, soonest: [] })));
    render(<ActionItemsWidget role="governance" />);
    expect(await screen.findByText("No open action items")).toBeTruthy();
  });

  it("says the data is not available yet while the API is not mounted (404), and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 404, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => stats() });
    vi.stubGlobal("fetch", fetchMock);
    render(<ActionItemsWidget role="governance" />);
    expect((await screen.findByRole("alert")).textContent).toContain("IQAC data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Update the SSR annexures")).toBeTruthy();
  });

  it("says the data is not available yet when the network fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<ActionItemsWidget role="governance" />);
    expect((await screen.findByRole("alert")).textContent).toContain("IQAC data is not available yet.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("offers no retry when access is refused (403) or the session ended (401)", async () => {
    vi.stubGlobal("fetch", answer(403, {}));
    render(<ActionItemsWidget role="governance" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    cleanup();
    vi.stubGlobal("fetch", answer(401, {}));
    render(<ActionItemsWidget role="governance" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("names the failure and offers a retry for any other server error", async () => {
    vi.stubGlobal("fetch", answer(500, {}));
    render(<ActionItemsWidget role="governance" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Could not load action items");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
