import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RecentMaterialItem } from "../src/api/client";
import { widgets } from "../src/widgets";
import { CourseMaterialsWidget, MATERIAL_LIMIT } from "../src/widgets/CourseMaterialsWidget";

const material = (over: Partial<RecentMaterialItem> = {}): RecentMaterialItem => ({
  material_id: "m1",
  course_space_id: "s1",
  course_title: "Programming",
  title: "Week 1 notes",
  material_type: "page",
  published_at: "2026-11-05T09:00:00+00:00",
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

describe("lms.course-materials widget", () => {
  it("is exported with the id, permission and size the Student layout expects", () => {
    const w = widgets.find((x) => x.id === "lms.course-materials");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("lms:course-space:read-own");
    expect(w?.size).toBe("2x1");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(CourseMaterialsWidget);
  });

  it("lists recent materials from GET /me/course-materials with the session token", async () => {
    const fetchMock = answer(200, {
      items: [
        material(),
        material({ material_id: "m2", title: "Python docs", material_type: "link", course_title: "Data Science" }),
        material({ material_id: "m3", title: "Slides", material_type: "document" }),
      ],
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<CourseMaterialsWidget role="student" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Week 1 notes")).toBeTruthy();
    expect(screen.getByText("Python docs")).toBeTruthy();
    expect(screen.getByText("Data Science")).toBeTruthy();
    expect(screen.getByText("Page")).toBeTruthy();
    expect(screen.getByText("Link")).toBeTruthy();
    expect(screen.getByText("Document")).toBeTruthy();
    expect(screen.getByRole("list", { name: "Course materials" })).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/api/v1/lms/me/course-materials?limit=${MATERIAL_LIMIT}`);
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("shows an empty state when nothing was published recently", async () => {
    vi.stubGlobal("fetch", answer(200, { items: [] }));
    render(<CourseMaterialsWidget role="student" />);
    expect(await screen.findByText("No new course materials")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 404, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => ({ items: [material()] }) });
    vi.stubGlobal("fetch", fetchMock);
    render(<CourseMaterialsWidget role="student" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Course data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Week 1 notes")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it.each([
    [401, "Sign in again to see this."],
    [403, "You do not have access to this."],
  ])("on %i says why and offers no retry", async (status, text) => {
    vi.stubGlobal("fetch", answer(status, {}));
    render(<CourseMaterialsWidget role="student" />);
    expect((await screen.findByRole("alert")).textContent).toContain(text);
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("on another server error offers a retry", async () => {
    vi.stubGlobal("fetch", answer(500, {}));
    render(<CourseMaterialsWidget role="student" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load course materials");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
