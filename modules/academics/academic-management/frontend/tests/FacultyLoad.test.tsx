import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { FacultyLoadReport } from "../src/api/client";
import { widgets } from "../src/widgets";
import { FacultyLoad } from "../src/widgets/FacultyLoad";

const report = (over: Partial<FacultyLoadReport> = {}): FacultyLoadReport => ({
  academic_period_id: "t-1",
  academic_period_code: "2026-ODD",
  academic_period_name: "Odd semester 2026",
  department_id: "d-1",
  max_weekly_contact_hours: 16,
  faculty_count: 3,
  over_load_count: 1,
  items: [
    { faculty_id: "f-1", faculty_name: "Dr Meera Iyer", offerings_count: 5, contact_hours: 18.5, over_load: true },
    { faculty_id: "f-2", faculty_name: "Prof Arun Das", offerings_count: 3, contact_hours: 12, over_load: false },
    { faculty_id: "f-3", faculty_name: "Dr Kavya Nair", offerings_count: 1, contact_hours: 4, over_load: false },
  ],
  ...over,
});

const reply = (status: number, body: unknown) => ({ ok: status < 400, status, statusText: "", json: async () => body });

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("academic-management.faculty-load widget", () => {
  it("is exported with the id and permission the Department Admin layout and the contract expect", () => {
    const w = widgets.find((x) => x.id === "academic-management.faculty-load");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("academic-management:faculty-load:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(FacultyLoad);
  });

  it("shows loading, then each faculty member's hours from GET /faculty-load with the session token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(reply(200, report()));
    vi.stubGlobal("fetch", fetchMock);
    render(<FacultyLoad role="department-admin" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    const list = await screen.findByRole("list", { name: "Faculty load, Odd semester 2026" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(within(rows[0]!).getByText("Dr Meera Iyer")).toBeTruthy();
    expect(within(rows[0]!).getByText("18.5 h · over")).toBeTruthy();
    expect(within(rows[1]!).getByText("12 h")).toBeTruthy(); // whole hours carry no ".0"
    expect(within(rows[2]!).getByText("1 offering")).toBeTruthy();
    expect(screen.getByText("Odd semester 2026 · 1 of 3 over the 16 h weekly maximum")).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/academic-management/faculty-load"); // the server narrows to the caller's department
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("says so when nobody has teaching assigned", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(200, report({ items: [], faculty_count: 0, over_load_count: 0 }))));
    render(<FacultyLoad role="department-admin" />);
    expect(await screen.findByText("No teaching assigned in Odd semester 2026")).toBeTruthy();
  });

  it("treats 'no term is active' (404 active_term_not_found) as nothing to show, not as a failure", async () => {
    const body = { detail: { code: "active_term_not_found", message: "no academic term was given and no term is active" } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(404, body)));
    render(<FacultyLoad role="department-admin" />);
    expect(await screen.findByText("No active term")).toBeTruthy();
    expect(screen.queryByText("Could not load faculty load")).toBeNull();
  });

  it("offers a retry after a failure (the 503 directory outage included), and the retry loads again", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(reply(503, {})).mockResolvedValueOnce(reply(200, report()));
    vi.stubGlobal("fetch", fetchMock);
    render(<FacultyLoad role="department-admin" />);
    const alert = await screen.findByRole("alert");
    fireEvent.click(within(alert).getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Dr Meera Iyer")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("offers no retry when access is refused", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(403, {})));
    render(<FacultyLoad role="faculty" />);
    const alert = await screen.findByRole("alert");
    expect(within(alert).queryByRole("button", { name: "Try again" })).toBeNull();
    expect(within(alert).getByText("You do not have access to faculty load.")).toBeTruthy();
  });
});
