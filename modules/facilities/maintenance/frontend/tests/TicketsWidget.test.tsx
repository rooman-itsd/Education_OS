import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Priority, Summary, Ticket, TicketPage } from "../src/api/client";
import { widgets } from "../src/widgets";
import { TicketsWidget } from "../src/widgets/TicketsWidget";

const ticket = (over: Partial<Ticket>): Ticket => ({
  id: "t-1",
  number: "MT-2026-00001",
  kind: "corrective",
  title: "Projector will not turn on",
  target: { kind: "asset", id: "AST-0142", label: "Lab 2 projector" },
  priority: "medium",
  status: "assigned",
  blocks_use: false,
  assignee_id: "u-1",
  vendor: null,
  sla_breached: [],
  ...over,
});

const summary = (over: Partial<Summary> = {}): Summary => ({
  open: 2,
  unassigned: 1,
  in_progress: 0,
  on_hold: 0,
  urgent_open: 1,
  sla_breached_open: 1,
  resolved_awaiting_confirmation: 0,
  preventive_due_7_days: 0,
  ...over,
});

const page = (items: Ticket[], total = items.length): TicketPage => ({ items, total, page: 1, page_size: 5 });

/** Answers each URL with its body; the widget loads the list and the summary together. */
function api(list: TicketPage, counts: Summary, status = 200) {
  return vi.fn().mockImplementation(async (url: string) => ({
    ok: status < 400,
    status,
    statusText: "",
    json: async () => (url.includes("/summary") ? counts : list),
  }));
}

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("maintenance.tickets widget", () => {
  it("is exported with the id and permission the role layouts and the contract expect", () => {
    const w = widgets.find((x) => x.id === "maintenance.tickets");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("maintenance:ticket:read-all");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(TicketsWidget);
  });

  it("lists open tickets in the order the API gives, with counts and status in words", async () => {
    const fetchMock = api(
      page([
        ticket({ id: "t-1", priority: "urgent", sla_breached: ["response"], status: "open", blocks_use: true }),
        ticket({ id: "t-2", number: "MT-2026-00002", title: "Leaking tap", priority: "low", vendor: { name: "AquaFix" }, assignee_id: null }),
      ]),
      summary(),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<TicketsWidget role="facility-staff" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("MT-2026-00001 · Projector will not turn on")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.textContent).toContain("Past SLA");
    expect(rows[1]?.textContent).toContain("Low");
    expect(screen.getByText("Lab 2 projector · Unassigned · Out of use")).toBeTruthy();
    expect(screen.getByText("Lab 2 projector · Vendor: AquaFix")).toBeTruthy();
    expect(screen.getByLabelText("Ticket counts").textContent).toBe("2 open · 1 unassigned · 0 on hold · 1 past SLA");
    const urls = fetchMock.mock.calls.map((c) => c[0] as string).sort();
    expect(urls).toEqual(["/api/v1/maintenance/summary", "/api/v1/maintenance/tickets?scope=managed&open=true&page_size=5"]);
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("says how many more are open beyond the first five", async () => {
    const five = Array.from({ length: 5 }, (_, i) => ticket({ id: `t-${i}`, number: `MT-2026-0000${i}` }));
    vi.stubGlobal("fetch", api(page(five, 9), summary({ open: 9, sla_breached_open: 0 })));
    render(<TicketsWidget role="equipment-manager" />);
    expect(await screen.findByText("4 more open")).toBeTruthy();
    expect(screen.getByLabelText("Ticket counts").textContent).toBe("9 open · 1 unassigned · 0 on hold");
  });

  it("shows an empty state when nothing is open", async () => {
    vi.stubGlobal("fetch", api(page([]), summary({ open: 0, unassigned: 0, urgent_open: 0, sla_breached_open: 0 })));
    render(<TicketsWidget role="lab-in-charge" />);
    expect(await screen.findByText("No open tickets")).toBeTruthy();
  });

  it("renders a row that has no sla_breached or an unknown priority instead of crashing", async () => {
    const bare = ticket({ id: "t-9", number: "MT-2026-00009", title: "Door handle loose" }) as Partial<Ticket>;
    delete bare.sla_breached;
    const odd = ticket({ id: "t-8", number: "MT-2026-00008", priority: "critical" as Priority });
    vi.stubGlobal("fetch", api(page([bare as Ticket, odd]), summary({ sla_breached_open: 0 })));
    render(<TicketsWidget role="facility-staff" />);
    expect(await screen.findByText("MT-2026-00009 · Door handle loose")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.textContent).toContain("Medium");
    expect(rows[1]?.textContent).toContain("critical");
  });

  it("says the service is not available yet when it is missing or down (404, 503, network), and retries", async () => {
    let fail = true;
    const fetchMock = vi.fn().mockImplementation(async (url: string) => {
      if (fail) return { ok: false, status: 503, statusText: "", json: async () => ({}) };
      return { ok: true, status: 200, statusText: "", json: async () => (url.includes("/summary") ? summary() : page([ticket({})])) };
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<TicketsWidget role="facility-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Maintenance data is not available yet.");
    fail = false;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("MT-2026-00001 · Projector will not turn on")).toBeTruthy();
    cleanup();

    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<TicketsWidget role="facility-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Maintenance data is not available yet.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("offers no retry when the session has expired (401) or access is refused (403)", async () => {
    vi.stubGlobal("fetch", api(page([]), summary(), 403));
    render(<TicketsWidget role="facility-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    cleanup();

    vi.stubGlobal("fetch", api(page([]), summary(), 401));
    render(<TicketsWidget role="facility-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("shows a plain error with retry for any other failure", async () => {
    vi.stubGlobal("fetch", api(page([]), summary(), 500));
    render(<TicketsWidget role="facility-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load maintenance tickets");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
