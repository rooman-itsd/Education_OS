import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DeadlineItem, NearingDeadline } from "../src/api/client";
import { widgets } from "../src/widgets";
import { NearingDeadlineWidget } from "../src/widgets/NearingDeadlineWidget";
import { dateInIndia, dueLabel } from "../src/widgets/shared";

// The end of 12 November 2026 in India, as the API writes it.
const end = (day: string) => `${day}T18:29:59+00:00`;

const item = (over: Partial<DeadlineItem>): DeadlineItem => ({
  request_id: "r1",
  number: "RTI-000045",
  status: "assigned",
  due_at: end("2026-11-12"),
  overdue: false,
  ...over,
});

const stats = (over: Partial<NearingDeadline> = {}): NearingDeadline => ({
  within_days: 7,
  due_soon: 1,
  overdue: 1,
  items: [
    item({ request_id: "late", number: "RTI-000012", status: "received", due_at: end("2026-11-01"), overdue: true }),
    item({ request_id: "soon", number: "RTI-000045", due_at: end("2026-11-08") }),
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

describe("rti widgets", () => {
  it("export the id, permission and component the layout and the contract expect", () => {
    expect(widgets.map((w) => w.id)).toEqual(["rti.nearing-deadline"]);
    const [w] = widgets;
    expect(w?.permission).toBe("rti:stats:read");
    expect(w?.component).toBe(NearingDeadlineWidget);
  });

  it("read a due date as a date in India", () => {
    expect(dateInIndia("2026-11-12T18:29:59+00:00")).toBe("2026-11-12");
    expect(dateInIndia("2026-11-12T18:30:00+00:00")).toBe("2026-11-13");
    expect(dateInIndia(new Date("2026-11-05T19:00:00Z"))).toBe("2026-11-06");
  });

  it("word how soon an item is due", () => {
    const now = new Date("2026-11-05T09:00:00Z"); // the 5th, 14:30 in India
    expect(dueLabel({ due_at: end("2026-11-03"), overdue: true }, now)).toEqual({ text: "Overdue by 2 days", tone: "danger" });
    expect(dueLabel({ due_at: end("2026-11-04"), overdue: true }, now)).toEqual({ text: "Overdue by 1 day", tone: "danger" });
    expect(dueLabel({ due_at: end("2026-11-05"), overdue: false }, now)).toEqual({ text: "Due today", tone: "danger" });
    expect(dueLabel({ due_at: end("2026-11-06"), overdue: false }, now)).toEqual({ text: "Due in 1 day", tone: "warning" });
    expect(dueLabel({ due_at: end("2026-11-12"), overdue: false }, now)).toEqual({ text: "Due in 7 days", tone: "info" });
    // 19:00 UTC on the 5th is already the 6th in India
    const late = new Date("2026-11-05T19:00:00Z");
    expect(dueLabel({ due_at: end("2026-11-06"), overdue: false }, late).text).toBe("Due today");
  });
});

describe("rti.nearing-deadline", () => {
  it("shows the counts and the requests from GET /stats/nearing-deadline with the session token", async () => {
    const fetchMock = answer(200, stats());
    vi.stubGlobal("fetch", fetchMock);
    render(<NearingDeadlineWidget role="governance" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("RTI-000012")).toBeTruthy();
    expect(screen.getByText("1 overdue · 1 due in the next 7 days")).toBeTruthy();
    expect(screen.getByText("RTI-000045")).toBeTruthy();
    expect(screen.getByText("Received, not assigned · 2026-11-01")).toBeTruthy();
    expect(screen.getByText("Assigned, response due · 2026-11-08")).toBeTruthy();
    expect(screen.getByRole("list", { name: "RTI requests nearing a deadline" }).querySelectorAll("li")).toHaveLength(2);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/rti/stats/nearing-deadline");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("says in words whether each request is overdue or due", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-05T09:00:00Z"));
    vi.stubGlobal("fetch", answer(200, stats()));
    render(<NearingDeadlineWidget role="governance" />);
    expect(await screen.findByText("Overdue by 4 days")).toBeTruthy();
    expect(screen.getByText("Due in 3 days")).toBeTruthy();
  });

  it("shows an appeal as waiting for its decision", async () => {
    vi.stubGlobal("fetch", answer(200, stats({ items: [item({ status: "appealed" })] })));
    render(<NearingDeadlineWidget role="governance" />);
    expect(await screen.findByText("First appeal, decision due · 2026-11-12")).toBeTruthy();
  });

  it("shows nothing of an applicant", async () => {
    vi.stubGlobal("fetch", answer(200, stats()));
    const { container } = render(<NearingDeadlineWidget role="governance" />);
    await screen.findByText("RTI-000012");
    expect(container.textContent).not.toMatch(/applicant|address|@|phone/i);
  });

  it("shows an empty state with the window when nothing is close", async () => {
    vi.stubGlobal("fetch", answer(200, stats({ due_soon: 0, overdue: 0, items: [] })));
    render(<NearingDeadlineWidget role="governance" />);
    expect(await screen.findByText("No RTI deadlines close")).toBeTruthy();
    expect(screen.getByText("Open requests due in the next 7 days or overdue appear here.")).toBeTruthy();
  });

  it("says the data is not available yet while the API is not mounted (404), and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 404, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => stats() });
    vi.stubGlobal("fetch", fetchMock);
    render(<NearingDeadlineWidget role="governance" />);
    expect((await screen.findByRole("alert")).textContent).toContain("RTI data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("RTI-000012")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("says the data is not available yet when the network fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<NearingDeadlineWidget role="governance" />);
    expect((await screen.findByRole("alert")).textContent).toContain("RTI data is not available yet.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("offers no retry when sign-in or access is refused (401, 403)", async () => {
    vi.stubGlobal("fetch", answer(401, {}));
    render(<NearingDeadlineWidget role="governance" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    cleanup();
    vi.stubGlobal("fetch", answer(403, {}));
    render(<NearingDeadlineWidget role="governance" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("says what could not be loaded for any other failure, and retries", async () => {
    vi.stubGlobal("fetch", answer(500, {}));
    render(<NearingDeadlineWidget role="governance" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load RTI deadlines");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
