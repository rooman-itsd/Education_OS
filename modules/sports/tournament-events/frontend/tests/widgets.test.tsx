import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { WidgetProps } from "@eos/ui-kit";
import type { CalendarEntry, Entry, Fixture, Tournament } from "../src/api/client";
import { widgets } from "../src/widgets";
import { calendarDays, dateTime, day, isoDay } from "../src/widgets/format";
import { DAYS, SHOWN as CALENDAR_SHOWN, TournamentCalendar } from "../src/widgets/TournamentCalendar";
import { entriesOpen, SHOWN, UpcomingTournaments } from "../src/widgets/UpcomingTournaments";

const BASE = "/api/v1/tournament-events";

type Reply = { status: number; body: unknown };
const ok = (body: unknown): Reply => ({ status: 200, body });
const notFound: Reply = { status: 404, body: { detail: "Not Found" } };
const forbidden: Reply = { status: 403, body: { code: "forbidden", message: "no" } };

/**
 * Stubs fetch by path (without the query): each handler answers a request to that path. A request to a path with
 * no handler fails the test.
 */
function stubApi(routes: Record<string, Reply | ((url: URL) => Reply)>) {
  const fetchMock = vi.fn(async (input: string, _init?: RequestInit) => {
    const url = new URL(input, "http://localhost");
    const route = routes[url.pathname.slice(BASE.length)];
    if (!route) throw new Error(`unexpected request ${input}`);
    const r = typeof route === "function" ? route(url) : route;
    return { ok: r.status < 400, status: r.status, statusText: "", json: async () => r.body };
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const urls = (fetchMock: { mock: { calls: unknown[][] } }) => fetchMock.mock.calls.map((c) => String(c[0]));
const page = <T,>(items: T[], total = items.length) => ({ items, total });

/** A local day some days from today as a contract date-time: its local midnight, or a local hour of it. */
const localAt = (offsetDays: number, hour = 0, minute = 0) => {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate() + offsetDays, hour, minute).toISOString();
};

const tournament = (id: string, name: string, status: Tournament["status"], start: number, end: number, extra: Partial<Tournament> = {}): Tournament => ({
  id,
  name,
  discipline: "Athletics",
  level: "state",
  start_date: isoDay(start),
  end_date: isoDay(end),
  status,
  ...extra,
});
const entry = (id: string, category: string, status: Entry["status"] = "confirmed"): Entry => ({ id, category, athlete_ids: ["a-me"], status });
const fixture = (id: string, round: string, entryIds: string[], at: string, extra: Partial<Fixture> = {}): Fixture => ({
  id,
  round,
  entry_ids: entryIds,
  scheduled_at: at,
  status: "scheduled",
  ...extra,
});

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("widget declarations", () => {
  const expected: [string, string, string, string, string, ComponentType<WidgetProps>][] = [
    ["tournament-events.upcoming", "Upcoming tournaments", "tournament-events:tournament:read", "2x1", "list", UpcomingTournaments],
    ["tournament-events.calendar", "Tournament calendar", "tournament-events:tournament:read", "2x1", "list", TournamentCalendar],
  ];

  it("exports the widgets the athlete and coach layouts name", () => {
    expect(widgets.map((w) => w.id)).toEqual(expected.map((e) => e[0]));
  });

  it.each(expected)("registers %s as %s with permission %s, size %s, kind %s and its component", (id, title, permission, size, kind, component) => {
    const w = widgets.find((x) => x.id === id);
    expect(w?.title).toBe(title);
    expect(w?.permission).toBe(permission);
    expect(w?.size).toBe(size);
    expect(w?.kind).toBe(kind);
    expect(w?.component).toBe(component);
  });
});

describe("format", () => {
  it("writes dates as 5 Nov 2026 and times in local time", () => {
    expect(day("2026-11-05")).toBe("5 Nov 2026");
    expect(dateTime(new Date(2026, 10, 5, 9, 30).toISOString())).toBe("5 Nov 2026, 09:30");
  });

  it("reads a calendar tournament's last day as the day before ends_at", () => {
    const start = new Date(2026, 10, 5).toISOString();
    expect(calendarDays(start, new Date(2026, 10, 8).toISOString())).toBe("5 Nov 2026 – 7 Nov 2026");
    expect(calendarDays(start, new Date(2026, 10, 6).toISOString())).toBe("5 Nov 2026");
  });

  it("takes entries until the registration deadline, inclusive, and never after the tournament ends", () => {
    const t = tournament("t", "T", "published", 10, 12, { registration_closes_on: isoDay(3) });
    expect(entriesOpen(t, isoDay(3))).toBe(true);
    expect(entriesOpen(t, isoDay(4))).toBe(false);
    expect(entriesOpen(tournament("t", "T", "ongoing", -1, 2), isoDay(2))).toBe(true);
    expect(entriesOpen(tournament("t", "T", "ongoing", -1, 2), isoDay(3))).toBe(false);
  });
});

describe("tournament-events.upcoming", () => {
  const meet = tournament("t-meet", "State Athletics Meet", "ongoing", -1, 1, { venue: "City Stadium" });
  const uni = tournament("t-uni", "Inter-University Games", "published", 10, 12, {
    level: "inter_university",
    registration_closes_on: isoDay(5),
  });
  const cup = tournament("t-cup", "Founders' Cup", "published", 20, 20, { level: "intra_institution", registration_closes_on: isoDay(-1) });

  const listed = (url: URL) => (url.searchParams.get("status") === "ongoing" ? ok(page([meet])) : ok(page([uni, cup])));
  const routes = (over: Record<string, Reply | ((url: URL) => Reply)> = {}) => ({
    "/tournaments": listed,
    "/tournaments/t-meet/entries": ok(page([entry("e-100", "Men's 100 m"), entry("e-relay", "4x100 m relay", "pending"), entry("e-old", "200 m", "withdrawn")])),
    "/tournaments/t-meet/fixtures": ok(
      page([
        fixture("f-final", "Final", ["e-100"], localAt(1, 16, 0), { category: "Men's 100 m", venue: "Track 2" }),
        fixture("f-heat", "Heat 2", ["e-100", "e-x"], localAt(1, 9, 30), { category: "Men's 100 m" }),
        fixture("f-relay", "Relay heat", ["e-relay"], localAt(2, 11, 0), { status: "in_progress" }),
        fixture("f-other", "Heat 1", ["e-x"], localAt(1, 9, 0)),
        fixture("f-done", "Heat 0", ["e-100"], localAt(0, 0, 0), { status: "completed" }),
        fixture("f-off", "Heat 3", ["e-100"], localAt(1, 12, 0), { status: "postponed" }),
      ]),
    ),
    "/tournaments/t-uni/entries": ok(page([])),
    "/tournaments/t-cup/entries": ok(page([])),
    ...over,
  });

  it("lists ongoing then upcoming tournaments with the athlete's entries, and their next fixtures", async () => {
    const fetchMock = stubApi(routes());
    render(<UpcomingTournaments role="athlete" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    const list = await screen.findByRole("list", { name: "Upcoming tournaments" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]?.textContent).toContain("State Athletics Meet");
    expect(items[0]?.textContent).toContain(`${day(isoDay(-1))} – ${day(isoDay(1))} · City Stadium · State · Entered in Men's 100 m, 4x100 m relay`);
    expect(items[0]?.textContent).toContain("Ongoing");
    expect(items[0]?.textContent).toContain("Entered");
    expect(items[0]?.textContent).not.toContain("200 m ");
    expect(items[1]?.textContent).toContain("Inter-University Games");
    expect(items[1]?.textContent).toContain(`Inter-university · Entries close on ${day(isoDay(5))}`);
    expect(items[1]?.textContent).toContain("Entries open");
    expect(items[2]?.textContent).toContain(`${day(isoDay(20))} · Intra-institution`);
    expect(items[2]?.textContent).toContain("Entries closed");

    const next = within(screen.getByRole("list", { name: "Your next fixtures" })).getAllByRole("listitem");
    expect(next).toHaveLength(3);
    expect(next[0]?.textContent).toContain("Heat 2 (Men's 100 m)");
    expect(next[1]?.textContent).toContain("Final (Men's 100 m)");
    expect(next[2]?.textContent).toContain("Relay heat");
    expect(next[0]?.textContent).toContain(`State Athletics Meet · ${dateTime(localAt(1, 9, 30))} · City Stadium`);
    expect(next[1]?.textContent).toContain("Track 2");
    expect(next[2]?.textContent).toContain("In progress");
    expect(screen.queryByText(/more$/)).toBeNull();

    const called = urls(fetchMock);
    expect(called.slice(0, 2).sort()).toEqual([`${BASE}/tournaments?status=ongoing&limit=${SHOWN}`, `${BASE}/tournaments?status=published&limit=${SHOWN}`]);
    expect(called).toContain(`${BASE}/tournaments/t-meet/entries?limit=200`);
    expect(called).toContain(`${BASE}/tournaments/t-meet/fixtures?from=${isoDay()}&limit=200`);
    // fixtures are read only where the athlete is entered
    expect(called.filter((u) => u.includes("/fixtures"))).toHaveLength(1);
    expect(called).toHaveLength(6);
    expect((fetchMock.mock.calls[0]?.[1] as unknown as { headers: Record<string, string> }).headers.Authorization).toBe("Bearer test-token");
  });

  it("says when only a pending entry is in", async () => {
    stubApi(
      routes({
        "/tournaments": (url: URL) => (url.searchParams.get("status") === "ongoing" ? ok(page([])) : ok(page([uni]))),
        "/tournaments/t-uni/entries": ok(page([entry("e-1", "Long jump", "pending")])),
        "/tournaments/t-uni/fixtures": ok(page([])),
      }),
    );
    render(<UpcomingTournaments role="athlete" />);
    const items = within(await screen.findByRole("list", { name: "Upcoming tournaments" })).getAllByRole("listitem");
    expect(items[0]?.textContent).toContain("Entry pending");
    expect(items[0]?.textContent).toContain("Entered in Long jump");
    expect(screen.queryByRole("list", { name: "Your next fixtures" })).toBeNull();
  });

  it("lists five tournaments and says how many more", async () => {
    const many = Array.from({ length: SHOWN }, (_, i) => tournament(`t-${i}`, `Meet ${i}`, "published", 5 + i, 5 + i));
    const entries = Object.fromEntries(many.map((t) => [`/tournaments/${t.id}/entries`, ok(page([]))]));
    stubApi({
      "/tournaments": (url: URL) => (url.searchParams.get("status") === "ongoing" ? ok(page([meet], 2)) : ok(page(many, 9))),
      "/tournaments/t-meet/entries": ok(page([])),
      ...entries,
    });
    render(<UpcomingTournaments role="athlete" />);
    expect(within(await screen.findByRole("list", { name: "Upcoming tournaments" })).getAllByRole("listitem")).toHaveLength(SHOWN);
    expect(screen.getByText("and 6 tournaments more")).toBeTruthy();
  });

  it("has an empty state", async () => {
    const fetchMock = stubApi({ "/tournaments": ok(page([])) });
    render(<UpcomingTournaments role="athlete" />);
    expect(await screen.findByText("No upcoming tournaments")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not offer a retry that cannot help (403)", async () => {
    stubApi({ "/tournaments": forbidden });
    render(<UpcomingTournaments role="athlete" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("asks to sign in again when the session has expired (401)", async () => {
    stubApi({ "/tournaments": { status: 401, body: { detail: "expired" } } });
    render(<UpcomingTournaments role="athlete" />);
    expect(await screen.findByText("Sign in again to see this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("says the data is not available yet while the backend is missing, and retries", async () => {
    let mounted = false;
    const fetchMock = stubApi(routes({ "/tournaments": (url: URL) => (mounted ? listed(url) : notFound) }));
    render(<UpcomingTournaments role="athlete" />);
    expect(await screen.findByText("Tournament data is not available yet.")).toBeTruthy();
    mounted = true;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("list", { name: "Upcoming tournaments" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(8);
  });

  it("says the data is not available yet when the service cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    render(<UpcomingTournaments role="athlete" />);
    expect(await screen.findByText("Tournament data is not available yet.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("does not put server wording in the headline (500)", async () => {
    stubApi({ "/tournaments": { status: 500, body: { code: "boom", message: "Traceback" } } });
    render(<UpcomingTournaments role="athlete" />);
    expect(await screen.findByText("Could not load tournament data.")).toBeTruthy();
    expect(screen.queryByText(/Traceback/)).toBeNull();
  });
});

describe("tournament-events.calendar", () => {
  const items: CalendarEntry[] = [
    { kind: "tournament", id: "t-meet", tournament_id: "t-meet", title: "State Athletics Meet", starts_at: localAt(-1), ends_at: localAt(2), venue: "City Stadium" },
    { kind: "fixture", id: "f-1", tournament_id: "t-meet", title: "State Athletics Meet: Heat 2 (Men's 100 m)", starts_at: localAt(1, 9, 30), venue: "Track 2" },
    { kind: "tournament", id: "t-cup", tournament_id: "t-cup", title: "Founders' Cup", starts_at: localAt(9), ends_at: localAt(10) },
  ];

  it("lists the next four weeks' tournaments and fixtures in the server's order, in one request", async () => {
    const fetchMock = stubApi({ "/calendar": ok({ items }) });
    render(<TournamentCalendar role="coach" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    const rows = within(await screen.findByRole("list", { name: "Tournament calendar" })).getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(rows[0]?.textContent).toContain(`State Athletics Meet${day(isoDay(-1))} – ${day(isoDay(1))} · City Stadium`);
    expect(rows[0]?.textContent).toContain("Tournament");
    expect(rows[1]?.textContent).toContain(`State Athletics Meet: Heat 2 (Men's 100 m)${dateTime(localAt(1, 9, 30))} · Track 2`);
    expect(rows[1]?.textContent).toContain("Fixture");
    expect(rows[2]?.textContent).toContain(`Founders' Cup${day(isoDay(9))}`);
    expect(rows[2]?.textContent).not.toContain("–");
    expect(screen.getByLabelText("Calendar summary").textContent).toBe("Tournaments2Fixtures1");
    expect(urls(fetchMock)).toEqual([`${BASE}/calendar?from=${isoDay()}&to=${isoDay(DAYS - 1)}`]);
    expect(DAYS).toBeLessThanOrEqual(366);
    expect(screen.queryByText(/more$/)).toBeNull();
  });

  it("lists eight rows and says how many more", async () => {
    const many: CalendarEntry[] = Array.from({ length: CALENDAR_SHOWN + 4 }, (_, i) => ({
      kind: "fixture",
      id: `f-${i}`,
      title: `Meet: Heat ${i}`,
      starts_at: localAt(1 + i, 10),
    }));
    stubApi({ "/calendar": ok({ items: many }) });
    render(<TournamentCalendar role="coach" />);
    expect(within(await screen.findByRole("list", { name: "Tournament calendar" })).getAllByRole("listitem")).toHaveLength(CALENDAR_SHOWN);
    expect(screen.getByText("and 4 items more")).toBeTruthy();
    expect(screen.getByLabelText("Calendar summary").textContent).toBe(`Tournaments0Fixtures${CALENDAR_SHOWN + 4}`);
  });

  it("has an empty state", async () => {
    stubApi({ "/calendar": ok({ items: [] }) });
    render(<TournamentCalendar role="coach" />);
    expect(await screen.findByText("Nothing on the calendar")).toBeTruthy();
  });

  it("does not offer a retry that cannot help (403)", async () => {
    stubApi({ "/calendar": forbidden });
    render(<TournamentCalendar role="coach" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("says the data is not available yet while the backend is missing, and retries", async () => {
    let mounted = false;
    const fetchMock = stubApi({ "/calendar": () => (mounted ? ok({ items }) : notFound) });
    render(<TournamentCalendar role="coach" />);
    expect(await screen.findByText("Tournament data is not available yet.")).toBeTruthy();
    mounted = true;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("list", { name: "Tournament calendar" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it.each([502, 503])("says the data is not available yet on %i", async (status) => {
    stubApi({ "/calendar": { status, body: {} } });
    render(<TournamentCalendar role="coach" />);
    expect(await screen.findByText("Tournament data is not available yet.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
