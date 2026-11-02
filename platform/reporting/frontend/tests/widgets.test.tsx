import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { describeFailure, ReportingApiError } from "../src/api/client";
import { widgets } from "../src/widgets";
import { AttendanceAndResultsByDepartment } from "../src/widgets/AttendanceAndResultsByDepartment";
import { DepartmentReports } from "../src/widgets/DepartmentReports";

function mockFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status < 400,
    status,
    statusText: status === 200 ? "OK" : "Error",
    json: async () => body,
  });
}

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("reporting dashboard widgets", () => {
  it("exports both widgets with expected IDs and permissions", () => {
    const deptWidget = widgets.find((x) => x.id === "reporting.department-reports");
    expect(deptWidget).toBeDefined();
    expect(deptWidget?.permission).toBe("reporting:report:read");
    expect(deptWidget?.component).toBe(DepartmentReports);

    const mgmtWidget = widgets.find((x) => x.id === "reporting.attendance-and-results-by-department");
    expect(mgmtWidget).toBeDefined();
    expect(mgmtWidget?.permission).toBe("reporting:report:read");
    expect(mgmtWidget?.component).toBe(AttendanceAndResultsByDepartment);
  });

  it("renders DepartmentReports with metrics and recent items", async () => {
    const data = {
      department_id: "dept-cs",
      department_name: "Computer Science",
      attendance_rate: 88.5,
      exam_pass_rate: 94.2,
      faculty_load_average: 16.0,
      recent_reports: [
        { id: "rep-1", code: "department-attendance", title: "Monthly Attendance Summary", generated_at: "2026-10-31" },
        { id: "rep-2", code: "exam-results-summary", title: "Midterm Exam Analysis", generated_at: "2026-10-31" },
      ],
    };
    vi.stubGlobal("fetch", mockFetch(200, data));

    render(<DepartmentReports role="department-admin" />);
    expect(await screen.findByText("88.5%")).toBeDefined();
    expect(await screen.findByText("94.2%")).toBeDefined();
    expect(await screen.findByText("Monthly Attendance Summary")).toBeDefined();
  });

  it("renders AttendanceAndResultsByDepartment with averages and department list", async () => {
    const data = {
      institution_average_attendance: 84.2,
      institution_average_pass_rate: 89.1,
      departments: [
        {
          department_id: "dept-cs",
          department_name: "Computer Science",
          attendance_rate: 88.5,
          pass_rate: 94.2,
          total_students: 320,
          is_attendance_low: false,
        },
        {
          department_id: "dept-me",
          department_name: "Mechanical Engineering",
          attendance_rate: 74.0,
          pass_rate: 79.0,
          total_students: 280,
          is_attendance_low: true,
        },
      ],
    };
    vi.stubGlobal("fetch", mockFetch(200, data));

    render(<AttendanceAndResultsByDepartment role="management" />);
    expect(await screen.findByText("84.2%")).toBeDefined();
    expect(await screen.findByText("89.1%")).toBeDefined();
    expect(await screen.findByText("Computer Science")).toBeDefined();
    expect(await screen.findByText("Mechanical Engineering")).toBeDefined();
  });

  it("handles empty state in department reports", async () => {
    const emptyData = {
      department_id: "dept-cs",
      department_name: "Computer Science",
      attendance_rate: 0,
      exam_pass_rate: 0,
      faculty_load_average: 0,
      recent_reports: [],
    };
    vi.stubGlobal("fetch", mockFetch(200, emptyData));

    render(<DepartmentReports role="department-admin" />);
    expect(await screen.findByText("No department reports")).toBeDefined();
  });

  it("handles error state with retry", async () => {
    vi.stubGlobal("fetch", mockFetch(503, {}));
    render(<DepartmentReports role="department-admin" />);
    expect(await screen.findByText("Reporting service is not available yet.")).toBeDefined();
  });

  it("maps failure descriptions accurately", () => {
    expect(describeFailure(new ReportingApiError(401, "Unauthorized"), "widget").retry).toBe(false);
    expect(describeFailure(new ReportingApiError(403, "Forbidden"), "widget").retry).toBe(false);
    expect(describeFailure(new ReportingApiError(503, "Service Unavailable"), "widget").retry).toBe(true);
  });
});
