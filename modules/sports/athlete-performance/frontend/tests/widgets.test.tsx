import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { WidgetProps } from "@eos/ui-kit";
import type { Athlete, FitnessClearance, FitnessTest, Metric, PerformanceHistory, SquadSummaryRow } from "../src/api/client";
import { widgets } from "../src/widgets";
import { BodyCompositionTrend, bodyCompositionMetrics } from "../src/widgets/BodyCompositionTrend";
import { CHECKED, FitnessClearances } from "../src/widgets/FitnessClearances";
import { isoDay } from "../src/widgets/format";
import { PerformanceTrend } from "../src/widgets/PerformanceTrend";
import { SquadOverview } from "../src/widgets/SquadOverview";

const BASE = "/api/v1/athlete-performance";

type Reply = { status: number; body: unknown };
const ok = (body: unknown): Reply => ({ status: 200, body });

/**
 * Stubs fetch by path (without the query): each handler answers a request to that path. A request to a path with
 * no handler fails the test.
 */
function stubApi(routes: Record<string, Reply | ((url: URL) => Reply)>) {
  const fetchMock = vi.fn(async (input: string, _init?: RequestInit) => {
    const url = new URL(input, "http://localhost");
    const route = routes[url.pathname.slice(BASE.length)];
    if (!route) throw new Error(`unexpected request ${input}`);
    const r = typeof route === "function" ? route(url) : route;
    return { ok: r.status < 400, status: r.status, statusText: "", json: async () => r.body };
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const urls = (fetchMock: { mock: { calls: unknown[][] } }) => fetchMock.mock.calls.map((c) => String(c[0]));

const metric = (id: string, name: string, unit: string, direction: Metric["direction"] = "higher_is_better"): Metric => ({ id, name, unit, direction });
const athlete = (id: string, full_name: string): Athlete => ({ id, full_name, primary_discipline_id: "d-1", status: "active" });
const page = <T,>(items: T[], total = items.length) => ({ items, total });

const SPRINT = metric("m-sprint", "100 m sprint", "s", "lower_is_better");
const JUMP = metric("m-jump", "Vertical jump", "cm");
const FAT = metric("m-fat", "Body fat", "%", "lower_is_better");
const MASS = metric("m-mass", "Lean mass", "kg");
const SKIN = metric("m-skin", "Sum of 7 sites", "mm", "lower_is_better");
const LIFT = metric("m-lift", "Weight lifted", "kg");

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("widget declarations", () => {
  const expected: [string, string, string, string, ComponentType<WidgetProps>][] = [
    ["athlete-performance.squad-overview", "athlete-performance:report:read", "2x1", "list", SquadOverview],
    ["athlete-performance.fitness-clearances", "athlete-performance:clearance:read", "2x1", "list", FitnessClearances],
    ["athlete-performance.performance-trend", "athlete-performance:result:read", "2x1", "panel", PerformanceTrend],
    ["athlete-performance.body-composition-trend", "athlete-performance:report:read", "2x1", "panel", BodyCompositionTrend],
  ];

  it("exports the four widgets the coach, medical-staff, athlete and nutritionist layouts name", () => {
    expect(widgets.map((w) => w.id)).toEqual(expected.map((e) => e[0]));
  });

  it.each(expected)("registers %s with permission %s, size %s, kind %s and its component", (id, permission, size, kind, component) => {
    const w = widgets.find((x) => x.id === id);
    expect(w?.permission).toBe(permission);
    expect(w?.size).toBe(size);
    expect(w?.kind).toBe(kind);
    expect(w?.component).toBe(component);
    expect(w?.title).toBeTruthy();
  });

  it("does not export session-plan or training-schedule: plans and sessions are not in this module", () => {
    expect(widgets.map((w) => w.id)).not.toContain("athlete-performance.session-plan");
    expect(widgets.map((w) => w.id)).not.toContain("athlete-performance.training-schedule");
  });
});

describe("athlete-performance.squad-overview", () => {
  const rows: SquadSummaryRow[] = [
    {
      athlete_id: "a-1",
      full_name: "Asha Rao",
      clearance: "cleared",
      metrics: [
        { metric_id: "m-sprint", latest_value: 11.24, trend: "improving" },
        { metric_id: "m-jump", latest_value: 58, trend: "declining" },
      ],
    },
    { athlete_id: "a-2", full_name: "Bilal Khan", clearance: "not_cleared", metrics: [] },
    { athlete_id: "a-3", full_name: "Chitra Iyer", clearance: "restricted", metrics: [{ metric_id: "3f2a9c7e-0000", latest_value: 4, trend: "steady" }] },
  ];

  it("lists the athletes with their metrics' latest values, trends and clearance, and sums them up", async () => {
    const fetchMock = stubApi({ "/reports/squad-summary": ok({ items: rows }), "/metrics": ok(page([SPRINT, JUMP])) });
    render(<SquadOverview role="coach" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    const list = await screen.findByRole("list", { name: "Squad" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]?.textContent).toContain("Asha Rao");
    expect(items[0]?.textContent).toContain("100 m sprint 11.24 s ↑ improving");
    expect(items[0]?.textContent).toContain("Vertical jump 58 cm ↓ declining");
    expect(items[0]?.textContent).toContain("Cleared");
    expect(items[1]?.textContent).toContain("No results yet");
    expect(items[1]?.textContent).toContain("Not cleared");
    expect(items[2]?.textContent).toContain("Metric 3f2a9c7e 4 → steady");
    expect(items[2]?.textContent).toContain("Restricted");
    const summary = screen.getByLabelText("Squad summary");
    expect(summary.textContent).toBe("Athletes3Improving1Declining1Not cleared1");
    expect(urls(fetchMock).sort()).toEqual([`${BASE}/metrics?limit=200`, `${BASE}/reports/squad-summary`]);
    expect((fetchMock.mock.calls[0]?.[1] as unknown as { headers: Record<string, string> }).headers.Authorization).toBe("Bearer test-token");
  });

  it("lists eight athletes and says how many more", async () => {
    const many = Array.from({ length: 11 }, (_, i) => ({ athlete_id: `a-${i}`, full_name: `Athlete ${i}`, metrics: [] }));
    stubApi({ "/reports/squad-summary": ok({ items: many }), "/metrics": ok(page([])) });
    render(<SquadOverview role="coach" />);
    expect(within(await screen.findByRole("list", { name: "Squad" })).getAllByRole("listitem")).toHaveLength(8);
    expect(screen.getByText("and 3 athletes more")).toBeTruthy();
  });

  it("has an empty state", async () => {
    stubApi({ "/reports/squad-summary": ok({ items: [] }), "/metrics": ok(page([])) });
    render(<SquadOverview role="coach" />);
    expect(await screen.findByText("No athletes yet")).toBeTruthy();
  });

  it("does not offer a retry that cannot help (403)", async () => {
    stubApi({ "/reports/squad-summary": { status: 403, body: { code: "forbidden", message: "no" } }, "/metrics": ok(page([])) });
    render(<SquadOverview role="coach" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("says the data is not available yet while the backend is missing, and retries", async () => {
    let mounted = false;
    const fetchMock = stubApi({
      "/reports/squad-summary": () => (mounted ? ok({ items: rows }) : { status: 404, body: { detail: "Not Found" } }),
      "/metrics": () => (mounted ? ok(page([SPRINT, JUMP])) : { status: 404, body: { detail: "Not Found" } }),
    });
    render(<SquadOverview role="coach" />);
    expect(await screen.findByText("Athlete performance data is not available yet.")).toBeTruthy();
    mounted = true;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("list", { name: "Squad" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });
});

describe("athlete-performance.fitness-clearances", () => {
  const team = [athlete("a-1", "Asha Rao"), athlete("a-2", "Bilal Khan"), athlete("a-3", "Chitra Iyer"), athlete("a-4", "Dev Nair"), athlete("a-5", "Esha Paul")];
  const clearances: Record<string, FitnessClearance> = {
    "a-1": { athlete_id: "a-1", status: "cleared", valid_until: isoDay(120) },
    "a-2": { athlete_id: "a-2", status: "not_cleared" },
    "a-3": { athlete_id: "a-3", status: "restricted", valid_until: isoDay(30), restrictions: "No contact drills", set_at: "2026-10-01T09:00:00Z" },
    "a-4": { athlete_id: "a-4", status: "cleared", valid_until: isoDay(5), set_at: "2026-10-01T09:00:00Z" },
    "a-5": { athlete_id: "a-5", status: "not_cleared", valid_until: isoDay(-3), set_at: "2026-01-01T09:00:00Z" },
  };
  const routes = (list: Athlete[], total = list.length) => ({
    "/athletes": ok(page(list, total)),
    ...Object.fromEntries(list.map((a) => [`/athletes/${a.id}/clearance`, ok(clearances[a.id] ?? { athlete_id: a.id, status: "cleared" })])),
  });

  it("shows each athlete's status, not cleared and restricted first, and flags clearances lapsing soon", async () => {
    const fetchMock = stubApi(routes(team));
    render(<FitnessClearances role="medical-staff" />);
    const items = within(await screen.findByRole("list", { name: "Fitness clearances" })).getAllByRole("listitem");
    expect(items.map((li) => li.textContent?.split(/(?=Valid|Lapsed|No clearance|No contact)/)[0])).toEqual([
      "BKBilal Khan",
      "EPEsha Paul",
      "CIChitra Iyer",
      "DNDev Nair",
      "ARAsha Rao",
    ]);
    expect(items[0]?.textContent).toContain("No clearance recorded");
    expect(items[0]?.textContent).toContain("Not cleared");
    expect(items[1]?.textContent).toContain("Lapsed on");
    expect(items[2]?.textContent).toContain("No contact drills · Valid until");
    expect(items[2]?.textContent).toContain("Restricted");
    expect(items[3]?.textContent).toContain("Lapsing soon");
    expect(items[4]?.textContent).not.toContain("Lapsing soon");
    expect(screen.getByLabelText("Clearance summary").textContent).toBe("Cleared2Restricted1Not cleared2Lapsing soon1");
    expect(urls(fetchMock)[0]).toBe(`${BASE}/athletes?status=active&limit=${CHECKED}`);
    expect(fetchMock).toHaveBeenCalledTimes(1 + team.length);
    expect(screen.queryByText(/Checked the first/)).toBeNull();
  });

  it("checks at most the first page of athletes and says so", async () => {
    stubApi(routes(team, 42));
    render(<FitnessClearances role="medical-staff" />);
    expect(await screen.findByText("Checked the first 5 of 42 active athletes, by name.")).toBeTruthy();
  });

  it("has an empty state", async () => {
    stubApi({ "/athletes": ok(page([])) });
    render(<FitnessClearances role="medical-staff" />);
    expect(await screen.findByText("No athletes yet")).toBeTruthy();
  });

  it("does not offer a retry that cannot help (403)", async () => {
    stubApi({ "/athletes": { status: 403, body: { code: "forbidden", message: "no" } } });
    render(<FitnessClearances role="medical-staff" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("says the data is not available yet while the backend is missing", async () => {
    stubApi({ "/athletes": { status: 404, body: { detail: "Not Found" } } });
    render(<FitnessClearances role="medical-staff" />);
    expect(await screen.findByText("Athlete performance data is not available yet.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});

describe("athlete-performance.performance-trend", () => {
  const me = athlete("a-me", "Asha Rao");
  const history = (metricId: string, values: [string, number][], benchmark?: PerformanceHistory["benchmark"]): PerformanceHistory => ({
    athlete_id: me.id,
    metric_id: metricId,
    points: values.map(([at, value]) => ({ at, value, source: "result" })),
    benchmark,
  });
  const histories: Record<string, PerformanceHistory> = {
    "m-sprint": history(
      "m-sprint",
      [
        ["2026-01-10T09:00:00Z", 11.6],
        ["2026-05-10T09:00:00Z", 11.4],
        ["2026-10-20T09:00:00Z", 11.24],
      ],
      { id: "b-1", metric_id: "m-sprint", level: "state", target_value: 11 },
    ),
    "m-jump": history("m-jump", [
      ["2026-02-01T09:00:00Z", 60],
      ["2026-09-01T09:00:00Z", 57.5],
    ]),
    "m-fat": history("m-fat", [["2026-08-01T00:00:00Z", 14]]),
  };

  function routes(results: { metric_id: string; recorded_at: string }[], assessments: { assessed_on: string; metric_ids: string[] }[]) {
    return {
      "/athletes": ok(page([me])),
      "/metrics": ok(page([SPRINT, JUMP, FAT, MASS, SKIN])),
      "/results": ok(page(results.map((r, i) => ({ id: `r-${i}`, athlete_id: me.id, value: 1, context: "training", ...r })))),
      "/assessments": ok(
        page(assessments.map((a, i) => ({ id: `as-${i}`, athlete_id: me.id, fitness_test_id: "t-1", assessed_on: a.assessed_on, measurements: a.metric_ids.map((metric_id) => ({ metric_id, value: 1 })) }))),
      ),
      [`/athletes/${me.id}/history`]: (url: URL) => ok(histories[url.searchParams.get("metric_id")!] ?? history(url.searchParams.get("metric_id")!, [])),
    };
  }

  it("shows the athlete's own metrics, most recently measured first, with the change judged by direction and the benchmark", async () => {
    const fetchMock = stubApi(
      routes(
        [
          { metric_id: "m-sprint", recorded_at: "2026-10-20T09:00:00Z" },
          { metric_id: "m-jump", recorded_at: "2026-09-01T09:00:00Z" },
        ],
        [{ assessed_on: "2026-08-01", metric_ids: ["m-fat"] }],
      ),
    );
    render(<PerformanceTrend role="athlete" />);
    const list = await screen.findByRole("list", { name: "Your results by metric" });
    const items = within(list).getAllByRole("listitem");
    expect(items.map((li) => li.getAttribute("aria-label"))).toEqual(["100 m sprint", "Vertical jump", "Body fat"]);
    const sprint = within(list).getByRole("listitem", { name: "100 m sprint" });
    expect(sprint.textContent).toContain("11.24 s");
    expect(sprint.textContent).toContain("3 results");
    expect(sprint.textContent).toContain("Target 11 s (state)");
    expect(sprint.textContent).toContain("Improved 0.36 s since 10 Jan 2026");
    expect(within(list).getByRole("listitem", { name: "Vertical jump" }).textContent).toContain("Down 2.5 cm since 1 Feb 2026");
    expect(within(list).getByRole("listitem", { name: "Body fat" }).textContent).toContain("1 result");
    const called = urls(fetchMock);
    expect(called[0]).toBe(`${BASE}/athletes?limit=1`);
    expect(called).toContain(`${BASE}/results?athlete_id=a-me&limit=200`);
    expect(called).toContain(`${BASE}/assessments?athlete_id=a-me&limit=50`);
    expect(called).toContain(`${BASE}/athletes/a-me/history?metric_id=m-sprint`);
  });

  it("asks for the history of at most four metrics", async () => {
    const fetchMock = stubApi(
      routes(
        ["m-sprint", "m-jump", "m-fat", "m-mass", "m-skin"].map((metric_id, i) => ({ metric_id, recorded_at: `2026-0${i + 1}-01T00:00:00Z` })),
        [],
      ),
    );
    render(<PerformanceTrend role="athlete" />);
    await screen.findByRole("list", { name: "Your results by metric" });
    const historyCalls = urls(fetchMock).filter((u) => u.includes("/history"));
    expect(historyCalls).toHaveLength(4);
    expect(historyCalls.some((u) => u.endsWith("m-sprint"))).toBe(false);
  });

  it("has an empty state when the signed-in user has no athlete profile", async () => {
    const fetchMock = stubApi({ "/athletes": ok(page([])) });
    render(<PerformanceTrend role="athlete" />);
    expect(await screen.findByText("No results recorded yet")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("has the same empty state when nothing is recorded yet", async () => {
    stubApi(routes([], []));
    render(<PerformanceTrend role="athlete" />);
    expect(await screen.findByText("No results recorded yet")).toBeTruthy();
  });

  it("does not offer a retry that cannot help (403)", async () => {
    stubApi({ "/athletes": { status: 403, body: { code: "forbidden", message: "no" } } });
    render(<PerformanceTrend role="athlete" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("athlete-performance.body-composition-trend", () => {
  const tests: FitnessTest[] = [
    { id: "t-body", name: "Body composition check", metric_ids: ["m-skin"] },
    { id: "t-pre", name: "Pre-season fitness test", metric_ids: ["m-jump"] },
  ];

  it("counts metrics measured by a body composition test or named as body composition, and nothing else", () => {
    const body = bodyCompositionMetrics([SPRINT, JUMP, FAT, MASS, SKIN, LIFT, metric("m-w", "Weight", "kg"), metric("m-bmi", "BMI", "")], tests);
    expect([...body.keys()].sort()).toEqual(["m-bmi", "m-fat", "m-mass", "m-skin", "m-w"]);
  });

  const rows: SquadSummaryRow[] = [
    {
      athlete_id: "a-1",
      full_name: "Asha Rao",
      metrics: [
        { metric_id: "m-fat", latest_value: 14, trend: "improving" },
        { metric_id: "m-sprint", latest_value: 11.2, trend: "declining" },
      ],
    },
    {
      athlete_id: "a-2",
      full_name: "Bilal Khan",
      metrics: [
        { metric_id: "m-fat", latest_value: 18, trend: "declining" },
        { metric_id: "m-skin", latest_value: 62.5, trend: "steady" },
      ],
    },
    { athlete_id: "a-3", full_name: "Chitra Iyer", metrics: [{ metric_id: "m-jump", latest_value: 50, trend: "declining" }] },
  ];

  it("sums up each body composition metric and lists the athletes whose body composition is declining", async () => {
    const fetchMock = stubApi({
      "/reports/squad-summary": ok({ items: rows }),
      "/metrics": ok(page([SPRINT, JUMP, FAT, SKIN])),
      "/fitness-tests": ok(page(tests)),
    });
    render(<BodyCompositionTrend role="nutritionist" />);
    const list = await screen.findByRole("list", { name: "Body composition by metric" });
    const items = within(list).getAllByRole("listitem");
    expect(items.map((li) => li.getAttribute("aria-label"))).toEqual(["Body fat", "Sum of 7 sites"]);
    expect(items[0]?.textContent).toContain("2 athletes measured · Average 16%");
    expect(items[0]?.textContent).toContain("1 improving");
    expect(items[0]?.textContent).toContain("1 declining");
    expect(items[1]?.textContent).toContain("1 athlete measured · Average 62.5 mm");
    expect(items[1]?.textContent).toContain("1 steady");
    const review = within(screen.getByRole("list", { name: "Athletes with declining body composition" })).getAllByRole("listitem");
    expect(review).toHaveLength(1);
    expect(review[0]?.textContent).toContain("Bilal Khan");
    expect(review[0]?.textContent).toContain("Body fat 18%");
    expect(urls(fetchMock).sort()).toEqual([`${BASE}/fitness-tests?limit=200`, `${BASE}/metrics?limit=200`, `${BASE}/reports/squad-summary`]);
  });

  it("has an empty state when no body composition metric has values", async () => {
    stubApi({ "/reports/squad-summary": ok({ items: rows }), "/metrics": ok(page([SPRINT, JUMP])), "/fitness-tests": ok(page([])) });
    render(<BodyCompositionTrend role="nutritionist" />);
    expect(await screen.findByText("No body composition results yet")).toBeTruthy();
  });

  it("does not offer a retry that cannot help (403)", async () => {
    stubApi({
      "/reports/squad-summary": { status: 403, body: { code: "forbidden", message: "no" } },
      "/metrics": ok(page([])),
      "/fitness-tests": ok(page([])),
    });
    render(<BodyCompositionTrend role="nutritionist" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
