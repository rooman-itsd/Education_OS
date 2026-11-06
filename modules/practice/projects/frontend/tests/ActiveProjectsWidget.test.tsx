import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Project } from "../src/api/client";
import { widgets } from "../src/widgets";
import { ACTIVE_LIMIT, ActiveProjectsWidget } from "../src/widgets/ActiveProjectsWidget";
import { answer, failThenAnswer, firstCall, itDescribesFailures, pending, useSession } from "./helpers";

const project = (over: Partial<Project> = {}): Project => ({
  id: "p1",
  organisation_id: "o1",
  title: "Solar irrigation pump",
  kind: "Capstone",
  status: "active",
  ends_on: "2027-04-30",
  member_count: 3,
  milestones_total: 4,
  milestones_accepted: 1,
  ...over,
});

useSession();

describe("projects.active widget", () => {
  it("is exported with one permission that GET /projects accepts", () => {
    const w = widgets.find((x) => x.id === "projects.active");
    expect(w?.permission).toBe("projects:guidance:read");
    expect(w?.size).toBe("2x1");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(ActiveProjectsWidget);
  });

  it("every widget declares exactly one projects permission", () => {
    expect(widgets.map((w) => w.id)).toEqual([
      "projects.my-projects",
      "projects.milestones-due",
      "projects.to-review",
      "projects.active",
    ]);
    for (const w of widgets) expect(w.permission).toMatch(/^projects:[a-z]+:[a-z]+$/);
  });

  it("shows a loading state while the request runs", () => {
    vi.stubGlobal("fetch", pending());
    render(<ActiveProjectsWidget role="project-guide" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
  });

  it("lists active projects from GET /projects?status=active", async () => {
    const fetchMock = answer(200, {
      items: [project(), project({ id: "p2", title: "Water survey", kind: undefined, member_count: 1, milestones_total: 0, milestones_accepted: 0 })],
      next_cursor: null,
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ActiveProjectsWidget role="project-guide" />);
    expect(await screen.findByText("Solar irrigation pump")).toBeTruthy();
    expect(screen.getByText("Water survey")).toBeTruthy();
    expect(screen.getByText(/Capstone · 3 members · ends/)).toBeTruthy();
    expect(screen.getByText(/^1 member · ends/)).toBeTruthy();
    expect(screen.getByText("1/4")).toBeTruthy();
    expect(screen.getByText("0/0")).toBeTruthy();
    const { url, auth } = firstCall(fetchMock);
    expect(url).toBe(`/api/v1/projects/projects?status=active&limit=${ACTIVE_LIMIT}`);
    expect(auth).toBe("Bearer test-token");
  });

  it("shows an empty state when no project is active", async () => {
    vi.stubGlobal("fetch", answer(200, { items: [], next_cursor: null }));
    render(<ActiveProjectsWidget role="project-guide" />);
    expect(await screen.findByText("No active projects")).toBeTruthy();
  });

  it("shows an error, not a crash, when the service is unavailable, and retries", async () => {
    const fetchMock = failThenAnswer({ items: [project()], next_cursor: null });
    vi.stubGlobal("fetch", fetchMock);
    render(<ActiveProjectsWidget role="project-guide" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Projects data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Solar irrigation pump")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  itDescribesFailures(() => <ActiveProjectsWidget role="project-guide" />, "active projects");
});
