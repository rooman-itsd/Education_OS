import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { widgets } from "../src/widgets";
import { DEPARTMENT_LIMIT, DepartmentAttendanceWidget } from "../src/widgets/DepartmentAttendanceWidget";
import { answer, refuse } from "./helpers";

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const row = (over = {}) => ({
  course_offering_id: "o1",
  course_code: "CS101",
  section_id: "s1",
  section_code: "A",
  classes_held: 4,
  average_percentage: 83.34,
  students_below_threshold: 1,
  ...over,
});
const report = (items: unknown[]) => ({
  department_id: "d",
  academic_period_id: "p",
  threshold_percent: 75,
  overall_percentage: 85.71,
  items,
});

describe("timetable-attendance.department-attendance widget", () => {
  it("is exported with the id, permission and size the Department Admin layout expects", () => {
    const w = widgets.find((x) => x.id === "timetable-attendance.department-attendance");
    expect(w?.title).toBe("Department attendance");
    expect(w?.permission).toBe("timetable-attendance:report:read-department");
    expect(w?.size).toBe("2x1");
    expect(w?.component).toBe(DepartmentAttendanceWidget);
  });

  it("lists each course section with its average and the students below the minimum", async () => {
    const fetchMock = answer(200, report([row(), row({ section_id: "s2", section_code: "B", students_below_threshold: 0, average_percentage: null })]));
    vi.stubGlobal("fetch", fetchMock);
    render(<DepartmentAttendanceWidget role="department-admin" />);
    expect(await screen.findByText("CS101 · Section A")).toBeTruthy();
    expect(screen.getByText("4 classes held · average 83.3%")).toBeTruthy();
    expect(screen.getByText("1 below minimum")).toBeTruthy();
    expect(screen.getByText("None below minimum")).toBeTruthy();
    expect(screen.getByText("4 classes held · average –")).toBeTruthy();
    expect((fetchMock.mock.calls[0] as [string])[0]).toBe("/api/v1/timetable-attendance/reports/department-attendance");
  });

  it("shows the first sections and says how many more there are", async () => {
    const many = Array.from({ length: DEPARTMENT_LIMIT + 1 }, (_, i) => row({ section_id: `s${i}`, section_code: `${i}` }));
    vi.stubGlobal("fetch", answer(200, report(many)));
    render(<DepartmentAttendanceWidget role="department-admin" />);
    expect(await screen.findByText("and 1 more")).toBeTruthy();
  });

  it("shows the empty state when no term is active (404 active_term_not_found)", async () => {
    vi.stubGlobal("fetch", refuse(404, "active_term_not_found"));
    render(<DepartmentAttendanceWidget role="department-admin" />);
    expect(await screen.findByText("No department attendance yet")).toBeTruthy();
  });

  it("says the department is not known yet when the API cannot tell it (403 department_unknown)", async () => {
    vi.stubGlobal("fetch", refuse(403, "department_unknown"));
    render(<DepartmentAttendanceWidget role="department-admin" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Your department is not known yet");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("shows the empty state for a report with no rows", async () => {
    vi.stubGlobal("fetch", answer(200, report([])));
    render(<DepartmentAttendanceWidget role="department-admin" />);
    expect(await screen.findByText("No department attendance yet")).toBeTruthy();
  });
});
