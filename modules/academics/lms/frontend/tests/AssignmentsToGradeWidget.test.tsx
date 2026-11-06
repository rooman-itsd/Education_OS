import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { GradingQueueItem } from "../src/api/client";
import { widgets } from "../src/widgets";
import { AssignmentsToGradeWidget, QUEUE_LIMIT } from "../src/widgets/AssignmentsToGradeWidget";

const item = (over: Partial<GradingQueueItem> = {}): GradingQueueItem => ({
  course_space_id: "s1",
  course_title: "Programming",
  item_type: "assignment",
  item_id: "a1",
  title: "Essay 1",
  due_at: "2026-11-12T09:00:00+00:00",
  waiting_count: 3,
  oldest_waiting_since: "2026-11-05T10:00:00+00:00",
  ...over,
});

function answer(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({ ok: status < 400, status, statusText: "", json: async () => body });
}

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("lms.assignments-to-grade widget", () => {
  it("is exported with the id, permission and size the Faculty layout expects", () => {
    const w = widgets.find((x) => x.id === "lms.assignments-to-grade");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("lms:grade:manage-assigned");
    expect(w?.size).toBe("2x1");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(AssignmentsToGradeWidget);
  });

  it("lists the waiting work from GET /me/grading-queue with the session token", async () => {
    const fetchMock = answer(200, {
      items: [item(), item({ item_type: "quiz", item_id: "q1", title: "Quiz 2", waiting_count: 1, due_at: null })],
      total: 2,
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<AssignmentsToGradeWidget role="faculty" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Essay 1")).toBeTruthy();
    expect(screen.getByText("Quiz 2")).toBeTruthy();
    expect(screen.getByText("3 submissions")).toBeTruthy();
    expect(screen.getByText("1 attempt")).toBeTruthy();
    expect(screen.getAllByText(/Programming/)).toHaveLength(2);
    expect(screen.getByRole("list", { name: "Work to grade" })).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/lms/me/grading-queue");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("shows the first items and says how many more wait", async () => {
    const many = Array.from({ length: QUEUE_LIMIT + 2 }, (_, i) => item({ item_id: `a${i}`, title: `Work ${i}` }));
    vi.stubGlobal("fetch", answer(200, { items: many, total: many.length }));
    render(<AssignmentsToGradeWidget role="faculty" />);
    expect(await screen.findByText("Work 0")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(QUEUE_LIMIT);
    expect(screen.getByText("and 2 more")).toBeTruthy();
  });

  it("shows an empty state when nothing waits", async () => {
    vi.stubGlobal("fetch", answer(200, { items: [], total: 0 }));
    render(<AssignmentsToGradeWidget role="faculty" />);
    expect(await screen.findByText("Nothing waiting to be graded")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 503, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => ({ items: [item()], total: 1 }) });
    vi.stubGlobal("fetch", fetchMock);
    render(<AssignmentsToGradeWidget role="faculty" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Course data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Essay 1")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("treats a network failure as not available yet", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<AssignmentsToGradeWidget role="faculty" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Course data is not available yet.");
  });

  it.each([
    [401, "Sign in again to see this."],
    [403, "You do not have access to this."],
  ])("on %i says why and offers no retry", async (status, text) => {
    vi.stubGlobal("fetch", answer(status, {}));
    render(<AssignmentsToGradeWidget role="faculty" />);
    expect((await screen.findByRole("alert")).textContent).toContain(text);
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("on another server error offers a retry", async () => {
    vi.stubGlobal("fetch", answer(500, {}));
    render(<AssignmentsToGradeWidget role="faculty" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load work to grade");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
