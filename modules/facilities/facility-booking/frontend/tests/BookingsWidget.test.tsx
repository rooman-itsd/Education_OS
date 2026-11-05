import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { dayLabel, type Booking, type BookingPage } from "../src/api/client";
import { widgets } from "../src/widgets";
import { BookingsWidget } from "../src/widgets/BookingsWidget";

const at = (hour: number, minute = 0, days = 0): string => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
};

const booking = (over: Partial<Booking>): Booking => ({
  id: "b-1",
  resource_id: "r-1",
  resource_name: "Track",
  start_at: at(7, 0, 2),
  end_at: at(9, 0, 2),
  status: "pending",
  title: "U19 sprints",
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

describe("facility-booking.bookings widget", () => {
  it("is exported with the id and permission the role layouts and the contract expect", () => {
    const w = widgets.find((x) => x.id === "facility-booking.bookings");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("facility-booking:booking:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(BookingsWidget);
  });

  it("asks for upcoming bookings on the resources the viewer approves, requests to approve in words", async () => {
    const fetchMock = api(page([booking({}), booking({ id: "b-2", start_at: at(10), end_at: at(11), status: "confirmed", title: null })]));
    vi.stubGlobal("fetch", fetchMock);
    render(<BookingsWidget role="coach" />);
    expect(await screen.findByText("Track · U19 sprints")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows[0]?.textContent).toContain("Today ·"); // earliest first, whatever order the page came in
    expect(rows[0]?.textContent).toContain("Confirmed");
    expect(rows[1]?.textContent).toContain(dayLabel(at(7, 0, 2)));
    expect(rows[1]?.textContent).toContain("Awaiting approval");
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/v1/facility-booking/bookings?scope=managed&from=now&status=pending,confirmed,checked_in&page_size=6",
    );
  });

  it("shows an empty state naming the resources the viewer approves", async () => {
    vi.stubGlobal("fetch", api(page([])));
    render(<BookingsWidget role="medical-staff" />);
    expect(await screen.findByText("No upcoming bookings")).toBeTruthy();
    expect(screen.getByText("Bookings on the spaces and equipment you approve appear here.")).toBeTruthy();
  });

  it("asks the viewer to sign in again when the session has expired (401), without a retry", async () => {
    vi.stubGlobal("fetch", api({}, 401));
    render(<BookingsWidget role="coach" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});

describe("dayLabel", () => {
  const now = new Date(2026, 9, 30, 12, 0); // 30 Oct 2026, local time

  it("names today and tomorrow, and dates the rest with weekday, day and month", () => {
    expect(dayLabel(new Date(2026, 9, 30, 8, 0).toISOString(), now)).toBe("Today");
    expect(dayLabel(new Date(2026, 9, 31, 23, 0).toISOString(), now)).toBe("Tomorrow");
    const later = new Date(2026, 10, 3, 9, 0);
    const weekday = later.toLocaleDateString("en-GB", { weekday: "short" });
    expect(dayLabel(later.toISOString(), now)).toBe(`${weekday} 3 Nov`);
  });

  it("says a dash for a missing or broken value instead of crashing", () => {
    expect(dayLabel(null, now)).toBe("—");
    expect(dayLabel("not a date", now)).toBe("—");
  });
});
