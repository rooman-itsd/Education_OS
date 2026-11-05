import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { WidgetProps } from "@eos/ui-kit";
import type { CountsByApplicationStatus, DrivesUpcomingReport, MyOpening, MyOpeningPage, OpeningsSummaryReport, UpcomingDrive } from "../src/api/client";
import { widgets } from "../src/widgets";
import { Drives } from "../src/widgets/Drives";
import { day, rupees } from "../src/widgets/format";
import { Openings } from "../src/widgets/Openings";
import { OpeningsSummary } from "../src/widgets/OpeningsSummary";

const URL_OPENINGS = "/api/v1/placement-career/me/openings?limit=5";
const URL_SUMMARY = "/api/v1/placement-career/reports/openings-summary?limit=5";
const URL_DRIVES = "/api/v1/placement-career/reports/drives-upcoming?limit=5";

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

function lastCall(fetchMock: { mock: { calls: unknown[][] } }) {
  const [url, init] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1] as unknown as [string, RequestInit];
  return { url, headers: init.headers as Record<string, string>, signal: init.signal as AbortSignal };
}

/** The summary figure with this label: its <div> holding the dt and dd. */
function figure(label: string): HTMLElement {
  return screen.getByText(label, { selector: "dt" }).parentElement as HTMLElement;
}

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("widget declarations", () => {
  const expected: [string, string, string, string, string, ComponentType<WidgetProps>][] = [
    ["placement-career.openings", "Job openings", "placement-career:self:read", "2x1", "panel", Openings],
    ["placement-career.openings-summary", "Placement openings", "placement-career:report:read", "2x1", "panel", OpeningsSummary],
    ["placement-career.drives", "Upcoming drives", "placement-career:report:read", "1x1", "panel", Drives],
  ];

  it("exports the three widgets the role layouts name", () => {
    expect(widgets.map((w) => w.id)).toEqual(expected.map((e) => e[0]));
  });

  it.each(expected)("registers %s titled %s with permission %s, size %s, kind %s and its component", (id, title, permission, size, kind, component) => {
    const w = widgets.find((x) => x.id === id);
    expect(w).toBeTruthy();
    expect(w?.title).toBe(title);
    expect(w?.permission).toBe(permission);
    expect(w?.size).toBe(size);
    expect(w?.kind).toBe(kind);
    expect(w?.component).toBe(component);
  });
});

/** Every widget shares the client and the status handling; each one is checked against them. */
const cases: [string, ComponentType<WidgetProps>, string, () => unknown, string][] = [
  ["placement-career.openings", Openings, URL_OPENINGS, () => openingsPage(), "Software Engineer"],
  ["placement-career.openings-summary", OpeningsSummary, URL_SUMMARY, () => summary(), "Graduate Trainee"],
  ["placement-career.drives", Drives, URL_DRIVES, () => drivesReport(), "Infosys campus drive"],
];

describe.each(cases)("%s: request and failures", (_id, Widget, url, data, shown) => {
  it("shows a loading skeleton, then calls its endpoint with the session token", async () => {
    const fetchMock = stubFetch(answer(200, data()));
    render(<Widget role="test" />);
    expect(screen.getByLabelText("Loading").getAttribute("aria-busy")).toBe("true");
    expect(await screen.findByText(shown)).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const { url: called, headers } = lastCall(fetchMock);
    expect(called).toBe(url);
    expect(headers.Authorization).toBe("Bearer test-token");
  });

  it("sends no Authorization header without a session token", async () => {
    localStorage.clear();
    const fetchMock = stubFetch(answer(200, data()));
    render(<Widget role="test" />);
    expect(await screen.findByText(shown)).toBeTruthy();
    expect(lastCall(fetchMock).headers.Authorization).toBeUndefined();
  });

  it("shows a generic error, never the server's message, and retries", async () => {
    const fetchMock = stubFetch(answer(500, { detail: { code: "internal", message: "Database unavailable" } }), answer(200, data()));
    render(<Widget role="test" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Could not load placement data.");
    expect(alert.textContent).not.toContain("Database unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(shown)).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(lastCall(fetchMock).url).toBe(url);
  });

  it("says the data is not available yet when the service cannot be reached, and retries", async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValueOnce(answer(200, data()));
    vi.stubGlobal("fetch", fetchMock);
    render(<Widget role="test" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Placement data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(shown)).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it.each([404, 502, 503])("says the data is not available yet on %i, with a retry", async (status) => {
    stubFetch(answer(status, { detail: "Not Found" }));
    render(<Widget role="test" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Placement data is not available yet.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("asks the user to sign in again, without a retry, on 401", async () => {
    stubFetch(answer(401, { detail: { code: "unauthenticated", message: "Not authenticated" } }));
    render(<Widget role="test" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("says the viewer has no access, without a retry and without the permission key, on 403", async () => {
    stubFetch(answer(403, { detail: { code: "forbidden", message: "Missing permission placement-career:report:read" } }));
    render(<Widget role="test" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("You do not have access to this.");
    expect(alert.textContent).not.toContain("placement-career:");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("aborts its request when it unmounts first", async () => {
    const fetchMock = vi.fn(() => new Promise(() => {}));
    vi.stubGlobal("fetch", fetchMock);
    const { unmount } = render(<Widget role="test" />);
    const { signal } = lastCall(fetchMock);
    expect(signal.aborted).toBe(false);
    unmount();
    expect(signal.aborted).toBe(true);
  });

  it("aborts the retried request too when it unmounts while retrying", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(answer(503, {})).mockImplementationOnce(() => new Promise(() => {}));
    vi.stubGlobal("fetch", fetchMock);
    const { unmount } = render(<Widget role="test" />);
    fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const { signal } = lastCall(fetchMock);
    expect(signal.aborted).toBe(false);
    unmount();
    expect(signal.aborted).toBe(true);
  });

  it("does not show an answer that arrives after it unmounted", async () => {
    let resolve: (v: unknown) => void = () => {};
    vi.stubGlobal("fetch", vi.fn(() => new Promise((r) => (resolve = r))));
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});
    const { unmount } = render(<Widget role="test" />);
    unmount();
    resolve(answer(200, data()));
    await new Promise((r) => setTimeout(r, 0));
    expect(errors).not.toHaveBeenCalled();
    errors.mockRestore();
  });
});

// ---------------------------------------------------------------------------------------------------------------------
// placement-career.openings

const company = (name: string) => ({ id: `c-${name}`, name, industry: "IT services", website: null });

const opening = (over: Partial<MyOpening>): MyOpening => ({
  id: "o0",
  title: "Opening",
  company: company("Acme"),
  drive: null,
  location: null,
  ctc_per_annum: null,
  applications_close_on: "2026-11-10",
  eligibility: {},
  my_application: null,
  ...over,
});

const openingsPage = (over: Partial<MyOpeningPage> = {}): MyOpeningPage => ({
  items: [
    opening({
      id: "o1",
      title: "Software Engineer",
      company: company("Infosys"),
      location: "Bengaluru",
      ctc_per_annum: "650000",
      applications_close_on: "2026-11-05",
      drive: { id: "d1", title: "Infosys campus drive", scheduled_on: "2026-11-12", venue: "Main auditorium" },
    }),
    opening({ id: "o2", title: "Management Trainee", company: company("Tata Steel"), ctc_per_annum: "850000.50", applications_close_on: "2026-11-08", my_application: { id: "a2", status: "shortlisted" } }),
    opening({ id: "o3", title: "Analyst", company: company("Deloitte"), applications_close_on: "2026-11-20", my_application: { id: "a3", status: "offered" } }),
  ],
  next_cursor: null,
  ...over,
});

describe("placement-career.openings", () => {
  it("lists the openings in the API's order with company, place, CTC, drive date and last day to apply", async () => {
    stubFetch(answer(200, openingsPage()));
    render(<Openings role="engineering-student" />);
    const list = await screen.findByRole("list", { name: "Job openings" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows.map((r) => r.querySelector(".eos-row__title")?.textContent)).toEqual(["Software Engineer", "Management Trainee", "Analyst"]);
    expect(within(rows[0]!).getByText("Infosys, Bengaluru")).toBeTruthy();
    expect(within(rows[0]!).getByText("CTC ₹6,50,000 a year")).toBeTruthy();
    expect(within(rows[0]!).getByText("Campus drive on 12 Nov 2026")).toBeTruthy();
    expect(within(rows[0]!).getByText("Apply by 5 Nov 2026")).toBeTruthy();
    expect(within(rows[1]!).getByText("Tata Steel")).toBeTruthy();
    expect(within(rows[1]!).getByText("CTC ₹8,50,000.50 a year")).toBeTruthy();
    expect(within(rows[1]!).queryByText(/^Campus drive/)).toBeNull();
    // No CTC given: no CTC line.
    expect(within(rows[2]!).queryByText(/^CTC/)).toBeNull();
    expect(within(rows[2]!).getByText("Apply by 20 Nov 2026")).toBeTruthy();
  });

  it("is a section labelled for screen readers, not a labelled paragraph", async () => {
    stubFetch(answer(200, openingsPage()));
    render(<Openings role="engineering-student" />);
    const region = await screen.findByRole("region", { name: "Openings closing soonest" });
    expect(region.tagName).toBe("SECTION");
    expect(document.querySelector("p[aria-label]")).toBeNull();
  });

  it("shows the student's own application status, and nothing on openings they have not applied to", async () => {
    stubFetch(answer(200, openingsPage()));
    render(<Openings role="engineering-student" />);
    const rows = within(await screen.findByRole("list", { name: "Job openings" })).getAllByRole("listitem");
    expect(rows[0]!.querySelector(".eos-badge")).toBeNull();
    expect(within(rows[1]!).getByText("Shortlisted").className).toContain("eos-badge--info");
    expect(within(rows[2]!).getByText("Offer made").className).toContain("eos-badge--success");
  });

  it("says more openings are open when the page has a next cursor", async () => {
    stubFetch(answer(200, openingsPage({ next_cursor: "c-next" })));
    render(<Openings role="engineering-student" />);
    expect(await screen.findByText("Showing the 3 closing soonest; more are open.")).toBeTruthy();
  });

  it("says nothing more when the page is the last one", async () => {
    stubFetch(answer(200, openingsPage()));
    render(<Openings role="engineering-student" />);
    expect(await screen.findByText("Software Engineer")).toBeTruthy();
    expect(screen.queryByText(/more are open/)).toBeNull();
  });

  it("shows an empty state when no opening takes applications", async () => {
    stubFetch(answer(200, { items: [], next_cursor: null }));
    render(<Openings role="engineering-student" />);
    expect(await screen.findByText("No openings right now")).toBeTruthy();
    expect(screen.getByText("Job openings you can apply to appear here.")).toBeTruthy();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("shows the empty state for a page without items instead of failing", async () => {
    stubFetch(answer(200, { next_cursor: null }));
    render(<Openings role="engineering-student" />);
    expect(await screen.findByText("No openings right now")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

// ---------------------------------------------------------------------------------------------------------------------
// placement-career.openings-summary

const counts = (over: Partial<CountsByApplicationStatus> = {}): CountsByApplicationStatus => ({
  applied: 0,
  shortlisted: 0,
  in_process: 0,
  offered: 0,
  accepted: 0,
  declined: 0,
  rejected: 0,
  withdrawn: 0,
  ...over,
});

const summary = (over: Partial<OpeningsSummaryReport> = {}): OpeningsSummaryReport => ({
  openings: { draft: 2, open: 7, closed: 4 },
  applications: counts({ applied: 30, shortlisted: 10, in_process: 5, offered: 3, accepted: 8, rejected: 6, withdrawn: 1 }),
  students_placed: 8,
  closing_soon: [
    { id: "o1", title: "Graduate Trainee", company_name: "Wipro", applications_close_on: "2026-11-04", applications_count: 12 },
    { id: "o2", title: "Sales Associate", company_name: "HDFC Bank", applications_close_on: "2026-11-09", applications_count: 1 },
  ],
  ...over,
});

const noSummary = (): OpeningsSummaryReport => ({ openings: { draft: 0, open: 0, closed: 0 }, applications: counts(), students_placed: 0, closing_soon: [] });

describe("placement-career.openings-summary", () => {
  it("shows open openings, all applications and students placed", async () => {
    stubFetch(answer(200, summary()));
    render(<OpeningsSummary role="placement-officer" />);
    expect(await screen.findByText("Open openings")).toBeTruthy();
    expect(figure("Open openings").textContent).toBe("Open openings7");
    expect(figure("Applications").textContent).toBe("Applications63");
    expect(figure("Students placed").textContent).toBe("Students placed8");
  });

  it("mentions offers awaiting an answer and unpublished drafts", async () => {
    stubFetch(answer(200, summary()));
    render(<OpeningsSummary role="placement-officer" />);
    expect(await screen.findByText("3 offers awaiting an answer · 2 draft openings not published")).toBeTruthy();
  });

  it("says one offer and one draft in the singular, and leaves out what is zero", async () => {
    stubFetch(answer(200, summary({ openings: { draft: 1, open: 2, closed: 0 }, applications: counts({ offered: 1 }) })));
    const { unmount } = render(<OpeningsSummary role="placement-officer" />);
    expect(await screen.findByText("1 offer awaiting an answer · 1 draft opening not published")).toBeTruthy();
    unmount();
    stubFetch(answer(200, summary({ openings: { draft: 0, open: 2, closed: 0 }, applications: counts({ applied: 4 }) })));
    render(<OpeningsSummary role="placement-officer" />);
    expect(await screen.findByText("Graduate Trainee")).toBeTruthy();
    expect(screen.queryByText(/awaiting an answer|not published/)).toBeNull();
  });

  it("lists the openings closing soonest with company, closing date and applications", async () => {
    stubFetch(answer(200, summary()));
    render(<OpeningsSummary role="industry-liaison" />);
    const region = await screen.findByRole("region", { name: "Openings closing soonest" });
    const rows = within(within(region).getByRole("list", { name: "Openings closing soonest" })).getAllByRole("listitem");
    expect(rows.map((r) => r.querySelector(".eos-row__title")?.textContent)).toEqual(["Graduate Trainee", "Sales Associate"]);
    expect(within(rows[0]!).getByText("Wipro")).toBeTruthy();
    expect(within(rows[0]!).getByText("Closes 4 Nov 2026")).toBeTruthy();
    expect(within(rows[0]!).getByText("12 applications")).toBeTruthy();
    expect(within(rows[1]!).getByText("1 application")).toBeTruthy();
  });

  it("says how many more openings are open than it lists", async () => {
    stubFetch(answer(200, summary()));
    render(<OpeningsSummary role="placement-officer" />);
    expect(await screen.findByText("5 more open openings")).toBeTruthy();
  });

  it("says one more in the singular, and nothing when every open opening is listed", async () => {
    stubFetch(answer(200, summary({ openings: { draft: 0, open: 3, closed: 0 } })));
    const { unmount } = render(<OpeningsSummary role="placement-officer" />);
    expect(await screen.findByText("1 more open opening")).toBeTruthy();
    unmount();
    stubFetch(answer(200, summary({ openings: { draft: 0, open: 2, closed: 0 } })));
    render(<OpeningsSummary role="placement-officer" />);
    expect(await screen.findByText("Graduate Trainee")).toBeTruthy();
    expect(screen.queryByText(/more open opening/)).toBeNull();
  });

  it("shows the figures without a list when nothing is open", async () => {
    stubFetch(answer(200, summary({ openings: { draft: 0, open: 0, closed: 5 }, closing_soon: [] })));
    render(<OpeningsSummary role="placement-officer" />);
    expect(await screen.findByText("Open openings")).toBeTruthy();
    expect(figure("Open openings").textContent).toBe("Open openings0");
    expect(screen.queryByRole("list")).toBeNull();
    expect(screen.queryByText("No openings yet")).toBeNull();
  });

  it("shows an empty state for an organisation without openings or applications", async () => {
    stubFetch(answer(200, noSummary()));
    render(<OpeningsSummary role="placement-officer" />);
    expect(await screen.findByText("No openings yet")).toBeTruthy();
    expect(screen.getByText("Job openings and applications appear here once openings are posted.")).toBeTruthy();
    expect(screen.queryByText("Open openings")).toBeNull();
  });
});

// ---------------------------------------------------------------------------------------------------------------------
// placement-career.drives

const drive = (over: Partial<UpcomingDrive>): UpcomingDrive => ({
  id: "d0",
  title: "Drive",
  company: company("Acme"),
  scheduled_on: "2026-11-12",
  venue: null,
  registration_closes_on: null,
  openings_count: 1,
  applications: counts(),
  ...over,
});

const drivesReport = (over: Partial<DrivesUpcomingReport> = {}): DrivesUpcomingReport => ({
  next_30_days: 9,
  drives: [
    drive({ id: "d1", title: "Infosys campus drive", company: company("Infosys"), venue: "Main auditorium", scheduled_on: "2026-11-06", registration_closes_on: "2026-11-04", openings_count: 3, applications: counts({ applied: 20, shortlisted: 4 }) }),
    drive({ id: "d2", title: "TCS ninja hiring", company: company("TCS"), scheduled_on: "2026-11-15", openings_count: 1, applications: counts({ applied: 1 }) }),
  ],
  ...over,
});

describe("placement-career.drives", () => {
  it("shows how many drives are scheduled in the next 30 days", async () => {
    stubFetch(answer(200, drivesReport()));
    render(<Drives role="placement-officer" />);
    expect(await screen.findByText("Next 30 days")).toBeTruthy();
    expect(figure("Next 30 days").textContent).toBe("Next 30 days9");
  });

  it("lists the drives soonest first with company, venue, date, registration closing, openings and applications", async () => {
    stubFetch(answer(200, drivesReport()));
    render(<Drives role="placement-officer" />);
    const region = await screen.findByRole("region", { name: "Drives coming up" });
    const rows = within(within(region).getByRole("list", { name: "Upcoming drives" })).getAllByRole("listitem");
    expect(rows.map((r) => r.querySelector(".eos-row__title")?.textContent)).toEqual(["Infosys campus drive", "TCS ninja hiring"]);
    expect(within(rows[0]!).getByText("Infosys, Main auditorium")).toBeTruthy();
    expect(within(rows[0]!).getByText("6 Nov 2026")).toBeTruthy();
    expect(within(rows[0]!).getByText("Registration closes 4 Nov 2026")).toBeTruthy();
    expect(within(rows[0]!).getByText("3 openings")).toBeTruthy();
    expect(within(rows[0]!).getByText("24 applications")).toBeTruthy();
    expect(within(rows[1]!).getByText("TCS")).toBeTruthy();
    expect(within(rows[1]!).queryByText(/^Registration closes/)).toBeNull();
    expect(within(rows[1]!).getByText("1 opening")).toBeTruthy();
    expect(within(rows[1]!).getByText("1 application")).toBeTruthy();
  });

  it("puts the drive's date in the row's date tile", async () => {
    stubFetch(answer(200, drivesReport()));
    render(<Drives role="placement-officer" />);
    const rows = within(await screen.findByRole("list", { name: "Upcoming drives" })).getAllByRole("listitem");
    expect(rows[0]!.querySelector(".eos-row__date b")?.textContent).toBe("06");
    expect(rows[1]!.querySelector(".eos-row__date b")?.textContent).toBe("15");
  });

  it("says how many more drives fall in the next 30 days than it lists", async () => {
    stubFetch(answer(200, drivesReport()));
    render(<Drives role="placement-officer" />);
    expect(await screen.findByText("7 more drives in the next 30 days")).toBeTruthy();
  });

  it("says one more in the singular, and nothing when every drive of the next 30 days is listed", async () => {
    stubFetch(answer(200, drivesReport({ next_30_days: 3 })));
    const { unmount } = render(<Drives role="placement-officer" />);
    expect(await screen.findByText("1 more drive in the next 30 days")).toBeTruthy();
    unmount();
    stubFetch(answer(200, drivesReport({ next_30_days: 1 })));
    render(<Drives role="placement-officer" />);
    expect(await screen.findByText("Infosys campus drive")).toBeTruthy();
    expect(screen.queryByText(/more drive/)).toBeNull();
  });

  it("shows an empty state when no drive is scheduled", async () => {
    stubFetch(answer(200, { next_30_days: 0, drives: [] }));
    render(<Drives role="placement-officer" />);
    expect(await screen.findByText("No drives scheduled")).toBeTruthy();
    expect(screen.getByText("Scheduled campus drives appear here.")).toBeTruthy();
    expect(screen.queryByText("Next 30 days")).toBeNull();
  });
});

// ---------------------------------------------------------------------------------------------------------------------

describe("formatting", () => {
  it("runs in a time zone far from India, so the date checks mean something", () => {
    expect(new Date("2026-11-05T00:00:00+05:30").getDate()).toBe(4);
  });

  it("reads a contract date as an Indian calendar date in Asia/Kolkata, whatever the viewer's zone", () => {
    expect(day("2026-11-05")).toBe("5 Nov 2026");
    expect(day("2026-01-01")).toBe("1 Jan 2026");
    expect(day(null)).toBe("—");
    expect(day(undefined)).toBe("—");
    expect(day("not a date")).toBe("not a date");
  });

  it("shows rupees with Indian digit grouping", () => {
    expect(rupees("650000")).toBe("₹6,50,000");
    expect(rupees("1200000.5")).toBe("₹12,00,000.50");
    expect(rupees("850000.50")).toBe("₹8,50,000.50");
    expect(rupees("650000.00")).toBe("₹6,50,000");
    expect(rupees(null)).toBeNull();
    expect(rupees("")).toBeNull();
    expect(rupees("abc")).toBeNull();
  });
});
