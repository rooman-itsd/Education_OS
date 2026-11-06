import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { MilestoneDue } from "../src/api/client";
import { widgets } from "../src/widgets";
import { MilestonesDueWidget, WITHIN_DAYS } from "../src/widgets/MilestonesDueWidget";
import { answer, failThenAnswer, firstCall, itDescribesFailures, pending, useSession } from "./helpers";

const due = (over: Partial<MilestoneDue> = {}): MilestoneDue => ({
  id: "m1",
  organisation_id: "o1",
  project_id: "p1",
  project_title: "Solar irrigation pump",
  title: "Design review",
  due_on: "2026-11-10",
  status: "pending",
  overdue: false,
  days_left: 6,
  ...over,
});

useSession();

describe("projects.milestones-due widget", () => {
  it("is exported with the id, permission and size the learner layouts expect", () => {
    const w = widgets.find((x) => x.id === "projects.milestones-due");
    expect(w?.permission).toBe("projects:self:read");
    expect(w?.size).toBe("1x1");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(MilestonesDueWidget);
  });

  it("shows a loading state while the request runs", () => {
    vi.stubGlobal("fetch", pending());
    render(<MilestonesDueWidget role="engineering-student" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
  });

  it("lists milestones due from GET /me/milestones, overdue and returned marked", async () => {
    const fetchMock = answer(200, [
      due({ id: "m0", title: "Lab log", due_on: "2026-11-01", overdue: true, days_left: -3 }),
      due(),
      due({ id: "m2", title: "Survey", status: "returned", days_left: 9 }),
      due({ id: "m3", title: "Poster", days_left: 1 }),
    ]);
    vi.stubGlobal("fetch", fetchMock);
    render(<MilestonesDueWidget role="engineering-student" />);
    expect(await screen.findByText("Design review")).toBeTruthy();
    expect(screen.getByText("Overdue")).toBeTruthy();
    expect(screen.getByText("Returned")).toBeTruthy();
    expect(screen.getByText("6 days")).toBeTruthy();
    expect(screen.getByText("1 day")).toBeTruthy();
    expect(screen.getAllByText("Solar irrigation pump")).toHaveLength(4);
    expect(screen.getByRole("list", { name: "Milestones due" })).toBeTruthy();
    const { url, auth } = firstCall(fetchMock);
    expect(url).toBe(`/api/v1/projects/me/milestones?within_days=${WITHIN_DAYS}`);
    expect(auth).toBe("Bearer test-token");
  });

  it("shows an empty state when nothing is due", async () => {
    vi.stubGlobal("fetch", answer(200, []));
    render(<MilestonesDueWidget role="engineering-student" />);
    expect(await screen.findByText("Nothing due in the next two weeks")).toBeTruthy();
  });

  it("shows an error, not a crash, when the service is unavailable, and retries", async () => {
    const fetchMock = failThenAnswer([due()]);
    vi.stubGlobal("fetch", fetchMock);
    render(<MilestonesDueWidget role="engineering-student" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Projects data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Design review")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  itDescribesFailures(() => <MilestonesDueWidget role="engineering-student" />, "milestones");
});
