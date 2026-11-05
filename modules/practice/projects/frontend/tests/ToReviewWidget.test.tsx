import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReviewItem } from "../src/api/client";
import { widgets } from "../src/widgets";
import { REVIEW_LIMIT, ToReviewWidget } from "../src/widgets/ToReviewWidget";
import { answer, failThenAnswer, firstCall, itDescribesFailures, pending, useSession } from "./helpers";

const item = (over: Partial<ReviewItem> = {}): ReviewItem => ({
  kind: "milestone",
  project_id: "p1",
  project_title: "Solar irrigation pump",
  milestone_id: "m1",
  milestone_title: "Design review",
  submission: {
    id: "s1",
    organisation_id: "o1",
    project_id: "p1",
    milestone_id: "m1",
    version: 2,
    note: "With costs",
    submitted_by: "u1",
    submitted_at: "2026-11-01T06:00:00+00:00",
  },
  waiting_days: 3,
  ...over,
});

useSession();

describe("projects.to-review widget", () => {
  it("is exported with the id, permission and size the guide layouts expect", () => {
    const w = widgets.find((x) => x.id === "projects.to-review");
    expect(w?.permission).toBe("projects:guidance:read");
    expect(w?.size).toBe("2x1");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(ToReviewWidget);
  });

  it("shows a loading state while the request runs", () => {
    vi.stubGlobal("fetch", pending());
    render(<ToReviewWidget role="project-guide" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
  });

  it("lists milestones and final submissions from GET /me/reviews", async () => {
    const final = item({
      kind: "final",
      project_id: "p2",
      project_title: "Water survey",
      milestone_id: null,
      milestone_title: null,
      submission: { ...item().submission, id: "s2", milestone_id: null, version: 1 },
      waiting_days: 8,
    });
    const fetchMock = answer(200, [item(), final]);
    vi.stubGlobal("fetch", fetchMock);
    render(<ToReviewWidget role="project-guide" />);
    expect(await screen.findByText("Design review")).toBeTruthy();
    expect(screen.getByText("Final submission")).toBeTruthy();
    expect(screen.getByText(/Solar irrigation pump · version 2/)).toBeTruthy();
    expect(screen.getByText(/Water survey · version 1/)).toBeTruthy();
    expect(screen.getByText("3 days")).toBeTruthy();
    expect(screen.getByText("8 days")).toBeTruthy();
    const { url, auth } = firstCall(fetchMock);
    expect(url).toBe(`/api/v1/projects/me/reviews?limit=${REVIEW_LIMIT}`);
    expect(auth).toBe("Bearer test-token");
  });

  it("shows an empty state when nothing waits", async () => {
    vi.stubGlobal("fetch", answer(200, []));
    render(<ToReviewWidget role="project-guide" />);
    expect(await screen.findByText("Nothing waiting for your review")).toBeTruthy();
  });

  it("shows an error, not a crash, when the service is unavailable, and retries", async () => {
    const fetchMock = failThenAnswer([item({ waiting_days: 0 })]);
    vi.stubGlobal("fetch", fetchMock);
    render(<ToReviewWidget role="project-guide" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Projects data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Today")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  itDescribesFailures(() => <ToReviewWidget role="project-guide" />, "work to review");
});
