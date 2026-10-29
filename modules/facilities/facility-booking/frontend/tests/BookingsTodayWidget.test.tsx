import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clock, type Booking, type BookingPage, type Summary } from "../src/api/client";

/** A local time today (or `days` away), as the API sends it; the widget compares dates in the viewer's time. */
const at = (hour: number, minute = 0, days = 0): string => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
};
import { widgets } from "../src/widgets";
import { BookingsTodayWidget } from "../src/widgets/BookingsTodayWidget";

const booking = (over: Partial<Booking>): Booking => ({
  id: "b-1",
  resource_id: "r-1",
  resource_name: "Seminar hall",
  start_at: at(9),
  end_at: at(10, 30),
  status: "confirmed",
  title: "Guest lecture",
  ...over,
});

const summary = (over: Partial<Summary> = {}): Summary => ({
  date: "2026-10-28",
  bookings_today: 2,
  pending_approval: 1,
  checked_in_now: 0,
  no_shows_today: 0,
  resources_out_of_service: 0,
  ...over,
});

const page = (items: Booking[], total = items.length): BookingPage => ({ items, total, page: 1, page_size: 6 });

/** Answers each URL with its body; the widget loads the list and the summary together. */
function api(list: BookingPage, counts: Summary, status = 200) {
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

describe("facility-booking.bookings-today widget", () => {
  it("is exported with the id and permission the role layouts and the contract expect", () => {
    const w = widgets.find((x) => x.id === "facility-booking.bookings-today");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("facility-booking:booking:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(BookingsTodayWidget);
  });

  it("lists today's bookings earliest first, with counts and status in words", async () => {
    const fetchMock = api(
      page([
        booking({ id: "b-2", start_at: at(14), end_at: at(15), status: "pending", resource_name: "Music room 2", title: null }),
        booking({}),
      ]),
      summary(),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<BookingsTodayWidget role="facility-staff" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Seminar hall · Guest lecture")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.textContent).toContain("Confirmed");
    expect(rows[1]?.textContent).toContain("Music room 2");
    expect(rows[1]?.textContent).toContain("Awaiting approval");
    expect(screen.getByText(`${clock(at(9))}–${clock(at(10, 30))}`)).toBeTruthy();
    expect(screen.getByLabelText("Booking counts").textContent).toBe("2 today · 1 awaiting approval · 0 in use now");
    const urls = fetchMock.mock.calls.map((c) => c[0] as string).sort();
    expect(urls).toEqual([
      "/api/v1/facility-booking/bookings?scope=managed&date=today&status=pending,confirmed,checked_in,completed,no_show&page_size=6",
      "/api/v1/facility-booking/summary?date=today",
    ]);
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("says how many more there are today and names resources out of service", async () => {
    const six = Array.from({ length: 6 }, (_, i) => booking({ id: `b-${i}` }));
    vi.stubGlobal("fetch", api(page(six, 9), summary({ bookings_today: 9, pending_approval: 0, resources_out_of_service: 2 })));
    render(<BookingsTodayWidget role="facility-staff" />);
    expect(await screen.findByText("3 more today")).toBeTruthy();
    expect(screen.getByLabelText("Booking counts").textContent).toBe("9 today · 0 awaiting approval · 0 in use now · 2 out of service");
  });

  it("renders an unknown status or a missing resource name instead of crashing", async () => {
    const odd = booking({ status: "on_hold" as Booking["status"], resource_name: null });
    vi.stubGlobal("fetch", api(page([odd]), summary({ bookings_today: 1 })));
    render(<BookingsTodayWidget role="facility-staff" />);
    expect(await screen.findByText("on_hold")).toBeTruthy();
    expect(screen.getByText("Resource · Guest lecture")).toBeTruthy();
  });

  it("dates a start or end on another day, so an overnight booking is not read as a window within today", async () => {
    const overnight = booking({ id: "b-9", start_at: at(22, 0, -1), end_at: at(2), resource_name: "Lab 3", title: "Overnight run" });
    vi.stubGlobal("fetch", api(page([overnight]), summary({ bookings_today: 1, pending_approval: 0 })));
    render(<BookingsTodayWidget role="facility-staff" />);
    const day = new Date(at(22, 0, -1)).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
    expect(await screen.findByText(`${day} ${clock(at(22, 0, -1))}–${clock(at(2))}`)).toBeTruthy();
  });

  it("keeps the counts in sight when nothing is booked today but requests wait for approval", async () => {
    vi.stubGlobal("fetch", api(page([]), summary({ bookings_today: 0, pending_approval: 3, resources_out_of_service: 1 })));
    render(<BookingsTodayWidget role="facility-staff" />);
    expect(await screen.findByText("No bookings today")).toBeTruthy();
    expect(screen.getByLabelText("Booking counts").textContent).toBe("0 today · 3 awaiting approval · 0 in use now · 1 out of service");
  });

  it("shows an empty state when nothing is booked today", async () => {
    vi.stubGlobal("fetch", api(page([]), summary({ bookings_today: 0, pending_approval: 0 })));
    render(<BookingsTodayWidget role="facility-staff" />);
    expect(await screen.findByText("No bookings today")).toBeTruthy();
    expect(screen.queryByLabelText("Booking counts")).toBeNull(); // nothing needs attention
  });

  it("says the service is not available yet when it is missing or down, and retries", async () => {
    let fail = true;
    const fetchMock = vi.fn().mockImplementation(async (url: string) => {
      if (fail) return { ok: false, status: 404, statusText: "", json: async () => ({}) };
      return { ok: true, status: 200, statusText: "", json: async () => (url.includes("/summary") ? summary() : page([booking({})])) };
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<BookingsTodayWidget role="facility-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Booking data is not available yet.");
    fail = false;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Seminar hall · Guest lecture")).toBeTruthy();
  });

  it("offers no retry when the session has expired (401) or access is refused (403)", async () => {
    vi.stubGlobal("fetch", api(page([]), summary(), 403));
    render(<BookingsTodayWidget role="facility-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    cleanup();
    vi.stubGlobal("fetch", api(page([]), summary(), 401));
    render(<BookingsTodayWidget role="facility-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("names any other failure without blaming the connection, and still retries", async () => {
    vi.stubGlobal("fetch", api(page([]), summary(), 500));
    render(<BookingsTodayWidget role="facility-staff" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Could not load today's bookings");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
