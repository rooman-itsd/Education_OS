import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { localDate } from "../src/api/client";
import { widgets } from "../src/widgets";
import { TodayWidget } from "../src/widgets/TodayWidget";
import { answer, klass, refuse } from "./helpers";

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("timetable-attendance.today widget", () => {
  it("is exported with the id, permission and size the Student layout expects", () => {
    const w = widgets.find((x) => x.id === "timetable-attendance.today");
    expect(w?.title).toBe("Today's classes");
    expect(w?.permission).toBe("timetable-attendance:scheduled-class:read-own");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(TodayWidget);
  });

  it("lists today's classes from GET /me/schedule for the viewer's date, with the session token", async () => {
    const fetchMock = answer(200, {
      date: "2026-11-06",
      items: [klass(), klass({ id: "c2", course_code: undefined, course_title: undefined, section_code: undefined, location_label: null, status: "cancelled" })],
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<TodayWidget role="student" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("CS101 Programming")).toBeTruthy();
    expect(screen.getByText(/Room 4 · Section A/)).toBeTruthy();
    expect(screen.getByText("Class")).toBeTruthy(); // no academic field assumed (the dancer layout uses it too)
    expect(screen.getByText("Cancelled")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/api/v1/timetable-attendance/me/schedule?date=${localDate()}`);
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("shows an empty state when there is no class today", async () => {
    vi.stubGlobal("fetch", answer(200, { date: "2026-11-06", items: [] }));
    render(<TodayWidget role="student" />);
    expect(await screen.findByText("No classes today")).toBeTruthy();
  });

  it("says not available yet when the service is missing, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 404, statusText: "", json: async () => ({ detail: "Not Found" }) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => ({ date: "x", items: [klass()] }) });
    vi.stubGlobal("fetch", fetchMock);
    render(<TodayWidget role="student" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Timetable and attendance are not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("CS101 Programming")).toBeTruthy();
  });

  it("on 403 says there is no access and offers no retry", async () => {
    vi.stubGlobal("fetch", refuse(403, "forbidden"));
    render(<TodayWidget role="student" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});

describe("localDate", () => {
  it("is the viewer's calendar date, zero padded", () => {
    expect(localDate(new Date(2026, 0, 5, 23, 59))).toBe("2026-01-05");
  });
});
