import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clock, dayLabel, type Booking, type BookingPage } from "../src/api/client";
import { widgets } from "../src/widgets";
import { MyBookingsWidget } from "../src/widgets/MyBookingsWidget";

/** A local time today (or `days` away), as the API sends it; the widget compares dates in the viewer's time. */
const at = (hour: number, minute = 0, days = 0): string => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
};

const booking = (over: Partial<Booking>): Booking => ({
  id: "b-1",
  resource_id: "r-1",
  resource_name: "Practice room 4",
  start_at: at(9, 0, 1),
  end_at: at(10, 0, 1),
  status: "confirmed",
  title: "Scales",
  ...over,
});

const page = (items: Booking[], total = items.length): BookingPage => ({ items, total, page: 1, page_size: 6 });

function api(body: BookingPage | Record<string, never>, status = 200) {
  return vi.fn().mockImplementation(async () => ({ ok: status < 400, status, statusText: "", json: async () => body }));
}

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("facility-booking.my-bookings widget", () => {
  it("is exported with the id and permission the role layouts and the contract expect", () => {
    const w = widgets.find((x) => x.id === "facility-booking.my-bookings");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("facility-booking:booking:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(MyBookingsWidget);
  });

  it("asks for the caller's own bookings not yet over, and lists them earliest first with day and status", async () => {
    const fetchMock = api(
      page([
        booking({ id: "b-2", start_at: at(14, 0, 3), end_at: at(15, 0, 3), status: "pending", resource_name: "Recital hall", title: null }),
        booking({}),
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<MyBookingsWidget role="musician" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Practice room 4 · Scales")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.textContent).toContain(`Tomorrow · ${clock(at(9, 0, 1))}–${clock(at(10, 0, 1))}`);
    expect(rows[0]?.textContent).toContain("Confirmed");
    expect(rows[1]?.textContent).toContain(dayLabel(at(14, 0, 3)));
    expect(rows[1]?.textContent).toContain("Recital hall");
    expect(rows[1]?.textContent).toContain("Awaiting approval");
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/v1/facility-booking/bookings?scope=mine&from=now&status=pending,confirmed,checked_in&page_size=6",
    );
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("shows a booking under way as today, and an overnight one with its end date", async () => {
    const overnight = booking({ id: "b-3", start_at: at(22), end_at: at(2, 0, 1), status: "checked_in", title: "Late rehearsal" });
    vi.stubGlobal("fetch", api(page([overnight])));
    render(<MyBookingsWidget role="musician" />);
    const end = new Date(at(2, 0, 1)).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
    expect(await screen.findByText(`Today · ${clock(at(22))}–${end} ${clock(at(2, 0, 1))}`)).toBeTruthy();
    expect(screen.getByText("Checked in")).toBeTruthy();
  });

  it("says how many more there are", async () => {
    const six = Array.from({ length: 6 }, (_, i) => booking({ id: `b-${i}` }));
    vi.stubGlobal("fetch", api(page(six, 8)));
    render(<MyBookingsWidget role="musician" />);
    expect(await screen.findByText("2 more upcoming")).toBeTruthy();
  });

  it("shows an empty state when nothing is booked", async () => {
    vi.stubGlobal("fetch", api(page([])));
    render(<MyBookingsWidget role="musician" />);
    expect(await screen.findByText("No upcoming bookings")).toBeTruthy();
    expect(screen.getByText("Spaces and equipment you book appear here.")).toBeTruthy();
  });

  it("says the service is not available yet when it is missing or down, and retries", async () => {
    let fail = true;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async () =>
        fail
          ? { ok: false, status: 503, statusText: "", json: async () => ({}) }
          : { ok: true, status: 200, statusText: "", json: async () => page([booking({})]) },
      ),
    );
    render(<MyBookingsWidget role="musician" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Booking data is not available yet.");
    fail = false;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Practice room 4 · Scales")).toBeTruthy();
  });

  it("offers no retry when access is refused (403), and names any other failure", async () => {
    vi.stubGlobal("fetch", api({}, 403));
    render(<MyBookingsWidget role="musician" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    cleanup();
    vi.stubGlobal("fetch", api({}, 500));
    render(<MyBookingsWidget role="musician" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load upcoming bookings");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
