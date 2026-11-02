import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { WidgetProps } from "@eos/ui-kit";
import type { FileSummary, Inbox } from "../src/api/client";
import { widgets } from "../src/widgets";
import { FilesPending } from "../src/widgets/FilesPending";
import { day, indianDay } from "../src/widgets/format";

const URL_INBOX = "/api/v1/e-office/me/inbox?limit=5";

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

function lastCall(fetchMock: ReturnType<typeof vi.fn>) {
  const [url, init] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1] as [string, RequestInit];
  return { url, headers: init.headers as Record<string, string> };
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
  const expected: [string, string, string, string, ComponentType<WidgetProps>][] = [
    ["e-office.files-pending", "e-office:file:use", "2x1", "panel", FilesPending],
  ];

  it("exports the widget the HR Staff layout names", () => {
    expect(widgets.map((w) => w.id)).toEqual(expected.map((e) => e[0]));
  });

  it.each(expected)("registers %s with permission %s, size %s, kind %s and its component", (id, permission, size, kind, component) => {
    const w = widgets.find((x) => x.id === id);
    expect(w).toBeTruthy();
    expect(w?.permission).toBe(permission);
    expect(w?.size).toBe(size);
    expect(w?.kind).toBe(kind);
    expect(w?.component).toBe(component);
    expect(w?.title).toBe("Files pending with me");
  });
});

const me = { user_id: "u-me", name: "", designation: null };

const file = (over: Partial<FileSummary>): FileSummary => ({
  id: "f0",
  organisation_id: "org-1",
  number: "ADM/2026/0001",
  subject: "Subject",
  category_id: "c1",
  department_id: null,
  priority: "normal",
  confidential: false,
  status: "open",
  holder: me,
  held_since: "2026-10-20T05:30:00Z",
  action_required: null,
  due_on: null,
  overdue: false,
  ...over,
});

const inbox = (over: Partial<Inbox> = {}): Inbox => ({
  total: 12,
  overdue: 2,
  urgent: 3,
  oldest_held_since: "2026-10-01T04:00:00Z",
  items: [
    file({ id: "f1", number: "EST/2026/0007", subject: "Appointment of guest faculty, Commerce", priority: "urgent", action_required: "for approval", due_on: "2026-10-25", overdue: true }),
    file({ id: "f2", number: "ADM/2026/0012", subject: "Annual maintenance contract for lifts", action_required: "for comments", due_on: "2026-11-05" }),
    // Received at 20:00 UTC on 27 Oct: 28 Oct in India.
    file({ id: "f3", number: "HR/2026/0031", subject: "Leave encashment policy revision", priority: "immediate", held_since: "2026-10-27T20:00:00Z" }),
    file({ id: "f4", number: "ACC/2026/0004", subject: "Audit observations 2025-26", overdue: true }),
  ],
  unattached_receipts: 0,
  next_cursor: "c-next",
  ...over,
});

const nothing = (over: Partial<Inbox> = {}): Inbox =>
  inbox({ total: 0, overdue: 0, urgent: 0, oldest_held_since: null, items: [], unattached_receipts: 0, next_cursor: null, ...over });

describe("e-office.files-pending", () => {
  it("shows the counts from GET /me/inbox, asking for the five files waiting longest", async () => {
    const fetchMock = stubFetch(answer(200, inbox()));
    render(<FilesPending role="hr-staff" />);
    expect(screen.getByLabelText("Loading").getAttribute("aria-busy")).toBe("true");
    expect(await screen.findByText("Pending")).toBeTruthy();
    expect(figure("Pending").textContent).toBe("Pending12");
    expect(figure("Urgent").textContent).toBe("Urgent3");
    expect(figure("Overdue").textContent).toBe("Overdue2");
    const { url, headers } = lastCall(fetchMock);
    expect(url).toBe(URL_INBOX);
    expect(headers.Authorization).toBe("Bearer test-token");
  });

  it("sends no Authorization header without a session token", async () => {
    localStorage.clear();
    const fetchMock = stubFetch(answer(200, inbox()));
    render(<FilesPending role="hr-staff" />);
    expect(await screen.findByText("Pending")).toBeTruthy();
    expect(lastCall(fetchMock).headers.Authorization).toBeUndefined();
  });

  it("flags overdue files in danger when there are any", async () => {
    stubFetch(answer(200, inbox()));
    render(<FilesPending role="hr-staff" />);
    expect((await screen.findByText("2 files overdue")).className).toContain("eos-badge--danger");
    expect(figure("Overdue").hasAttribute("data-warn")).toBe(true);
    expect(figure("Pending").hasAttribute("data-warn")).toBe(false);
    expect(figure("Urgent").hasAttribute("data-warn")).toBe(false);
  });

  it("says one file overdue in the singular", async () => {
    stubFetch(answer(200, inbox({ overdue: 1 })));
    render(<FilesPending role="hr-staff" />);
    expect((await screen.findByText("1 file overdue")).className).toContain("eos-badge--danger");
  });

  it("does not flag overdue files when there are none", async () => {
    stubFetch(answer(200, inbox({ overdue: 0, items: [file({ id: "f9", number: "ADM/2026/0099" })] })));
    render(<FilesPending role="hr-staff" />);
    expect(await screen.findByText("ADM/2026/0099")).toBeTruthy();
    expect(figure("Overdue").hasAttribute("data-warn")).toBe(false);
    expect(document.querySelector(".eos-e-office__alert")).toBeNull();
    expect(screen.queryByText("Overdue", { selector: ".eos-badge" })).toBeNull();
  });

  it("lists the files waiting longest with subject, action asked for, due or received date, in the inbox's order", async () => {
    stubFetch(answer(200, inbox()));
    render(<FilesPending role="hr-staff" />);
    const list = await screen.findByRole("list", { name: "Files waiting longest" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows.map((r) => within(r).getByText(/^[A-Z]+\/2026\//).textContent)).toEqual([
      "EST/2026/0007",
      "ADM/2026/0012",
      "HR/2026/0031",
      "ACC/2026/0004",
    ]);
    expect(within(rows[0]!).getByText("Appointment of guest faculty, Commerce")).toBeTruthy();
    expect(within(rows[0]!).getByText("For approval")).toBeTruthy();
    expect(within(rows[0]!).getByText("Due 25 Oct 2026")).toBeTruthy();
    expect(within(rows[1]!).getByText("For comments")).toBeTruthy();
    expect(within(rows[1]!).getByText("Due 5 Nov 2026")).toBeTruthy();
    // No due date: the date it was received, as an Indian date.
    expect(within(rows[2]!).getByText("Received 28 Oct 2026")).toBeTruthy();
    expect(within(rows[3]!).getByText("Received 20 Oct 2026")).toBeTruthy();
  });

  it("puts an overdue badge on overdue files only, and a priority badge on urgent and immediate ones", async () => {
    stubFetch(answer(200, inbox()));
    render(<FilesPending role="hr-staff" />);
    const rows = within(await screen.findByRole("list", { name: "Files waiting longest" })).getAllByRole("listitem");
    expect(within(rows[0]!).getByText("Overdue").className).toContain("eos-badge--danger");
    expect(within(rows[0]!).getByText("Urgent").className).toContain("eos-badge--warning");
    expect(within(rows[1]!).queryByText("Overdue")).toBeNull();
    expect(rows[1]!.querySelector(".eos-badge")).toBeNull();
    expect(within(rows[2]!).queryByText("Overdue")).toBeNull();
    expect(within(rows[2]!).getByText("Immediate").className).toContain("eos-badge--danger");
    expect(within(rows[3]!).getByText("Overdue").className).toContain("eos-badge--danger");
    expect(within(rows[3]!).queryByText("Normal")).toBeNull();
  });

  it("says how many of the files it shows when the inbox holds more", async () => {
    stubFetch(answer(200, inbox()));
    render(<FilesPending role="hr-staff" />);
    expect(await screen.findByText("Showing 4 of 12 files")).toBeTruthy();
  });

  it("does not say how many it shows when every file is listed", async () => {
    stubFetch(answer(200, inbox({ total: 4, next_cursor: null })));
    render(<FilesPending role="hr-staff" />);
    expect(await screen.findByRole("list", { name: "Files waiting longest" })).toBeTruthy();
    expect(screen.queryByText(/^Showing/)).toBeNull();
  });

  it("mentions letters received still to attach to a file", async () => {
    stubFetch(answer(200, inbox({ unattached_receipts: 3 })));
    render(<FilesPending role="hr-staff" />);
    expect(await screen.findByText("3 letters received to attach to a file")).toBeTruthy();
  });

  it("is not empty while a letter waits to be attached, and says it in the singular", async () => {
    stubFetch(answer(200, nothing({ unattached_receipts: 1 })));
    render(<FilesPending role="hr-staff" />);
    expect(await screen.findByText("1 letter received to attach to a file")).toBeTruthy();
    expect(figure("Pending").textContent).toBe("Pending0");
    expect(screen.queryByText("No files pending")).toBeNull();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("shows an empty state when no file is pending", async () => {
    stubFetch(answer(200, nothing()));
    render(<FilesPending role="hr-staff" />);
    expect(await screen.findByText("No files pending")).toBeTruthy();
    expect(screen.getByText("Files sent to you for action appear here.")).toBeTruthy();
    expect(screen.queryByText("Pending")).toBeNull();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("renders an inbox without items instead of unmounting the dashboard", async () => {
    const { items: _omitted, ...withoutItems } = inbox();
    stubFetch(answer(200, withoutItems));
    render(<FilesPending role="hr-staff" />);
    expect(await screen.findByText("Pending")).toBeTruthy();
    expect(screen.queryByRole("list")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows a generic error, never the server's message, and retries", async () => {
    const fetchMock = stubFetch(answer(500, { detail: { code: "internal", message: "Database unavailable" } }), answer(200, inbox()));
    render(<FilesPending role="hr-staff" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Could not load file data.");
    expect(alert.textContent).not.toContain("Database unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("EST/2026/0007")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(lastCall(fetchMock).url).toBe(URL_INBOX);
  });

  it("shows an error when the service cannot be reached, and retries", async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValueOnce(answer(200, inbox()));
    vi.stubGlobal("fetch", fetchMock);
    render(<FilesPending role="hr-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("File data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("EST/2026/0007")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it.each([404, 502, 503])("says the data is not available yet on %i, with a retry", async (status) => {
    stubFetch(answer(status, { detail: "Not Found" }));
    render(<FilesPending role="hr-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("File data is not available yet.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("asks the user to sign in again, without a retry, on 401", async () => {
    stubFetch(answer(401, { detail: { code: "unauthenticated", message: "Not authenticated" } }));
    render(<FilesPending role="hr-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("offers no retry when the viewer lacks the permission (403)", async () => {
    stubFetch(answer(403, { detail: { code: "forbidden", message: "Missing permission e-office:file:use" } }));
    render(<FilesPending role="hr-staff" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("You do not have access to this.");
    expect(alert.textContent).not.toContain("e-office:file:use");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});

describe("dates", () => {
  it("reads a contract date as an Indian calendar date", () => {
    expect(day("2026-11-05")).toBe("5 Nov 2026");
    expect(day(null)).toBe("—");
    expect(day("not a date")).toBe("not a date");
  });

  it("gives the date in India of a date-time", () => {
    expect(indianDay("2026-10-27T18:29:00Z")).toBe("27 Oct 2026");
    expect(indianDay("2026-10-27T18:30:00Z")).toBe("28 Oct 2026");
    expect(indianDay(null)).toBe("—");
    expect(indianDay("garbage")).toBe("—");
  });
});
