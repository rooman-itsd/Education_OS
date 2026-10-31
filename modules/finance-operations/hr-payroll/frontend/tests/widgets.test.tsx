import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { WidgetProps } from "@eos/ui-kit";
import type { JoiningsAndExitsReport, LeaveRequest, LeaveRequestPage, PayrollRun } from "../src/api/client";
import { widgets } from "../src/widgets";
import { dateRange, indianMonth, leaveDays, month, paise, rupees } from "../src/widgets/format";
import { JoiningsAndExits } from "../src/widgets/JoiningsAndExits";
import { LeaveRequests } from "../src/widgets/LeaveRequests";
import { PayrollRunStatus } from "../src/widgets/PayrollRunStatus";

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

/** The module is not mounted: the app answers FastAPI's own 404, without the contract's code. */
const UNMOUNTED = { detail: "Not Found" };

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
  // 15 Oct 2026, 11:30 in India: the payroll widget compares the run's month with this.
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-10-15T06:00:00Z"));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("widget declarations", () => {
  const expected: [string, string, string, string, string, ComponentType<WidgetProps>][] = [
    ["hr-payroll.leave-requests", "Leave requests pending", "hr-payroll:leave:approve", "2x1", "panel", LeaveRequests],
    ["hr-payroll.payroll-run-status", "Payroll this month", "hr-payroll:payroll:read", "1x1", "panel", PayrollRunStatus],
    ["hr-payroll.joinings-and-exits", "Joinings and exits", "hr-payroll:report:read", "2x1", "panel", JoiningsAndExits],
  ];

  it("exports the widgets the HR Staff layout names", () => {
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

describe("format", () => {
  it("formats money exactly in Indian rupees", () => {
    expect(rupees("1234567.5")).toBe("₹12,34,567.50");
    expect(rupees("0.05")).toBe("₹0.05");
    expect(rupees("-250.00")).toBe("-₹250.00");
    expect(rupees("12.345")).toBe("—");
    expect(rupees(null)).toBe("—");
    expect(paise("1500.5")).toBe(150050);
  });

  it("formats months, ranges and leave days", () => {
    expect(month("2026-10")).toBe("October 2026");
    expect(dateRange("2026-11-05", "2026-11-05")).toBe("5 Nov 2026");
    expect(dateRange("2026-11-05", "2026-11-07")).toBe("5 Nov – 7 Nov 2026");
    expect(dateRange("2026-12-30", "2027-01-02")).toBe("30 Dec 2026 – 2 Jan 2027");
    expect(leaveDays(0.5)).toBe("Half day");
    expect(leaveDays(1)).toBe("1 day");
    expect(leaveDays(2.5)).toBe("2.5 days");
  });

  it("takes the current month from the Indian date", () => {
    expect(indianMonth(new Date("2026-10-31T19:00:00Z"))).toBe("2026-11");
    expect(indianMonth(new Date("2026-10-31T18:00:00Z"))).toBe("2026-10");
  });
});

// ---------------------------------------------------------------------------------------------------------------

const leave = (over: Partial<LeaveRequest> = {}): LeaveRequest => ({
  id: "l1",
  employee_id: "e1",
  employee_name: "Anita Rao",
  leave_type_id: "t1",
  leave_type_name: "Casual leave",
  from: "2026-10-20",
  to: "2026-10-22",
  half_day: "none",
  days: 3,
  paid: true,
  status: "pending",
  created_at: "2026-10-10T05:00:00Z",
  ...over,
});

const leavePage = (over: Partial<LeaveRequestPage> = {}): LeaveRequestPage => ({
  items: [
    leave(),
    leave({ id: "l2", employee_name: "Ravi Kumar", leave_type_name: "Sick leave", from: "2026-10-21", to: "2026-10-21", half_day: "first_half", days: 0.5 }),
    leave({ id: "l3", employee_name: "Meena Iyer", leave_type_name: "Leave without pay", from: "2026-11-02", to: "2026-11-06", days: 5, paid: false }),
  ],
  pending_total: 3,
  next_cursor: null,
  ...over,
});

describe("hr-payroll.leave-requests", () => {
  it("shows the pending count and requests from GET /leave-requests?status=pending", async () => {
    const fetchMock = stubFetch(answer(200, leavePage()));
    render(<LeaveRequests role="hr-staff" />);
    expect(screen.getByLabelText("Loading").getAttribute("aria-busy")).toBe("true");
    expect(await screen.findByText("Pending")).toBeTruthy();
    expect(figure("Pending").textContent).toBe("Pending3");
    const { url, headers } = lastCall(fetchMock);
    expect(url).toBe("/api/v1/hr-payroll/leave-requests?status=pending");
    expect(headers.Authorization).toBe("Bearer test-token");
  });

  it("lists employee, type, dates and days in the contract's order, flagging unpaid leave", async () => {
    stubFetch(answer(200, leavePage()));
    render(<LeaveRequests role="hr-staff" />);
    const list = await screen.findByRole("list", { name: "Pending leave requests" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(within(rows[0]!).getByText("Anita Rao")).toBeTruthy();
    expect(within(rows[0]!).getByText("Casual leave")).toBeTruthy();
    expect(within(rows[0]!).getByText("20 Oct – 22 Oct 2026")).toBeTruthy();
    expect(within(rows[0]!).getByText("3 days")).toBeTruthy();
    expect(within(rows[0]!).queryByText("Unpaid")).toBeNull();
    expect(within(rows[1]!).getByText("21 Oct 2026 (first half)")).toBeTruthy();
    expect(within(rows[1]!).getByText("Half day")).toBeTruthy();
    expect(within(rows[2]!).getByText("5 days")).toBeTruthy();
    expect(within(rows[2]!).getByText("Unpaid").className).toContain("eos-badge--warning");
    expect(screen.queryByText(/more pending$/)).toBeNull();
  });

  it("lists the first five and says how many more are pending", async () => {
    const items = Array.from({ length: 6 }, (_, i) => leave({ id: `l${i}`, employee_name: `Employee ${i}` }));
    stubFetch(answer(200, leavePage({ items, pending_total: 12 })));
    render(<LeaveRequests role="hr-staff" />);
    const list = await screen.findByRole("list", { name: "Pending leave requests" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(5);
    expect(figure("Pending").textContent).toBe("Pending12");
    expect(screen.getByText("7 more pending")).toBeTruthy();
  });

  it("shows an empty state when no request is pending", async () => {
    stubFetch(answer(200, leavePage({ items: [], pending_total: 0 })));
    render(<LeaveRequests role="hr-staff" />);
    expect(await screen.findByText("No leave requests pending")).toBeTruthy();
    expect(screen.getByText("Requests waiting for a decision appear here.")).toBeTruthy();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("shows a generic error, never the server's message, and retries", async () => {
    const fetchMock = stubFetch(answer(500, { detail: { code: "internal", message: "Database unavailable" } }), answer(200, leavePage()));
    render(<LeaveRequests role="hr-staff" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Could not load HR data.");
    expect(alert.textContent).not.toContain("Database unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Anita Rao")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("says the data is not available yet when the module is not mounted, with a retry", async () => {
    stubFetch(answer(404, UNMOUNTED));
    render(<LeaveRequests role="hr-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("HR data is not available yet.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("offers no retry when the viewer lacks the permission", async () => {
    stubFetch(answer(403, { detail: { code: "forbidden", message: "Missing hr-payroll:leave:approve" } }));
    render(<LeaveRequests role="hr-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});

// ---------------------------------------------------------------------------------------------------------------

const run = (over: Partial<PayrollRun> = {}): PayrollRun => ({
  id: "r1",
  period: "2026-10",
  status: "review",
  employees: 148,
  gross_total: "6250000.00",
  deductions_total: "512345.50",
  net_total: "5737654.50",
  exceptions: [],
  prepared_by: "u-hr",
  approved_by: null,
  note: null,
  submitted_at: null,
  approved_at: null,
  paid_on: null,
  bank_reference: null,
  due_on: "2026-10-28",
  late: false,
  updated_at: "2026-10-14T05:00:00Z",
  ...over,
});

describe("hr-payroll.payroll-run-status", () => {
  it("shows the month, status, employees and net pay from GET /payroll-runs/current", async () => {
    const fetchMock = stubFetch(answer(200, run()));
    render(<PayrollRunStatus role="hr-staff" />);
    expect(screen.getByLabelText("Loading").getAttribute("aria-busy")).toBe("true");
    expect(await screen.findByText("October 2026")).toBeTruthy();
    expect(screen.getByText("In review").className).toContain("eos-badge--warning");
    expect(figure("Employees").textContent).toBe("Employees148");
    expect(figure("Net pay").textContent).toBe("Net pay₹57,37,654.50");
    expect(screen.getByText("Next: HR to submit it for approval")).toBeTruthy();
    expect(screen.getByText("Due 28 Oct 2026").hasAttribute("data-warn")).toBe(false);
    expect(screen.queryByText("Late")).toBeNull();
    expect(screen.queryByText(/^No run for/)).toBeNull();
    const { url, headers } = lastCall(fetchMock);
    expect(url).toBe("/api/v1/hr-payroll/payroll-runs/current");
    expect(headers.Authorization).toBe("Bearer test-token");
  });

  it.each([
    ["submitted", "Awaiting approval", "eos-badge--warning", "Next: finance or management to approve"],
    ["approved", "Approved", "eos-badge--info", "Next: finance to mark it paid"],
  ] as const)("says who acts next when the run is %s", async (status, label, tone, next) => {
    stubFetch(answer(200, run({ status })));
    render(<PayrollRunStatus role="hr-staff" />);
    expect((await screen.findByText(label)).className).toContain(tone);
    expect(screen.getByText(next)).toBeTruthy();
  });

  it("shows the paid date and no due date once paid", async () => {
    stubFetch(answer(200, run({ status: "paid", paid_on: "2026-10-30" })));
    render(<PayrollRunStatus role="hr-staff" />);
    expect((await screen.findByText("Paid")).className).toContain("eos-badge--success");
    expect(screen.getByText("Paid on 30 Oct 2026")).toBeTruthy();
    expect(screen.queryByText(/^Due /)).toBeNull();
  });

  it("flags a late run in danger", async () => {
    stubFetch(answer(200, run({ status: "submitted", late: true })));
    render(<PayrollRunStatus role="hr-staff" />);
    expect((await screen.findByText("Late")).className).toContain("eos-badge--danger");
    expect(screen.getByText("Due 28 Oct 2026").hasAttribute("data-warn")).toBe(true);
  });

  it("shows why a run was returned and the exceptions", async () => {
    stubFetch(
      answer(200, run({ note: "Arrears for Ravi missing", exceptions: [{ employee_id: "e1", message: "No salary" }, { employee_id: "e2", message: "No bank account" }] })),
    );
    render(<PayrollRunStatus role="hr-staff" />);
    expect(await screen.findByText("Returned: Arrears for Ravi missing")).toBeTruthy();
    expect(screen.getByText("Next: HR to correct it and submit again")).toBeTruthy();
    expect(screen.getByText("2 exceptions").className).toContain("eos-badge--warning");
  });

  it("says when the run shown is an earlier month's", async () => {
    stubFetch(answer(200, run({ period: "2026-09", status: "paid", paid_on: "2026-09-30" })));
    render(<PayrollRunStatus role="hr-staff" />);
    expect(await screen.findByText("September 2026")).toBeTruthy();
    expect(screen.getByText("No run for October 2026 yet. This is the latest.")).toBeTruthy();
  });

  it("shows an empty state when there is no run yet (404 not_found)", async () => {
    stubFetch(answer(404, { detail: { code: "not_found", message: "payroll run not found in your organisation" } }));
    render(<PayrollRunStatus role="hr-staff" />);
    expect(await screen.findByText("No payroll run this month")).toBeTruthy();
    expect(screen.getByText("Once HR starts the payroll for a month, its status appears here.")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("says the data is not available yet on a 404 without the module's code, and retries", async () => {
    const fetchMock = stubFetch(answer(404, UNMOUNTED), answer(200, run()));
    render(<PayrollRunStatus role="hr-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("HR data is not available yet.");
    expect(screen.queryByText("No payroll run this month")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("October 2026")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("offers no retry when the viewer lacks the permission", async () => {
    stubFetch(answer(403, { detail: { code: "forbidden", message: "Missing hr-payroll:payroll:read" } }));
    render(<PayrollRunStatus role="hr-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("asks the user to sign in again, without a retry, on 401", async () => {
    stubFetch(answer(401, { detail: { code: "unauthenticated", message: "Not authenticated" } }));
    render(<PayrollRunStatus role="hr-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});

// ---------------------------------------------------------------------------------------------------------------

const person = (name: string, date: string, over: Record<string, unknown> = {}) => ({
  employee_id: `id-${name}`,
  name,
  designation: "Assistant Professor",
  department_name: "Finance",
  date,
  ...over,
});

const movement = (over: Partial<JoiningsAndExitsReport> = {}): JoiningsAndExitsReport => ({
  from: "2026-10-01",
  to: "2026-10-15",
  joined: 2,
  exited: 1,
  headcount: 148,
  recent_joinings: [person("Kavya Shetty", "2026-10-12"), person("Arjun Nair", "2026-10-01", { department_name: null, designation: "Accountant" })],
  recent_exits: [person("Suresh Babu", "2026-10-10", { designation: "Lab Assistant", department_name: "Science" })],
  upcoming_exits: [person("Lata Menon", "2026-11-14")],
  ...over,
});

const quiet = (over: Partial<JoiningsAndExitsReport> = {}): JoiningsAndExitsReport =>
  movement({ joined: 0, exited: 0, recent_joinings: [], recent_exits: [], upcoming_exits: [], ...over });

describe("hr-payroll.joinings-and-exits", () => {
  it("shows the period, joined, exited and headcount from GET /reports/joinings-and-exits", async () => {
    const fetchMock = stubFetch(answer(200, movement()));
    render(<JoiningsAndExits role="hr-staff" />);
    expect(screen.getByLabelText("Loading").getAttribute("aria-busy")).toBe("true");
    expect(await screen.findByText("1 Oct – 15 Oct 2026")).toBeTruthy();
    expect(figure("Joined").textContent).toBe("Joined2");
    expect(figure("Exited").textContent).toBe("Exited1");
    expect(figure("Headcount").textContent).toBe("Headcount148");
    const { url, headers } = lastCall(fetchMock);
    expect(url).toBe("/api/v1/hr-payroll/reports/joinings-and-exits");
    expect(headers.Authorization).toBe("Bearer test-token");
  });

  it("lists recent joinings, exits and those serving notice with their dates", async () => {
    stubFetch(answer(200, movement()));
    render(<JoiningsAndExits role="hr-staff" />);
    const joinings = within(await screen.findByRole("list", { name: "Recent joinings" })).getAllByRole("listitem");
    expect(joinings).toHaveLength(2);
    expect(within(joinings[0]!).getByText("Kavya Shetty")).toBeTruthy();
    expect(within(joinings[0]!).getByText("Assistant Professor · Finance")).toBeTruthy();
    expect(within(joinings[0]!).getByText("Joined 12 Oct 2026")).toBeTruthy();
    expect(within(joinings[1]!).getByText("Accountant")).toBeTruthy();
    const exits = within(screen.getByRole("list", { name: "Recent exits" })).getAllByRole("listitem");
    expect(within(exits[0]!).getByText("Suresh Babu")).toBeTruthy();
    expect(within(exits[0]!).getByText("Left 10 Oct 2026")).toBeTruthy();
    const notice = within(screen.getByRole("list", { name: "Serving notice" })).getAllByRole("listitem");
    expect(within(notice[0]!).getByText("Lata Menon")).toBeTruthy();
    expect(within(notice[0]!).getByText("Last day 14 Nov 2026")).toBeTruthy();
  });

  it("lists at most five names a list and leaves out empty lists", async () => {
    const many = Array.from({ length: 8 }, (_, i) => person(`Joiner ${i}`, "2026-10-05"));
    stubFetch(answer(200, movement({ joined: 8, recent_joinings: many, recent_exits: [], upcoming_exits: [] })));
    render(<JoiningsAndExits role="hr-staff" />);
    const list = await screen.findByRole("list", { name: "Recent joinings" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(5);
    expect(screen.queryByRole("list", { name: "Recent exits" })).toBeNull();
    expect(screen.queryByRole("list", { name: "Serving notice" })).toBeNull();
  });

  it("is not empty while someone is serving notice", async () => {
    stubFetch(answer(200, quiet({ upcoming_exits: [person("Lata Menon", "2026-11-14")] })));
    render(<JoiningsAndExits role="hr-staff" />);
    expect(await screen.findByText("Lata Menon")).toBeTruthy();
    expect(screen.queryByText("No joinings or exits this month")).toBeNull();
  });

  it("shows an empty state when nobody joined, left or is serving notice", async () => {
    stubFetch(answer(200, quiet()));
    render(<JoiningsAndExits role="hr-staff" />);
    expect(await screen.findByText("No joinings or exits this month")).toBeTruthy();
    expect(screen.getByText("People who join or leave, and those serving notice, appear here.")).toBeTruthy();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("renders a report without lists instead of unmounting the dashboard", async () => {
    const { recent_joinings: _j, recent_exits: _e, upcoming_exits: _u, ...bare } = movement();
    stubFetch(answer(200, bare));
    render(<JoiningsAndExits role="hr-staff" />);
    expect(await screen.findByText("Headcount")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows an error when the service cannot be reached, and retries", async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValueOnce(answer(200, movement()));
    vi.stubGlobal("fetch", fetchMock);
    render(<JoiningsAndExits role="hr-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("HR data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Kavya Shetty")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it.each([404, 502, 503])("says the data is not available yet on %i, with a retry", async (status) => {
    stubFetch(answer(status, status === 404 ? UNMOUNTED : {}));
    render(<JoiningsAndExits role="hr-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("HR data is not available yet.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("offers no retry when the viewer lacks the permission", async () => {
    stubFetch(answer(403, { detail: { code: "forbidden", message: "Missing hr-payroll:report:read" } }));
    render(<JoiningsAndExits role="hr-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});
