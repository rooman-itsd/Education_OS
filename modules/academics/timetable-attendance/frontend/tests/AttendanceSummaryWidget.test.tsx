import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { widgets } from "../src/widgets";
import { AttendanceSummaryWidget } from "../src/widgets/AttendanceSummaryWidget";
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
  course_title: "Programming",
  classes_held: 3,
  attended: 2,
  excused: 1,
  percentage: 66.67,
  below_threshold: true,
  ...over,
});

describe("timetable-attendance.attendance-summary widget", () => {
  it("is exported with the id, permission and size the Student layout expects", () => {
    const w = widgets.find((x) => x.id === "timetable-attendance.attendance-summary");
    expect(w?.title).toBe("My attendance");
    expect(w?.permission).toBe("timetable-attendance:report:read-own");
    expect(w?.component).toBe(AttendanceSummaryWidget);
  });

  it("shows the overall figure and each course with its shortage flag", async () => {
    const fetchMock = answer(200, {
      student_id: "u",
      academic_period_id: "p",
      threshold_percent: 75,
      overall_percentage: 85.71,
      items: [
        row(),
        row({ course_offering_id: "o2", course_code: "MA201", course_title: "Maths", percentage: 100, below_threshold: false, excused: 0 }),
        row({ course_offering_id: "o3", course_code: "PH101", course_title: "Physics", classes_held: 0, attended: 0, percentage: null, below_threshold: false }),
      ],
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<AttendanceSummaryWidget role="student" />);
    expect(await screen.findByText("Overall 85.7% · minimum 75%")).toBeTruthy();
    expect(screen.getByText("66.7% short")).toBeTruthy();
    expect(screen.getByText("100%")).toBeTruthy();
    expect(screen.getByText("–")).toBeTruthy(); // no counted class: no percentage
    expect(screen.getByText("2 of 3 attended · 1 excused")).toBeTruthy();
    expect((fetchMock.mock.calls[0] as [string])[0]).toBe("/api/v1/timetable-attendance/me/attendance-summary");
  });

  it("shows the empty state when no term is active (404 active_term_not_found)", async () => {
    vi.stubGlobal("fetch", refuse(404, "active_term_not_found"));
    render(<AttendanceSummaryWidget role="student" />);
    expect(await screen.findByText("No attendance recorded yet")).toBeTruthy();
  });

  it("shows the empty state when nothing has been counted", async () => {
    vi.stubGlobal("fetch", answer(200, { student_id: "u", academic_period_id: "p", threshold_percent: 75, overall_percentage: null, items: [] }));
    render(<AttendanceSummaryWidget role="student" />);
    expect(await screen.findByText("No attendance recorded yet")).toBeTruthy();
  });

  it("a 404 without the code is not available yet", async () => {
    vi.stubGlobal("fetch", answer(404, { detail: "Not Found" }));
    render(<AttendanceSummaryWidget role="student" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Timetable and attendance are not available yet.");
  });
});
