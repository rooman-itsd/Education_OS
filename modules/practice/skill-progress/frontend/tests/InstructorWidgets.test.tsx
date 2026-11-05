import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Assessment, FrameworkSummary } from "../src/api/client";
import { widgets } from "../src/widgets";
import { AssessmentsToVerifyWidget } from "../src/widgets/AssessmentsToVerifyWidget";
import { CohortOverviewWidget } from "../src/widgets/CohortOverviewWidget";

const assessment = (over: Partial<Assessment>): Assessment => ({
  id: "a-1",
  learner_id: "11111111-aaaa-bbbb-cccc-dddddddddddd",
  evaluator_id: "e-1",
  skill_id: "s-1",
  assessed_at: "2026-10-12T10:00:00Z",
  overall_score: 72,
  level_achieved: "Proficient",
  status: "submitted",
  ...over,
});

const framework = (over: Partial<FrameworkSummary>): FrameworkSummary => ({
  framework_id: "f-1",
  framework_title: "Kitchen skills",
  learners_assessed: 3,
  levels: [
    { level: "Developing", count: 2 },
    { level: "Proficient", count: 4 },
  ],
  ...over,
});

/** Answers each URL with its body (or a failure status for every URL). */
function api(bodies: { assessments?: unknown; skills?: unknown; summary?: unknown }, status = 200) {
  return vi.fn().mockImplementation(async (url: string) => ({
    ok: status < 400,
    status,
    statusText: "",
    json: async () =>
      url.includes("/reports/framework-summary") ? bodies.summary : url.includes("/skills") ? bodies.skills : bodies.assessments,
  }));
}

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("skill-progress.assessments-due widget", () => {
  it("is exported with the id and permission the role layouts and the contract expect", () => {
    const w = widgets.find((x) => x.id === "skill-progress.assessments-due");
    expect(w?.permission).toBe("skill-progress:assessment:read");
    expect(w?.component).toBe(AssessmentsToVerifyWidget);
  });

  it("lists the submitted assessments with the skill title, learner, date and level", async () => {
    const fetchMock = api({
      assessments: { items: [assessment({}), assessment({ id: "a-2", skill_id: "s-9", level_achieved: "Expert" })], total: 2 },
      skills: { items: [{ id: "s-1", title: "Knife skills" }], total: 1 },
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<AssessmentsToVerifyWidget role="chef-instructor" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Knife skills")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.textContent).toContain("Learner 11111111");
    expect(rows[0]?.textContent).toContain("Proficient");
    expect(rows[1]?.textContent).toContain("Skill"); // a skill missing from the titles list
    expect(rows[1]?.textContent).toContain("Expert");
    expect(screen.getByLabelText("Verification summary").textContent).toBe("2 assessments waiting");
    const urls = fetchMock.mock.calls.map((c) => c[0] as string).sort();
    expect(urls).toEqual(["/api/v1/skill-progress/assessments?status=submitted&limit=6", "/api/v1/skill-progress/skills?limit=100"]);
  });

  it("says how many more are waiting", async () => {
    const six = Array.from({ length: 6 }, (_, i) => assessment({ id: `a-${i}` }));
    vi.stubGlobal("fetch", api({ assessments: { items: six, total: 9 }, skills: { items: [], total: 0 } }));
    render(<AssessmentsToVerifyWidget role="chef-instructor" />);
    expect(await screen.findByText("3 more waiting")).toBeTruthy();
  });

  it("still lists the assessments when the skill titles cannot be loaded", async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string) =>
      url.includes("/skills")
        ? { ok: false, status: 403, statusText: "", json: async () => ({}) }
        : { ok: true, status: 200, statusText: "", json: async () => ({ items: [assessment({})], total: 1 }) },
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<AssessmentsToVerifyWidget role="chef-instructor" />);
    expect(await screen.findByText("1 assessment waiting")).toBeTruthy();
    expect(screen.getAllByRole("listitem")[0]?.textContent).toContain("Skill");
  });

  it("says nothing is waiting", async () => {
    vi.stubGlobal("fetch", api({ assessments: { items: [], total: 0 }, skills: { items: [], total: 0 } }));
    render(<AssessmentsToVerifyWidget role="chef-instructor" />);
    expect(await screen.findByText("Nothing to verify")).toBeTruthy();
  });

  it("says the data is not available when the service is missing, and retries", async () => {
    const fetchMock = api({}, 404);
    vi.stubGlobal("fetch", fetchMock);
    render(<AssessmentsToVerifyWidget role="chef-instructor" />);
    expect(await screen.findByText("Skill progress data is not available yet.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByText("Skill progress data is not available yet.");
  });

  it("does not offer a retry when access is refused", async () => {
    vi.stubGlobal("fetch", api({}, 403));
    render(<AssessmentsToVerifyWidget role="chef-instructor" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});

describe("skill-progress.cohort-overview widget", () => {
  it("is exported with the id and permission the role layout and the contract expect", () => {
    const w = widgets.find((x) => x.id === "skill-progress.cohort-overview");
    expect(w?.permission).toBe("skill-progress:progress:read");
    expect(w?.component).toBe(CohortOverviewWidget);
  });

  it("shows each framework with its learners and the count at each level", async () => {
    const fetchMock = api({
      summary: { items: [framework({}), framework({ framework_id: "f-2", framework_title: "Service", learners_assessed: 1, levels: [] })] },
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<CohortOverviewWidget role="practicum-coordinator" />);
    expect(await screen.findByText("Kitchen skills")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.textContent).toContain("Developing 2 · Proficient 4");
    expect(rows[0]?.textContent).toContain("3 learners");
    expect(rows[1]?.textContent).toContain("1 learner");
    expect(rows[1]?.textContent).toContain("No levels yet");
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/skill-progress/reports/framework-summary");
  });

  it("says how many more frameworks there are beyond the first five", async () => {
    const seven = Array.from({ length: 7 }, (_, i) => framework({ framework_id: `f-${i}`, framework_title: `Framework ${i}` }));
    vi.stubGlobal("fetch", api({ summary: { items: seven } }));
    render(<CohortOverviewWidget role="practicum-coordinator" />);
    expect(await screen.findByText("2 more frameworks")).toBeTruthy();
  });

  it("says there are no assessments yet", async () => {
    vi.stubGlobal("fetch", api({ summary: { items: [] } }));
    render(<CohortOverviewWidget role="practicum-coordinator" />);
    expect(await screen.findByText("No assessments yet")).toBeTruthy();
  });

  it("does not offer a retry when the summary is refused", async () => {
    vi.stubGlobal("fetch", api({}, 403));
    render(<CohortOverviewWidget role="practicum-coordinator" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});
