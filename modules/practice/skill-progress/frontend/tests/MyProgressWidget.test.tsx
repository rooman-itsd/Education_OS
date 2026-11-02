import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { LearnerProgressSummary, SkillProficiencyStatus } from "../src/api/client";
import { widgets } from "../src/widgets";
import { MyProgressWidget } from "../src/widgets/MyProgressWidget";

const skill = (over: Partial<SkillProficiencyStatus>): SkillProficiencyStatus => ({
  skill_id: "s-1",
  skill_title: "Knife skills",
  category: "Technique",
  latest_score: 72,
  latest_level: "Proficient",
  total_evaluations: 2,
  latest_assessed_at: "2026-10-12T10:00:00Z",
  ...over,
});

const summary = (skills: SkillProficiencyStatus[]): LearnerProgressSummary => ({
  learner_id: "u-1",
  organisation_id: "o-1",
  skills_evaluated: skills.length,
  current_skills: skills,
});

const api = (body: unknown, status = 200) =>
  vi.fn().mockImplementation(async () => ({ ok: status < 400, status, statusText: "", json: async () => body }));

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("skill-progress.my-progress widget", () => {
  it("is exported with the id and permission the role layouts and the contract expect", () => {
    const w = widgets.find((x) => x.id === "skill-progress.my-progress");
    expect(w?.permission).toBe("skill-progress:progress:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(MyProgressWidget);
  });

  it("lists the skills most recently assessed first, with the level in words", async () => {
    const fetchMock = api(
      summary([
        skill({ skill_id: "s-1", skill_title: "Knife skills", latest_assessed_at: "2026-09-01T10:00:00Z" }),
        skill({ skill_id: "s-2", skill_title: "Plating", category: null, latest_level: "Expert", latest_assessed_at: "2026-10-12T10:00:00Z" }),
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<MyProgressWidget role="hospitality-trainee" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Plating")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.textContent).toContain("Plating");
    expect(rows[0]?.textContent).toContain("Expert");
    expect(rows[1]?.textContent).toContain("Knife skills");
    expect(rows[1]?.textContent).toContain("Technique");
    expect(screen.getByLabelText("Progress summary").textContent).toBe("2 skills assessed");
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/skill-progress/me/progress");
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("says how many more skills there are beyond the first six", async () => {
    const many = Array.from({ length: 8 }, (_, i) => skill({ skill_id: `s-${i}`, skill_title: `Skill ${i}` }));
    vi.stubGlobal("fetch", api(summary(many)));
    render(<MyProgressWidget role="dancer" />);
    expect(await screen.findByText("2 more skills")).toBeTruthy();
  });

  it("says there are no assessments yet", async () => {
    vi.stubGlobal("fetch", api(summary([])));
    render(<MyProgressWidget role="dancer" />);
    expect(await screen.findByText("No assessments yet")).toBeTruthy();
  });

  it("says the data is not available when the service is missing, and retries", async () => {
    const fetchMock = api({}, 404);
    vi.stubGlobal("fetch", fetchMock);
    render(<MyProgressWidget role="dancer" />);
    expect(await screen.findByText("Skill progress data is not available yet.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByText("Skill progress data is not available yet.");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not offer a retry when access is refused", async () => {
    vi.stubGlobal("fetch", api({}, 403));
    render(<MyProgressWidget role="dancer" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});
