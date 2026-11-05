import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { MyProject } from "../src/api/client";
import { widgets } from "../src/widgets";
import { MyProjectsWidget } from "../src/widgets/MyProjectsWidget";
import { answer, failThenAnswer, firstCall, itDescribesFailures, pending, useSession } from "./helpers";

const project = (over: Partial<MyProject> = {}): MyProject => ({
  id: "p1",
  organisation_id: "o1",
  title: "Solar irrigation pump",
  status: "active",
  member_count: 3,
  milestones_total: 4,
  milestones_accepted: 1,
  my_role: "lead",
  next_milestone: {
    id: "m1",
    organisation_id: "o1",
    project_id: "p1",
    title: "Design review",
    due_on: "2026-11-10",
    status: "pending",
  },
  ...over,
});

useSession();

describe("projects.my-projects widget", () => {
  it("is exported with the id, permission and size the learner layouts expect", () => {
    const w = widgets.find((x) => x.id === "projects.my-projects");
    expect(w?.permission).toBe("projects:self:read");
    expect(w?.size).toBe("2x1");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(MyProjectsWidget);
  });

  it("shows a loading state while the request runs", () => {
    vi.stubGlobal("fetch", pending());
    render(<MyProjectsWidget role="engineering-student" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
  });

  it("lists the caller's projects from GET /me/projects with the session token", async () => {
    const fetchMock = answer(200, [
      project(),
      project({ id: "p2", title: "Compost study", status: "proposed", my_role: "member", milestones_total: 0, next_milestone: null }),
    ]);
    vi.stubGlobal("fetch", fetchMock);
    render(<MyProjectsWidget role="engineering-student" />);
    expect(await screen.findByText("Solar irrigation pump")).toBeTruthy();
    expect(screen.getByText("Compost study")).toBeTruthy();
    expect(screen.getByText(/Lead · 1 of 4 milestones accepted/)).toBeTruthy();
    expect(screen.getByText(/next: Design review/)).toBeTruthy();
    expect(screen.getByText(/Member · No milestones yet/)).toBeTruthy();
    expect(screen.getByText("Active")).toBeTruthy();
    expect(screen.getByText("Proposed")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    const { url, auth } = firstCall(fetchMock);
    expect(url).toBe("/api/v1/projects/me/projects");
    expect(auth).toBe("Bearer test-token");
  });

  it("shows an empty state when the caller is on no project", async () => {
    vi.stubGlobal("fetch", answer(200, []));
    render(<MyProjectsWidget role="engineering-student" />);
    expect(await screen.findByText("You are not on a project yet")).toBeTruthy();
  });

  it("shows an error, not a crash, when the service is unavailable, and retries", async () => {
    const fetchMock = failThenAnswer([project()]);
    vi.stubGlobal("fetch", fetchMock);
    render(<MyProjectsWidget role="engineering-student" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Projects data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Solar irrigation pump")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  itDescribesFailures(() => <MyProjectsWidget role="engineering-student" />, "your projects");
});
