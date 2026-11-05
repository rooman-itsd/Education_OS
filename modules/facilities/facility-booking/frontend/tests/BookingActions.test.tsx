import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Booking, BookingPage } from "../src/api/client";
import { BookingsWidget } from "../src/widgets/BookingsWidget";
import { MyBookingsWidget } from "../src/widgets/MyBookingsWidget";

/** A local time today (or `days` away), as the API sends it. */
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
  can: [],
  ...over,
});

const page = (items: Booking[], total = items.length): BookingPage => ({ items, total, page: 1, page_size: 6 });

type Reply = { status?: number; body?: unknown; statusText?: string } | Promise<never>;

/**
 * A fetch that answers GET /bookings with the next list in `lists` (the last one repeats) and a POST with `post`.
 * Every call is recorded, with its method, URL, body and signal.
 */
function api(lists: BookingPage[], post: () => Reply = () => ({ body: {} })) {
  let n = 0;
  return vi.fn().mockImplementation(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? "GET";
    const reply = method === "GET" ? { body: lists[Math.min(n++, lists.length - 1)] } : post();
    const { status = 200, body = {}, statusText = "" } = await reply;
    return { ok: status < 400, status, statusText, json: async () => body };
  });
}

type Call = [string, RequestInit | undefined];
const posts = (f: ReturnType<typeof vi.fn>): Call[] => (f.mock.calls as Call[]).filter(([, init]) => init?.method === "POST");
const gets = (f: ReturnType<typeof vi.fn>): Call[] => (f.mock.calls as Call[]).filter(([, init]) => (init?.method ?? "GET") === "GET");

const never = () => new Promise<never>(() => {});

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("row actions on the bookings widgets", () => {
  it("shows Check in and Cancel only when the booking's `can` lists them, never from status or role", async () => {
    vi.stubGlobal(
      "fetch",
      api([
        page([
          booking({ id: "b-1", resource_name: "Room A", can: ["check_in", "cancel"] }),
          booking({ id: "b-2", resource_name: "Room B", can: ["cancel", "edit"] }),
          booking({ id: "b-3", resource_name: "Room C", can: ["check_in"] }),
          booking({ id: "b-4", resource_name: "Room D", can: [] }),
          booking({ id: "b-5", resource_name: "Room E", can: undefined }),
          booking({ id: "b-6", resource_name: "Room F", status: "pending", can: ["approve", "reject"] }),
        ]),
      ]),
    );
    render(<BookingsWidget role="coach" />);
    await screen.findByText("Room A · Scales");
    const checkIns = screen.getAllByRole("button", { name: /^Check in: / }).map((b) => b.getAttribute("aria-label"));
    const cancels = screen.getAllByRole("button", { name: /^Cancel: / }).map((b) => b.getAttribute("aria-label"));
    expect(checkIns).toHaveLength(2);
    expect(checkIns[0]).toMatch(/^Check in: Room A · Scales, Tomorrow · /); // the name says which booking
    expect(checkIns[1]).toMatch(/^Check in: Room C/);
    expect(cancels).toHaveLength(2);
    expect(cancels[0]).toMatch(/^Cancel: Room A/);
    expect(cancels[1]).toMatch(/^Cancel: Room B/);
    // Rows whose `can` offers neither action have no buttons at all.
    for (const room of ["Room D", "Room E", "Room F"]) {
      const row = screen.getByText(`${room} · Scales`).closest("li") as HTMLElement;
      expect(row.querySelector("button")).toBeNull();
    }
  });

  it("asks the booker to confirm, cancels without a reason and loads the list again", async () => {
    const fetchMock = api([page([booking({ can: ["cancel"] })]), page([])]);
    vi.stubGlobal("fetch", fetchMock);
    render(<MyBookingsWidget role="musician" />);
    fireEvent.click(await screen.findByRole("button", { name: /^Cancel: Practice room 4/ }));
    expect(screen.getByText("Cancel this booking?")).toBeTruthy();
    expect(screen.queryByRole("textbox")).toBeNull(); // no reason asked of the booker
    fireEvent.click(screen.getByRole("button", { name: /^Cancel booking: Practice room 4/ }));
    expect(await screen.findByText("No upcoming bookings")).toBeTruthy();
    const [[url, init]] = posts(fetchMock) as [Call];
    expect(url).toBe("/api/v1/facility-booking/bookings/b-1/cancel");
    expect(init?.body).toBeUndefined();
    expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
    expect(gets(fetchMock)).toHaveLength(2);
  });

  it("keeps the booking when the confirm is declined", async () => {
    const fetchMock = api([page([booking({ can: ["cancel"] })])]);
    vi.stubGlobal("fetch", fetchMock);
    render(<MyBookingsWidget role="musician" />);
    fireEvent.click(await screen.findByRole("button", { name: /^Cancel: / }));
    fireEvent.click(screen.getByRole("button", { name: /^Keep booking: / }));
    expect(screen.queryByText("Cancel this booking?")).toBeNull();
    expect(screen.getByRole("button", { name: /^Cancel: / })).toBeTruthy();
    expect(posts(fetchMock)).toHaveLength(0);
  });

  it("on the managed list, asks for a reason before cancelling and sends it", async () => {
    const fetchMock = api([page([booking({ resource_name: "Track", title: "U19 sprints", can: ["cancel"] })]), page([])]);
    vi.stubGlobal("fetch", fetchMock);
    render(<BookingsWidget role="coach" />);
    fireEvent.click(await screen.findByRole("button", { name: /^Cancel: Track · U19 sprints/ }));
    const confirm = screen.getByRole("button", { name: /^Cancel booking: Track/ }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true); // no reason yet
    const reason = screen.getByRole("textbox", { name: "Reason for cancelling" });
    fireEvent.change(reason, { target: { value: "   " } });
    expect(confirm.disabled).toBe(true); // blanks are not a reason
    fireEvent.change(reason, { target: { value: "  Track resurfacing " } });
    expect(confirm.disabled).toBe(false);
    fireEvent.click(confirm);
    expect(await screen.findByText("No upcoming bookings")).toBeTruthy();
    const [[url, init]] = posts(fetchMock) as [Call];
    expect(url).toBe("/api/v1/facility-booking/bookings/b-1/cancel");
    expect(JSON.parse(String(init?.body))).toEqual({ reason: "Track resurfacing" });
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("checks in and shows the refreshed booking, now without the button", async () => {
    const fetchMock = api([
      page([booking({ start_at: at(0, 5), end_at: at(23, 55), can: ["check_in", "cancel"] })]),
      page([booking({ start_at: at(0, 5), end_at: at(23, 55), status: "checked_in", can: [] })]),
    ]);
    vi.stubGlobal("fetch", fetchMock);
    render(<MyBookingsWidget role="musician" />);
    fireEvent.click(await screen.findByRole("button", { name: /^Check in: Practice room 4 · Scales, Today/ }));
    expect(await screen.findByText("Checked in")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Check in: / })).toBeNull();
    const [[url, init]] = posts(fetchMock) as [Call];
    expect(url).toBe("/api/v1/facility-booking/bookings/b-1/check-in");
    expect(init?.body).toBeUndefined();
  });

  it("says in its own words when the booking can no longer be cancelled (409), without the server's text", async () => {
    const fetchMock = api([page([booking({ can: ["cancel"] })])], () => ({
      status: 409,
      statusText: "a checked_in booking cannot be cancelled",
      body: { detail: "a checked_in booking cannot be cancelled" },
    }));
    vi.stubGlobal("fetch", fetchMock);
    render(<MyBookingsWidget role="musician" />);
    fireEvent.click(await screen.findByRole("button", { name: /^Cancel: / }));
    fireEvent.click(screen.getByRole("button", { name: /^Cancel booking: / }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe("This booking can no longer be cancelled.");
    expect(alert.closest("li")?.textContent).toContain("Practice room 4 · Scales"); // on the row itself
    expect(document.body.textContent).not.toContain("checked_in booking");
    expect(gets(fetchMock)).toHaveLength(1); // nothing to refresh
    expect((screen.getByRole("button", { name: /^Cancel booking: / }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("says when check-in is not open (409)", async () => {
    vi.stubGlobal("fetch", api([page([booking({ can: ["check_in"] })])], () => ({ status: 409 })));
    render(<MyBookingsWidget role="musician" />);
    fireEvent.click(await screen.findByRole("button", { name: /^Check in: / }));
    expect((await screen.findByRole("alert")).textContent).toBe("This booking cannot be checked in now.");
  });

  it("disables the row's buttons while its request runs", async () => {
    const fetchMock = api(
      [page([booking({ can: ["check_in", "cancel"] }), booking({ id: "b-2", resource_name: "Room B", can: ["cancel"] })])],
      never,
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<MyBookingsWidget role="musician" />);
    const checkIn = (await screen.findByRole("button", { name: /^Check in: Practice room 4/ })) as HTMLButtonElement;
    const cancel = screen.getByRole("button", { name: /^Cancel: Practice room 4/ }) as HTMLButtonElement;
    fireEvent.click(checkIn);
    expect(checkIn.disabled).toBe(true);
    expect(cancel.disabled).toBe(true);
    fireEvent.click(checkIn);
    expect(posts(fetchMock)).toHaveLength(1); // a second click sends nothing
    // Another row stays usable.
    expect((screen.getByRole("button", { name: /^Cancel: Room B/ }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("disables the confirm while the cancel runs", async () => {
    vi.stubGlobal("fetch", api([page([booking({ can: ["cancel"] })])], never));
    render(<BookingsWidget role="coach" />);
    fireEvent.click(await screen.findByRole("button", { name: /^Cancel: / }));
    fireEvent.change(screen.getByRole("textbox", { name: "Reason for cancelling" }), { target: { value: "Clash" } });
    fireEvent.click(screen.getByRole("button", { name: /^Cancel booking: / }));
    expect((screen.getByRole("button", { name: /^Cancel booking: / }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: /^Keep booking: / }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("textbox", { name: "Reason for cancelling" }) as HTMLInputElement).disabled).toBe(true);
  });

  it("aborts the list request when the widget goes away before it answers", async () => {
    const fetchMock = vi.fn().mockImplementation(never);
    vi.stubGlobal("fetch", fetchMock);
    const { unmount } = render(<MyBookingsWidget role="musician" />);
    const signal = (fetchMock.mock.calls[0]?.[1] as RequestInit).signal as AbortSignal;
    expect(signal.aborted).toBe(false);
    unmount();
    expect(signal.aborted).toBe(true);
  });

  it("aborts a row's request when the widget goes away before it answers", async () => {
    const fetchMock = api([page([booking({ can: ["check_in"] })])], never);
    vi.stubGlobal("fetch", fetchMock);
    const { unmount } = render(<MyBookingsWidget role="musician" />);
    fireEvent.click(await screen.findByRole("button", { name: /^Check in: / }));
    await waitFor(() => expect(posts(fetchMock)).toHaveLength(1));
    const [[, init]] = posts(fetchMock) as [Call];
    expect(init?.signal?.aborted).toBe(false);
    act(() => unmount());
    expect(init?.signal?.aborted).toBe(true);
  });
});
