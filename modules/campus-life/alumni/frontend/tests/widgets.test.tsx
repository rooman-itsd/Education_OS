import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { describeFailure, AlumniApiError, type MyMentoring, type MySession } from "../src/api/client";
import { routes, widgets as fromIndex } from "../src/index";
import { widgets } from "../src/widgets";
import { day, duration, indianDate, indianDateTime, role, telHref, upcoming, webUrl } from "../src/widgets/format";
import { Mentoring } from "../src/widgets/Mentoring";

function answer(status: number, body: unknown) {
  return { ok: status < 400, status, statusText: "", json: async () => body };
}

/** Stubs fetch with one response per call, in order. */
function stubFetch(...responses: ReturnType<typeof answer>[]) {
  const fetchMock = vi.fn();
  for (const r of responses) fetchMock.mockResolvedValueOnce(r);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function call(fetchMock: { mock: { calls: unknown[][] } }, n: number) {
  const [url, init] = fetchMock.mock.calls[n] as [string, RequestInit];
  return { url, headers: init.headers as Record<string, string>, signal: init.signal as AbortSignal };
}

/** The module is not mounted: the app answers FastAPI's own 404, without the contract's code. */
const UNMOUNTED = { detail: "Not Found" };

/** 3 Nov 2026, 11:30 in India. */
const NOW = new Date("2026-11-03T06:00:00Z");

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const session = (over: Partial<MySession> & Record<string, unknown> = {}): MySession => ({
  id: "s1",
  scheduled_at: "2026-11-05T11:00:00Z", // 4:30 pm on 5 Nov in India
  duration_minutes: 45,
  mode: "in_person",
  location: "Placement cell, room 204",
  topic: "Preparing for finance interviews",
  ...over,
});

const mentoring = (over: Partial<MyMentoring> = {}): MyMentoring => ({
  assignment: {
    id: "a1",
    started_on: "2026-10-01",
    focus: "Finance careers",
    mentor: {
      id: "m1",
      full_name: "Asha Menon",
      graduation_year: 2014,
      programme: "MBA Finance",
      current_company: "Acme Capital",
      current_designation: "Vice President",
      industry: "Banking",
      city: "Mumbai",
      email: "asha.menon@example.com",
      phone: "+91 98450 12345",
      linkedin_url: "https://www.linkedin.com/in/asha-menon",
    },
  },
  upcoming_sessions: [session()],
  ...over,
});

describe("widget declarations", () => {
  it("exports alumni.mentoring for the management-student layout, behind alumni:self:read", () => {
    expect(widgets).toHaveLength(1);
    const [w] = widgets;
    expect(w?.id).toBe("alumni.mentoring");
    expect(w?.title).toBe("My mentor");
    expect(w?.permission).toBe("alumni:self:read");
    expect(w?.size).toBe("1x1");
    expect(w?.kind).toBe("panel");
    expect(w?.component).toBe(Mentoring);
  });

  it("is the module's public surface, with no routes yet", () => {
    expect(fromIndex).toBe(widgets);
    expect(routes).toEqual([]);
  });
});

describe("format", () => {
  it("shows date-times in India whatever the viewer's zone", () => {
    expect(Intl.DateTimeFormat().resolvedOptions().timeZone).toBe("America/New_York");
    expect(indianDateTime("2026-11-05T11:00:00Z")).toBe("Thu, 5 Nov 2026, 4:30 pm");
    // 1:30 am on 6 Nov in India is still 5 Nov in New York.
    expect(indianDateTime("2026-11-05T20:00:00Z")).toBe("Fri, 6 Nov 2026, 1:30 am");
    expect(indianDate("2026-11-05T20:00:00Z")).toBe("2026-11-06");
    expect(indianDateTime("not a date")).toBe("—");
    expect(indianDateTime(null)).toBe("—");
    expect(indianDate("")).toBeUndefined();
  });

  it("formats calendar dates, lengths and the mentor's role", () => {
    expect(day("2026-10-01")).toBe("1 Oct 2026");
    expect(day(null)).toBe("—");
    expect(duration(45)).toBe("45 min");
    expect(duration(60)).toBe("1 h");
    expect(duration(90)).toBe("1 h 30 min");
    expect(duration(null)).toBeNull();
    expect(role("Vice President", "Acme Capital")).toBe("Vice President, Acme Capital");
    expect(role(null, "Acme Capital")).toBe("Acme Capital");
    expect(role(" ", null)).toBeNull();
  });

  it("makes only phone numbers and web addresses into links", () => {
    expect(telHref("+91 98450-12345")).toBe("tel:+919845012345");
    expect(telHref("080 2345 6789")).toBe("tel:08023456789");
    expect(telHref("call the office")).toBeNull();
    expect(webUrl("https://meet.example.com/abc")).toBe("https://meet.example.com/abc");
    expect(webUrl("javascript:alert(1)")).toBeNull();
    expect(webUrl("Room 204")).toBeNull();
  });

  it("keeps the next five scheduled sessions at or after now, soonest first", () => {
    const list = [
      session({ id: "later", scheduled_at: "2026-11-20T05:00:00Z" }),
      session({ id: "past", scheduled_at: "2026-11-03T05:59:59Z" }),
      session({ id: "now", scheduled_at: "2026-11-03T06:00:00Z" }),
      session({ id: "cancelled", scheduled_at: "2026-11-04T05:00:00Z", status: "cancelled" }),
      session({ id: "scheduled", scheduled_at: "2026-11-04T06:00:00Z", status: "scheduled" }),
      session({ id: "d1", scheduled_at: "2026-11-10T05:00:00Z" }),
      session({ id: "d2", scheduled_at: "2026-11-11T05:00:00Z" }),
      session({ id: "d3", scheduled_at: "2026-11-12T05:00:00Z" }),
      session({ id: "broken", scheduled_at: "soon" }),
    ];
    expect(upcoming(list, NOW).map((s) => s.id)).toEqual(["now", "scheduled", "d1", "d2", "d3"]);
    expect(upcoming(undefined, NOW)).toEqual([]);
  });
});

describe("api client", () => {
  it("maps every failure to the widget's words and says when retrying can help", () => {
    const words = (e: unknown) => describeFailure(e);
    expect(words(new AlumniApiError(0, "x"))).toEqual({ message: "Alumni data is not available yet.", retry: true });
    expect(words(new AlumniApiError(404, "x"))).toEqual({ message: "Alumni data is not available yet.", retry: true });
    expect(words(new AlumniApiError(502, "x"))).toEqual({ message: "Alumni data is not available yet.", retry: true });
    expect(words(new AlumniApiError(503, "x"))).toEqual({ message: "Alumni data is not available yet.", retry: true });
    expect(words(new AlumniApiError(401, "x"))).toEqual({ message: "Sign in again to see this.", retry: false });
    expect(words(new AlumniApiError(403, "x"))).toEqual({ message: "You do not have access to this.", retry: false });
    expect(words(new AlumniApiError(500, "Database down"))).toEqual({ message: "Could not load alumni data.", retry: true });
    expect(words(new Error("boom"))).toEqual({ message: "Could not load alumni data.", retry: true });
  });
});

describe("alumni.mentoring", () => {
  it("fetches GET /api/v1/alumni/me/mentoring with the session token", async () => {
    const fetchMock = stubFetch(answer(200, mentoring()));
    render(<Mentoring role="management-student" />);
    expect(screen.getByLabelText("Loading").getAttribute("aria-busy")).toBe("true");
    expect(await screen.findByText("Asha Menon")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const { url, headers, signal } = call(fetchMock, 0);
    expect(url).toBe("/api/v1/alumni/me/mentoring");
    expect(headers.Authorization).toBe("Bearer test-token");
    expect(signal).toBeInstanceOf(AbortSignal);
  });

  it("sends no Authorization header without a session token", async () => {
    localStorage.clear();
    const fetchMock = stubFetch(answer(200, mentoring()));
    render(<Mentoring role="management-student" />);
    await screen.findByText("Asha Menon");
    expect(call(fetchMock, 0).headers).toEqual({});
  });

  it("shows the mentor: name, role and company, background, focus and start date", async () => {
    stubFetch(answer(200, mentoring()));
    render(<Mentoring role="management-student" />);
    const mentor = await screen.findByRole("region", { name: "Your mentor" });
    expect(within(mentor).getByRole("heading", { name: "Asha Menon" })).toBeTruthy();
    expect(within(mentor).getByText("Vice President, Acme Capital")).toBeTruthy();
    expect(within(mentor).getByText("Class of 2014 · MBA Finance · Banking · Mumbai")).toBeTruthy();
    expect(within(mentor).getByText("Focus").nextElementSibling?.textContent).toBe("Finance careers");
    expect(within(mentor).getByText("Mentoring since").nextElementSibling?.textContent).toBe("1 Oct 2026");
  });

  it("gives the mentor's contact details as accessible links", async () => {
    stubFetch(answer(200, mentoring()));
    render(<Mentoring role="management-student" />);
    const email = await screen.findByRole("link", { name: "asha.menon@example.com" });
    expect(email.getAttribute("href")).toBe("mailto:asha.menon@example.com");
    const phone = screen.getByRole("link", { name: "+91 98450 12345" });
    expect(phone.getAttribute("href")).toBe("tel:+919845012345");
    const linkedin = screen.getByRole("link", { name: "LinkedIn profile (opens in a new tab)" });
    expect(linkedin.getAttribute("href")).toBe("https://www.linkedin.com/in/asha-menon");
    expect(linkedin.getAttribute("target")).toBe("_blank");
    expect(linkedin.getAttribute("rel")).toBe("noopener noreferrer");
    // The contact list is named, and the icons are hidden from screen readers.
    const contacts = screen.getByLabelText("Contact Asha Menon");
    expect(contacts.tagName).toBe("DL");
    for (const svg of contacts.querySelectorAll("svg")) expect(svg.getAttribute("aria-hidden")).toBe("true");
  });

  it("shows only the details the contract gives, and never a non-web LinkedIn value as a link", async () => {
    stubFetch(
      answer(
        200,
        mentoring({
          assignment: {
            id: "a1",
            started_on: "2026-10-01",
            focus: null,
            mentor: { id: "m1", full_name: "Ravi Kumar", graduation_year: 2010, email: null, phone: null, linkedin_url: "javascript:alert(1)" },
          },
        }),
      ),
    );
    render(<Mentoring role="management-student" />);
    const mentor = await screen.findByRole("region", { name: "Your mentor" });
    expect(within(mentor).getByText("Class of 2010")).toBeTruthy();
    expect(within(mentor).queryByText("Focus")).toBeNull();
    expect(screen.queryByLabelText("Contact Ravi Kumar")).toBeNull();
    expect(screen.queryAllByRole("link")).toHaveLength(0);
  });

  it("lists upcoming sessions with date and time in India, topic, mode, place and length", async () => {
    stubFetch(
      answer(
        200,
        mentoring({
          upcoming_sessions: [
            session(),
            session({ id: "s2", scheduled_at: "2026-11-05T20:00:00Z", mode: "online", location: "https://meet.example.com/xyz", topic: null, duration_minutes: 90 }),
            session({ id: "s3", scheduled_at: "2026-11-09T04:30:00Z", mode: "phone", location: null, topic: "CV review", duration_minutes: null }),
          ],
        }),
      ),
    );
    render(<Mentoring role="management-student" />);
    const region = await screen.findByRole("region", { name: "Upcoming sessions" });
    expect(within(region).getByRole("heading", { name: "Upcoming sessions" })).toBeTruthy();
    const rows = within(within(region).getByRole("list", { name: "Upcoming mentoring sessions" })).getAllByRole("listitem");
    expect(rows).toHaveLength(3);

    expect(within(rows[0]!).getByText("Thu, 5 Nov 2026, 4:30 pm").getAttribute("dateTime")).toBe("2026-11-05T11:00:00Z");
    expect(within(rows[0]!).getByText("Preparing for finance interviews")).toBeTruthy();
    expect(within(rows[0]!).getByText("In person · Placement cell, room 204")).toBeTruthy();
    expect(within(rows[0]!).getByText("45 min")).toBeTruthy();

    // 20:00 UTC on 5 Nov is 1:30 am on 6 Nov in India: the time and the date tile both say 6 Nov.
    expect(within(rows[1]!).getByText("Fri, 6 Nov 2026, 1:30 am")).toBeTruthy();
    expect(rows[1]!.querySelector(".eos-row__date b")?.textContent).toBe("06");
    const link = within(rows[1]!).getByRole("link", { name: "Meeting link (opens in a new tab)" });
    expect(link.getAttribute("href")).toBe("https://meet.example.com/xyz");
    expect(within(rows[1]!).getByText("1 h 30 min")).toBeTruthy();

    expect(within(rows[2]!).getByText("Mon, 9 Nov 2026, 10:00 am")).toBeTruthy();
    expect(within(rows[2]!).getByText("CV review")).toBeTruthy();
    expect(within(rows[2]!).getByText("Phone")).toBeTruthy();
  });

  it("shows only scheduled sessions still to come, at most five, soonest first", async () => {
    const future = Array.from({ length: 7 }, (_, i) => session({ id: `f${i}`, scheduled_at: `2026-11-${String(20 - i).padStart(2, "0")}T05:00:00Z`, topic: `Topic ${20 - i}` }));
    stubFetch(
      answer(
        200,
        mentoring({
          upcoming_sessions: [
            session({ id: "past", scheduled_at: "2026-11-02T05:00:00Z", topic: "Already happened" }),
            session({ id: "cancelled", scheduled_at: "2026-11-04T05:00:00Z", topic: "Called off", status: "cancelled" } as Partial<MySession>),
            ...future,
          ],
        }),
      ),
    );
    render(<Mentoring role="management-student" />);
    const list = await screen.findByRole("list", { name: "Upcoming mentoring sessions" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(5);
    expect(rows.map((r) => within(r).getByText(/^Topic /).textContent)).toEqual(["Topic 14", "Topic 15", "Topic 16", "Topic 17", "Topic 18"]);
    expect(screen.queryByText("Already happened")).toBeNull();
    expect(screen.queryByText("Called off")).toBeNull();
  });

  it("says so when the mentor has no session scheduled", async () => {
    stubFetch(answer(200, mentoring({ upcoming_sessions: [] })));
    render(<Mentoring role="management-student" />);
    const region = await screen.findByRole("region", { name: "Upcoming sessions" });
    expect(within(region).getByText("No sessions scheduled.")).toBeTruthy();
    expect(within(region).queryByRole("list")).toBeNull();
  });

  it("never shows staff notes, even if a response carries them", async () => {
    const withNotes = mentoring({ upcoming_sessions: [session({ notes: "Staff note on the session", cancel_reason: "Internal reason" } as Partial<MySession>)] });
    (withNotes.assignment!.mentor as unknown as Record<string, unknown>).notes = "Staff note on the alumnus";
    (withNotes.assignment as unknown as Record<string, unknown>).end_reason = "Staff end reason";
    stubFetch(answer(200, withNotes));
    const { container } = render(<Mentoring role="management-student" />);
    await screen.findByText("Asha Menon");
    expect(container.textContent).not.toMatch(/Staff note|Internal reason|Staff end reason/);
  });

  it("shows the empty state when the student has no active mentor (assignment is null)", async () => {
    stubFetch(answer(200, { assignment: null, upcoming_sessions: [] }));
    render(<Mentoring role="management-student" />);
    expect(await screen.findByText("No mentor assigned yet")).toBeTruthy();
    expect(screen.getByText("Your alumni mentor and upcoming sessions appear here once one is assigned.")).toBeTruthy();
    expect(screen.queryByRole("region")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it.each([
    ["the module is not mounted (404)", answer(404, UNMOUNTED)],
    ["the gateway fails (502)", answer(502, {})],
    ["the service is unavailable (503)", answer(503, {})],
  ])("says the data is not available yet when %s, and retries", async (_case, failure) => {
    const fetchMock = stubFetch(failure, answer(200, mentoring()));
    render(<Mentoring role="management-student" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Alumni data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Asha Menon")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("says the data is not available yet when the service cannot be reached, and retries", async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValueOnce(answer(200, mentoring()));
    vi.stubGlobal("fetch", fetchMock);
    render(<Mentoring role="management-student" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Alumni data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Asha Menon")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shows a generic error, never the server's message, and retries", async () => {
    const fetchMock = stubFetch(answer(500, { detail: { code: "internal", message: "Database unavailable" } }), answer(200, { assignment: null, upcoming_sessions: [] }));
    render(<Mentoring role="management-student" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Could not load alumni data.");
    expect(alert.textContent).not.toContain("Database unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No mentor assigned yet")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("offers no retry when the viewer lacks the permission (403)", async () => {
    stubFetch(answer(403, { detail: { code: "forbidden", message: "Missing alumni:self:read" } }));
    render(<Mentoring role="management-student" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("You do not have access to this.");
    expect(alert.textContent).not.toContain("Missing alumni:self:read");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("asks the viewer to sign in again when the session has expired (401), without a retry", async () => {
    stubFetch(answer(401, { detail: "Not authenticated" }));
    render(<Mentoring role="management-student" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("cancels the request when the widget unmounts before the answer", async () => {
    const fetchMock = vi.fn((_url: string, _init?: RequestInit) => new Promise<never>(() => {}));
    vi.stubGlobal("fetch", fetchMock);
    const { unmount } = render(<Mentoring role="management-student" />);
    const { signal } = call(fetchMock, 0);
    expect(signal.aborted).toBe(false);
    unmount();
    expect(signal.aborted).toBe(true);
  });

  it("cancels a retry's request too when the widget unmounts", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(answer(503, {}))
      .mockImplementationOnce(() => new Promise<never>(() => {}));
    vi.stubGlobal("fetch", fetchMock);
    const { unmount } = render(<Mentoring role="management-student" />);
    fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const first = call(fetchMock, 0).signal;
    const second = call(fetchMock, 1).signal;
    expect(first.aborted).toBe(true); // the finished attempt's effect was cleaned up when the retry started
    expect(second.aborted).toBe(false);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    unmount();
    expect(second.aborted).toBe(true);
  });

  it("ignores an answer that arrives after the widget unmounted", async () => {
    let resolve: (v: unknown) => void = () => {};
    const fetchMock = vi.fn((_url: string, _init?: RequestInit) => new Promise((r) => (resolve = r)));
    vi.stubGlobal("fetch", fetchMock);
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});
    const { unmount } = render(<Mentoring role="management-student" />);
    unmount();
    await act(async () => resolve(answer(200, mentoring())));
    expect(errors).not.toHaveBeenCalled();
    errors.mockRestore();
  });
});
