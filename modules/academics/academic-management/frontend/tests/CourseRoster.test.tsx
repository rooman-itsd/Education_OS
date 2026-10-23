import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MyOffering, RosterPage } from "../src/api/client";
import { widgets } from "../src/widgets";
import { CourseRoster } from "../src/widgets/CourseRoster";

const offering = (over: Partial<MyOffering> = {}): MyOffering => ({
  course_offering_id: "co-1",
  course: { code: "CS101", title: "Programming", credits: 4, course_type: "theory" },
  role: "primary",
  status: "open",
  sections: [
    { section_id: "s-a", code: "A", enrolled_count: 2 },
    { section_id: "s-b", code: "B", enrolled_count: 1 },
  ],
  enrolled_count: 3,
  ...over,
});

const roster: RosterPage = {
  course_offering_id: "co-1",
  total: 2,
  items: [
    { person_id: "p-1", student_name: "Asha Rao", roll_number: "R1", section_id: "s-a", section_code: "A", enrolled_at: "2026-10-22T08:00:00+00:00" },
    { person_id: "p-2", section_id: "s-b", section_code: "B", enrolled_at: "2026-10-22T08:00:00+00:00" },
  ],
};

const reply = (status: number, body: unknown) => ({ ok: status < 400, status, statusText: "", json: async () => body });

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("academic-management.course-roster widget", () => {
  it("is exported with the id and permission the Faculty layout and the contract expect", () => {
    const w = widgets.find((x) => x.id === "academic-management.course-roster");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("academic-management:roster:read");
    expect(w?.kind).toBe("list");
    expect(w?.size).toBe("2x1");
    expect(w?.component).toBe(CourseRoster);
    expect(widgets.some((x) => x.id === "academic-management.faculty-load")).toBe(false); // built by its dashboard owner
  });

  it("shows loading, then the caller's courses from GET /me/offerings with the session token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(reply(200, { academic_period_id: "t-1", items: [offering()] }));
    vi.stubGlobal("fetch", fetchMock);
    render(<CourseRoster role="faculty" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("CS101 · Programming")).toBeTruthy();
    expect(screen.getByText("3 enrolled")).toBeTruthy();
    expect(screen.getByText(/Primary · A \(2\), B \(1\)/)).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/academic-management/me/offerings");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("says so when the caller teaches nothing this term", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(200, { academic_period_id: "t-1", items: [] })));
    render(<CourseRoster role="faculty" />);
    expect(await screen.findByText("No courses this term")).toBeTruthy();
  });

  it("treats 'no term is active' (404 active_term_not_found) as nothing this term, not as a failure", async () => {
    const body = { detail: { code: "active_term_not_found", message: "no academic term was given and no term is active" } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(404, body)));
    render(<CourseRoster role="faculty" />);
    expect(await screen.findByText("No courses this term")).toBeTruthy();
    expect(screen.queryByText("Could not load your courses")).toBeNull();
  });

  it("offers a retry after a failure, and the retry loads again", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(reply(503, {}))
      .mockResolvedValueOnce(reply(200, { academic_period_id: "t-1", items: [offering()] }));
    vi.stubGlobal("fetch", fetchMock);
    render(<CourseRoster role="faculty" />);
    const alert = await screen.findByRole("alert");
    fireEvent.click(within(alert).getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("CS101 · Programming")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("offers no retry when access is refused", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(403, {})));
    render(<CourseRoster role="student" />);
    const alert = await screen.findByRole("alert");
    expect(within(alert).queryByRole("button", { name: "Try again" })).toBeNull();
    expect(within(alert).getByText("You do not have access to course rosters.")).toBeTruthy();
  });

  it("opens a course's roster and goes back to the list", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(reply(200, { academic_period_id: "t-1", items: [offering()] }))
      .mockResolvedValueOnce(reply(200, roster));
    vi.stubGlobal("fetch", fetchMock);
    render(<CourseRoster role="faculty" />);
    fireEvent.click(await screen.findByText("CS101 · Programming"));
    const list = await screen.findByRole("list", { name: "Roster of CS101 · Programming" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(2);
    expect(within(list).getByText("Asha Rao")).toBeTruthy();
    expect(within(list).getByText("R1 · Section A")).toBeTruthy();
    expect(within(list).getByText("Name not available")).toBeTruthy(); // no name and no roll number are allowed
    expect(within(list).getByText("Section B")).toBeTruthy();
    expect((fetchMock.mock.calls[1] as [string])[0]).toBe("/api/v1/academic-management/offerings/co-1/roster?limit=200");
    fireEvent.click(screen.getByRole("button", { name: "All courses" }));
    expect(await screen.findByText("CS101 · Programming")).toBeTruthy();
  });

  it("shows an empty roster as such", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(reply(200, { academic_period_id: "t-1", items: [offering({ enrolled_count: 0 })] }))
        .mockResolvedValueOnce(reply(200, { course_offering_id: "co-1", items: [], total: 0 })),
    );
    render(<CourseRoster role="faculty" />);
    fireEvent.click(await screen.findByText("CS101 · Programming"));
    expect(await screen.findByText("No learners enrolled in CS101 · Programming yet")).toBeTruthy();
  });
});
