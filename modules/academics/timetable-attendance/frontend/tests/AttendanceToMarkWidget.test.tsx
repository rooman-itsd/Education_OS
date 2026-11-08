import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { widgets } from "../src/widgets";
import { AttendanceToMarkWidget, MARK_LIMIT } from "../src/widgets/AttendanceToMarkWidget";
import { answer, klass } from "./helpers";

const counts = { eligible: 30, unmarked: 4, present: 20, absent: 4, late: 2, excused: 0 };

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("timetable-attendance.attendance-to-mark widget", () => {
  it("is exported with the id, permission and size the Faculty layout expects", () => {
    const w = widgets.find((x) => x.id === "timetable-attendance.attendance-to-mark");
    expect(w?.title).toBe("Attendance to mark");
    expect(w?.permission).toBe("timetable-attendance:attendance-record:mark");
    expect(w?.component).toBe(AttendanceToMarkWidget);
  });

  it("lists the classes waiting for attendance from GET /me/attendance-to-mark", async () => {
    const fetchMock = answer(200, {
      items: [
        { scheduled_class: klass({ id: "a" }), marking_deadline: "2026-11-07T10:00:00+00:00" },
        { scheduled_class: klass({ id: "b", course_code: "MA201" }), marking_deadline: "2026-11-07T11:00:00+00:00", counts },
        {
          scheduled_class: klass({ id: "c", course_code: "PH101" }),
          marking_deadline: "2026-11-07T12:00:00+00:00",
          counts: { ...counts, unmarked: 0 },
        },
      ],
      total: 3,
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<AttendanceToMarkWidget role="faculty" />);
    expect(await screen.findByText("Not opened")).toBeTruthy();
    expect(screen.getByText("4 unmarked")).toBeTruthy();
    expect(screen.getByText("Ready to close")).toBeTruthy();
    expect(screen.getAllByText(/mark by/)).toHaveLength(3);
    expect((fetchMock.mock.calls[0] as [string])[0]).toBe("/api/v1/timetable-attendance/me/attendance-to-mark");
  });

  it("shows the first classes and says how many more wait", async () => {
    const many = Array.from({ length: MARK_LIMIT + 3 }, (_, i) => ({
      scheduled_class: klass({ id: `c${i}` }),
      marking_deadline: "2026-11-07T10:00:00+00:00",
    }));
    vi.stubGlobal("fetch", answer(200, { items: many, total: many.length }));
    render(<AttendanceToMarkWidget role="faculty" />);
    expect(await screen.findByText("and 3 more")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(MARK_LIMIT);
  });

  it("shows an empty state when nothing waits", async () => {
    vi.stubGlobal("fetch", answer(200, { items: [], total: 0 }));
    render(<AttendanceToMarkWidget role="faculty" />);
    expect(await screen.findByText("No attendance waiting to be marked")).toBeTruthy();
  });

  it("treats a network failure as not available yet", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<AttendanceToMarkWidget role="faculty" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Timetable and attendance are not available yet.");
  });
});
