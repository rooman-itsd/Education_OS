import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { WidgetProps } from "@eos/ui-kit";
import type { Appointment, Injury, NutritionPlan as Plan } from "../src/api/client";
import { widgets } from "../src/widgets";
import { AppointmentsToday, appointmentsToday } from "../src/widgets/AppointmentsToday";
import { AthletesOnPlans } from "../src/widgets/AthletesOnPlans";
import { localDay } from "../src/widgets/format";
import { InjuredAthletes } from "../src/widgets/InjuredAthletes";
import { NutritionPlan } from "../src/widgets/NutritionPlan";
import { PlanReviewsDue } from "../src/widgets/PlanReviewsDue";

const BASE = "/api/v1/sports-nutrition-health";

type Reply = { status: number; body: unknown };
const ok = (body: unknown): Reply => ({ status: 200, body });
const notFound: Reply = { status: 404, body: { detail: "Not Found" } };

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
const page = <T,>(items: T[], total = items.length) => ({ items, total });

const A1 = "3f2a9c7e-1111-4111-8111-111111111111";
const A2 = "8b41d0aa-2222-4222-8222-222222222222";
const A3 = "c0ffee00-3333-4333-8333-333333333333";

const plan = (over: Partial<Plan> & Pick<Plan, "id" | "athlete_id">): Plan => ({
  title: "Competition phase",
  goal: "performance",
  start_date: "2026-10-01",
  status: "active",
  ...over,
});

const injury = (over: Partial<Injury> & Pick<Injury, "id" | "athlete_id" | "status">): Injury => ({
  body_part: "Left hamstring",
  severity: "moderate",
  occurred_on: "2026-10-20",
  ...over,
});

const appointment = (over: Partial<Appointment> & Pick<Appointment, "id" | "scheduled_at">): Appointment => ({
  athlete_id: A1,
  practitioner_id: "p-1",
  appointment_type: "physiotherapy",
  status: "scheduled",
  ...over,
});

/** Saturday 31 Oct 2026, 10:00 in India (UTC+05:30, set in vitest.config.ts). */
const NOW = new Date("2026-10-31T10:00:00+05:30");

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("widget declarations", () => {
  const expected: [string, string, string, string, ComponentType<WidgetProps>][] = [
    ["sports-nutrition-health.nutrition-plan", "sports-nutrition-health:plan:read", "1x1", "panel", NutritionPlan],
    ["sports-nutrition-health.injured-athletes", "sports-nutrition-health:injury:read", "2x1", "list", InjuredAthletes],
    ["sports-nutrition-health.appointments-today", "sports-nutrition-health:appointment:read", "1x1", "list", AppointmentsToday],
    ["sports-nutrition-health.athletes-on-plans", "sports-nutrition-health:plan:read", "1x1", "list", AthletesOnPlans],
    ["sports-nutrition-health.plan-reviews-due", "sports-nutrition-health:plan:read", "1x1", "list", PlanReviewsDue],
  ];

  it("exports the five widgets the athlete, medical-staff and nutritionist layouts name", () => {
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
});

describe("sports-nutrition-health.nutrition-plan", () => {
  it("shows the athlete's active plan, its targets and when the review is due", async () => {
    const fetchMock = stubApi({
      "/nutrition-plans": ok(
        page([
          plan({
            id: "p-1",
            athlete_id: A1,
            title: "Competition phase: sprint squad",
            daily_calories: 2800,
            protein_g: 160,
            carbohydrate_g: 350,
            fat_g: 80,
            meals: [
              { meal: "Breakfast", items: "Oats" },
              { meal: "Lunch", items: "Rice, dal" },
            ],
            end_date: "2026-12-31",
            review_due_on: "2026-11-02",
          }),
        ]),
      ),
    });
    render(<NutritionPlan role="athlete" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    const region = await screen.findByRole("region", { name: "Your nutrition plan" });
    const items = within(region).getAllByRole("listitem");
    expect(within(region).getByRole("list", { name: "Your active plans" })).toBeTruthy();
    expect(items).toHaveLength(1);
    expect(items[0]?.textContent).toContain("Competition phase: sprint squad");
    expect(items[0]?.textContent).toContain("2,800 kcal · Protein 160 g · Carbs 350 g · Fat 80 g");
    expect(items[0]?.textContent).toContain("1 Oct 2026 to 31 Dec 2026");
    expect(items[0]?.textContent).toContain("2 meals");
    expect(items[0]?.textContent).toContain("Performance");
    expect(screen.getByLabelText("Next review").textContent).toBe("Next review2 Nov 2026StatusDue in 2 days");
    expect(urls(fetchMock)).toEqual([`${BASE}/nutrition-plans?status=active&limit=5`]);
    expect((fetchMock.mock.calls[0]?.[1] as unknown as { headers: Record<string, string> }).headers.Authorization).toBe("Bearer test-token");
  });

  it("says when the review is overdue and when no targets or review are set", async () => {
    stubApi({
      "/nutrition-plans": ok(page([plan({ id: "p-1", athlete_id: A1, review_due_on: "2026-10-28" }), plan({ id: "p-2", athlete_id: A1, title: "Recovery" })])),
    });
    render(<NutritionPlan role="athlete" />);
    await screen.findByRole("list", { name: "Your active plans" });
    expect(screen.getByLabelText("Next review").textContent).toContain("Overdue by 3 days");
    expect(screen.getAllByText(/No daily targets set/)).toHaveLength(2);
  });

  it("has an empty state", async () => {
    stubApi({ "/nutrition-plans": ok(page([])) });
    render(<NutritionPlan role="athlete" />);
    expect(await screen.findByText("No active nutrition plan")).toBeTruthy();
  });

  it("says the data is not available yet while the backend is missing, and retries", async () => {
    let mounted = false;
    const fetchMock = stubApi({ "/nutrition-plans": () => (mounted ? ok(page([plan({ id: "p-1", athlete_id: A1 })])) : notFound) });
    render(<NutritionPlan role="athlete" />);
    expect(await screen.findByText("Nutrition and health data is not available yet.")).toBeTruthy();
    mounted = true;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("list", { name: "Your active plans" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe("sports-nutrition-health.injured-athletes", () => {
  const active = [
    injury({ id: "i-1", athlete_id: A1, status: "active", severity: "minor", body_part: "Right ankle", injury_type: "Sprain", expected_return_on: "2026-11-05" }),
    injury({ id: "i-2", athlete_id: A2, status: "active", severity: "severe", expected_return_on: "2026-12-01", occurred_on: "2026-10-10" }),
  ];
  const recovering = [
    { ...injury({ id: "i-3", athlete_id: A3, status: "recovering", expected_return_on: "2026-10-29" }), clinical_notes: "Grade 2 tear, MRI booked" },
    injury({ id: "i-4", athlete_id: A1, status: "recovering", body_part: "Shoulder" }),
  ];

  it("lists active then recovering injuries, most severe first, with the expected return and no clinical notes", async () => {
    const fetchMock = stubApi({
      "/injuries": (url) => ok(url.searchParams.get("status") === "active" ? page(active) : page(recovering)),
    });
    render(<InjuredAthletes role="medical-staff" />);
    const list = await screen.findByRole("list", { name: "Injured athletes" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(4);
    expect(items[0]?.textContent).toContain("Athlete 8b41d0aa");
    expect(items[0]?.textContent).toContain("Left hamstring · Since 10 Oct 2026 · Expected back 1 Dec 2026");
    expect(items[0]?.textContent).toContain("ActiveSevere");
    expect(items[1]?.textContent).toContain("Athlete 3f2a9c7e");
    expect(items[1]?.textContent).toContain("Right ankle sprain · Since 20 Oct 2026 · Expected back 5 Nov 2026");
    expect(items[2]?.textContent).toContain("Athlete c0ffee00");
    expect(items[2]?.textContent).toContain("Was expected back 29 Oct 2026");
    expect(items[2]?.textContent).toContain("RecoveringModerate");
    expect(items[3]?.textContent).toContain("No return date");
    expect(screen.getByLabelText("Injury summary").textContent).toBe("Athletes3Active2Recovering2");
    expect(document.body.textContent).not.toContain("MRI");
    expect(urls(fetchMock).sort()).toEqual([`${BASE}/injuries?status=active&limit=200`, `${BASE}/injuries?status=recovering&limit=200`]);
  });

  it("lists eight injuries and says how many more, counting from the server totals", async () => {
    const many = Array.from({ length: 10 }, (_, i) => injury({ id: `i-${i}`, athlete_id: `a${i}`.padEnd(8, "0"), status: "active" }));
    stubApi({ "/injuries": (url) => ok(url.searchParams.get("status") === "active" ? page(many, 12) : page([], 0)) });
    render(<InjuredAthletes role="medical-staff" />);
    expect(within(await screen.findByRole("list", { name: "Injured athletes" })).getAllByRole("listitem")).toHaveLength(8);
    expect(screen.getByText("and 4 injuries more")).toBeTruthy();
  });

  it("has an empty state", async () => {
    stubApi({ "/injuries": ok(page([])) });
    render(<InjuredAthletes role="medical-staff" />);
    expect(await screen.findByText("No injured athletes")).toBeTruthy();
  });

  it("does not offer a retry that cannot help (403)", async () => {
    stubApi({ "/injuries": { status: 403, body: { code: "forbidden", message: "no" } } });
    render(<InjuredAthletes role="medical-staff" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("sports-nutrition-health.appointments-today", () => {
  it("covers the local day: both UTC days it overlaps, local midnight to midnight", () => {
    expect(NOW.getTimezoneOffset()).toBe(-330);
    const { start, end, utcDays } = localDay(NOW);
    expect(start.toISOString()).toBe("2026-10-30T18:30:00.000Z");
    expect(end.toISOString()).toBe("2026-10-31T18:30:00.000Z");
    expect(utcDays).toEqual(["2026-10-30", "2026-10-31"]);
  });

  it("keeps only appointments in the local day, earliest first, from both UTC days", async () => {
    const fetchMock = stubApi({
      "/appointments": (url) =>
        ok(
          url.searchParams.get("on") === "2026-10-30"
            ? page([
                // 30 Oct 23:00 IST: yesterday, dropped.
                appointment({ id: "x-1", scheduled_at: "2026-10-30T17:30:00Z" }),
                // 31 Oct 01:00 IST: today, although its UTC day is the 30th.
                appointment({ id: "x-2", scheduled_at: "2026-10-30T19:30:00Z", appointment_type: "medical", status: "completed" }),
              ])
            : page([
                appointment({ id: "x-3", scheduled_at: "2026-10-31T09:00:00Z", injury_id: "i-1", duration_minutes: 45, athlete_id: A2 }),
                appointment({ id: "x-4", scheduled_at: "2026-10-31T04:00:00Z", appointment_type: "nutrition", status: "cancelled" }),
                // 1 Nov 00:30 IST: tomorrow, dropped.
                appointment({ id: "x-5", scheduled_at: "2026-10-31T19:00:00Z" }),
              ]),
        ),
    });
    render(<AppointmentsToday role="medical-staff" />);
    const list = await screen.findByRole("list", { name: "Today's appointments" });
    const items = within(list).getAllByRole("listitem");
    expect(items.map((i) => i.querySelector(".eos-row__title")?.textContent)).toEqual([
      "01:00 · Medical",
      "09:30 · Nutrition",
      "14:30 · Physiotherapy",
    ]);
    expect(items[0]?.textContent).toContain("Athlete 3f2a9c7e · 30 min");
    expect(items[0]?.textContent).toContain("Completed");
    expect(items[1]?.textContent).toContain("Cancelled");
    expect(items[2]?.textContent).toContain("Athlete 8b41d0aa · 45 min · Injury follow-up");
    expect(items[2]?.textContent).toContain("Scheduled");
    expect(screen.getByLabelText("Appointments summary").textContent).toBe("Today3Scheduled1Completed1");
    expect(urls(fetchMock).sort()).toEqual([
      `${BASE}/appointments?on=2026-10-30&limit=200`,
      `${BASE}/appointments?on=2026-10-31&limit=200`,
    ]);
  });

  it("does not list an appointment twice", async () => {
    const same = appointment({ id: "x-1", scheduled_at: "2026-10-31T04:00:00Z" });
    stubApi({ "/appointments": ok(page([same])) });
    const rows = await appointmentsToday(new AbortController().signal);
    expect(rows.map((r) => r.id)).toEqual(["x-1"]);
  });

  it("has an empty state", async () => {
    stubApi({ "/appointments": ok(page([])) });
    render(<AppointmentsToday role="medical-staff" />);
    expect(await screen.findByText("No appointments today")).toBeTruthy();
  });

  it("asks to sign in again on 401, without a retry", async () => {
    stubApi({ "/appointments": { status: 401, body: { detail: "expired" } } });
    render(<AppointmentsToday role="medical-staff" />);
    expect(await screen.findByText("Sign in again to see this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("sports-nutrition-health.athletes-on-plans", () => {
  it("lists each athlete with an active plan once, with the plan and its goal", async () => {
    const fetchMock = stubApi({
      "/nutrition-plans": ok(
        page([
          plan({ id: "p-1", athlete_id: A1, title: "Cutting for weigh-in", goal: "weight_loss" }),
          plan({ id: "p-2", athlete_id: A2, title: "Rehab fuelling", goal: "recovery" }),
          plan({ id: "p-3", athlete_id: A1, title: "Older plan" }),
        ]),
      ),
    });
    render(<AthletesOnPlans role="nutritionist" />);
    const list = await screen.findByRole("list", { name: "Athletes on plans" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]?.textContent).toContain("Athlete 3f2a9c7e");
    expect(items[0]?.textContent).toContain("Cutting for weigh-in · +1 plan more");
    expect(items[0]?.textContent).toContain("Weight loss");
    expect(items[1]?.textContent).toContain("Athlete 8b41d0aa");
    expect(items[1]?.textContent).toContain("Recovery");
    expect(screen.getByLabelText("Plan summary").textContent).toBe("Athletes2Active plans3");
    expect(urls(fetchMock)).toEqual([`${BASE}/nutrition-plans?status=active&limit=200`]);
  });

  it("says when more active plans exist than were loaded", async () => {
    const many = Array.from({ length: 10 }, (_, i) => plan({ id: `p-${i}`, athlete_id: `athlete${i}` }));
    stubApi({ "/nutrition-plans": ok(page(many, 250)) });
    render(<AthletesOnPlans role="nutritionist" />);
    expect(within(await screen.findByRole("list", { name: "Athletes on plans" })).getAllByRole("listitem")).toHaveLength(8);
    expect(screen.getByText("and 2 athletes more")).toBeTruthy();
    expect(screen.getByText("Athletes counted from the first 10 active plans.")).toBeTruthy();
  });

  it("has an empty state", async () => {
    stubApi({ "/nutrition-plans": ok(page([])) });
    render(<AthletesOnPlans role="nutritionist" />);
    expect(await screen.findByText("No athletes on a plan")).toBeTruthy();
  });

  it("does not offer a retry that cannot help (403)", async () => {
    stubApi({ "/nutrition-plans": { status: 403, body: { code: "forbidden", message: "no" } } });
    render(<AthletesOnPlans role="nutritionist" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("sports-nutrition-health.plan-reviews-due", () => {
  it("lists active plans with a review due within a week or overdue, most overdue first", async () => {
    const fetchMock = stubApi({
      "/nutrition-plans": ok(
        page([
          plan({ id: "p-1", athlete_id: A1, title: "Bulk", review_due_on: "2026-11-06" }),
          plan({ id: "p-2", athlete_id: A2, title: "Cut", review_due_on: "2026-10-25" }),
          plan({ id: "p-3", athlete_id: A3, title: "Rehab", review_due_on: "2026-10-31" }),
        ]),
      ),
    });
    render(<PlanReviewsDue role="nutritionist" />);
    const list = await screen.findByRole("list", { name: "Plan reviews due" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]?.textContent).toContain("Cut");
    expect(items[0]?.textContent).toContain("Athlete 8b41d0aa · Review on 25 Oct 2026");
    expect(items[0]?.textContent).toContain("Overdue by 6 days");
    expect(items[1]?.textContent).toContain("Due today");
    expect(items[2]?.textContent).toContain("Due in 6 days");
    expect(screen.getByLabelText("Review summary").textContent).toBe("Due3Overdue1Due today1");
    expect(urls(fetchMock)).toEqual([`${BASE}/nutrition-plans?status=active&review_due_before=2026-11-07&limit=200`]);
  });

  it("lists eight and says how many more", async () => {
    const many = Array.from({ length: 10 }, (_, i) => plan({ id: `p-${i}`, athlete_id: A1, review_due_on: `2026-11-0${(i % 6) + 1}` }));
    stubApi({ "/nutrition-plans": ok(page(many)) });
    render(<PlanReviewsDue role="nutritionist" />);
    expect(within(await screen.findByRole("list", { name: "Plan reviews due" })).getAllByRole("listitem")).toHaveLength(8);
    expect(screen.getByText("and 2 plans more")).toBeTruthy();
  });

  it("has an empty state", async () => {
    stubApi({ "/nutrition-plans": ok(page([])) });
    render(<PlanReviewsDue role="nutritionist" />);
    expect(await screen.findByText("No reviews due")).toBeTruthy();
  });

  it("says the data is not available yet when the service cannot be reached, and offers a retry", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    render(<PlanReviewsDue role="nutritionist" />);
    expect(await screen.findByText("Nutrition and health data is not available yet.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("does not put server wording in the headline of a 500", async () => {
    stubApi({ "/nutrition-plans": { status: 500, body: { code: "boom", message: "Traceback ..." } } });
    render(<PlanReviewsDue role="nutritionist" />);
    expect(await screen.findByText("Could not load nutrition and health data.")).toBeTruthy();
    expect(document.body.textContent).not.toContain("Traceback");
  });
});
