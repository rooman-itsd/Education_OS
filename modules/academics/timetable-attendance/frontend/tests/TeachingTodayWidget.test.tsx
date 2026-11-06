import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { localDate } from "../src/api/client";
import { widgets } from "../src/widgets";
import { TeachingTodayWidget } from "../src/widgets/TeachingTodayWidget";
import { answer, klass, refuse } from "./helpers";

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("timetable-attendance.today-classes widget", () => {
  it("is exported with the id, permission and size the Faculty layout expects", () => {
    const w = widgets.find((x) => x.id === "timetable-attendance.today-classes");
    expect(w?.title).toBe("Teaching today");
    expect(w?.permission).toBe("timetable-attendance:scheduled-class:read");
    expect(w?.component).toBe(TeachingTodayWidget);
  });

  it("lists the classes taught today with their attendance state", async () => {
    const fetchMock = answer(200, {
      date: "2026-11-06",
      items: [
        klass({ id: "a" }),
        klass({ id: "b", course_code: "MA201", attendance_session: { id: "s", status: "open" } }),
        klass({ id: "c", course_code: "PH101", status: "completed", attendance_session: { id: "t", status: "closed" } }),
        klass({ id: "d", course_code: "CH101", status: "cancelled" }),
      ],
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<TeachingTodayWidget role="faculty" />);
    expect(await screen.findByText("Not taken")).toBeTruthy();
    expect(screen.getByText("Attendance open")).toBeTruthy();
    expect(screen.getByText("Attendance taken")).toBeTruthy();
    expect(screen.getByText("Cancelled")).toBeTruthy();
    expect(screen.getByRole("list", { name: "Classes you teach today" })).toBeTruthy();
    expect((fetchMock.mock.calls[0] as [string])[0]).toBe(`/api/v1/timetable-attendance/me/teaching-schedule?date=${localDate()}`);
  });

  it("shows an empty state when nothing is taught today", async () => {
    vi.stubGlobal("fetch", answer(200, { date: "2026-11-06", items: [] }));
    render(<TeachingTodayWidget role="faculty" />);
    expect(await screen.findByText("No classes to teach today")).toBeTruthy();
  });

  it("on 401 asks to sign in again", async () => {
    vi.stubGlobal("fetch", refuse(401, "unauthorised"));
    render(<TeachingTodayWidget role="faculty" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
  });

  it("on another server error offers a retry", async () => {
    vi.stubGlobal("fetch", answer(500, {}));
    render(<TeachingTodayWidget role="faculty" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load your classes");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
