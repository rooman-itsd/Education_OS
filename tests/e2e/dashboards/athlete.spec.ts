import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, dayFromNow, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Athlete dashboard (layout platform/identity/config/dashboards/athlete.yaml, which extends the Student layout; the
 * role exists in the sports-college profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: an athlete user signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Student ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml: the panel renders by its registered title and shows its empty
 *   state, or says its data is not available while the backend is missing (the athlete holds the student role's
 *   permissions through `extends`);
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it;
 * - the data journeys need their module enabled; the athlete is registered in athlete-performance once (in the
 *   performance-trend journey) and reused by the sports-nutrition-health and tournament-events journeys, which scope
 *   the athlete's own records by the athlete id they learn from the athlete-performance.athlete.registered event.
 *
 * The sports suite is the profile's one specialized suite, so the Trial plan already includes it; the inherited
 * fees-accounts and hostel widgets are not in Trial, so the super admin moves the organisation to Standard first.
 * The empty-state tests run before any data is created (serial mode). Loading states are covered by the modules'
 * unit tests, not here.
 */

const TITLE = "Athlete";

const WIDGETS: LayoutWidget[] = [
  // Inherited from the Student layout (extends: student).
  { id: "timetable-attendance.today", module: "academics/timetable-attendance", batch: "#325" },
  { id: "timetable-attendance.attendance-summary", module: "academics/timetable-attendance", batch: "#325" },
  { id: "examinations.upcoming-assessments", module: "academics/examinations", batch: "#325" },
  {
    id: "lms.course-materials",
    module: "academics/lms",
    batch: "#326",
    title: "Course materials",
    probe: "/lms/me/course-materials?limit=1",
    empty: "No new course materials",
    unavailable: "Course data is not available yet.",
  },

  {
    id: "fees-accounts.fee-dues",
    module: "finance-operations/fees-accounts",
    batch: "#107",
    title: "Fee dues",
    probe: "/fees-accounts/me/dues",
    empty: "No fees due",
    unavailable: "Fee data is not available yet.",
  },
  {
    id: "hostel.notices",
    module: "campus-life/hostel",
    batch: "#338",
    title: "Hostel notices",
    probe: "/hostel/me/notices?limit=1",
    empty: "No hostel notices right now",
    unavailable: "Could not load hostel notices",
    forbidden: "Could not load hostel notices",
  },
  {
    // Texts of NoticesWidget.tsx in PR #473 (sprint batch #338).
    id: "transport.notices",
    module: "campus-life/transport",
    batch: "#338",
    title: "Transport notices",
    probe: "/transport/me/notices?limit=1",
    empty: "No transport notices right now",
    unavailable: "Transport data is not available yet.",
  },
  {
    // Texts of LoansWidget.tsx in PR #476 (sprint batch #338).
    id: "library.loans",
    module: "campus-life/library",
    batch: "#338",
    title: "Library loans",
    probe: "/library/me/loans",
    empty: "No books on loan",
    unavailable: "Library data is not available yet.",
  },
  // The athlete's own widgets.
  {
    id: "training-video-analysis.training-schedule",
    module: "sports/training-video-analysis",
    batch: "#330",
    title: "Training schedule",
    probe: "/training-video-analysis/sessions?status=scheduled&limit=1",
    empty: "No training sessions scheduled",
    unavailable: "Training video data is not available yet.",
  },
  {
    id: "athlete-performance.performance-trend",
    module: "sports/athlete-performance",
    batch: "#330",
    title: "Performance trend",
    probe: "/athlete-performance/athletes",
    empty: "No results recorded yet",
    unavailable: "Athlete performance data is not available yet.",
  },
  {
    id: "sports-nutrition-health.nutrition-plan",
    module: "sports/sports-nutrition-health",
    batch: "#330",
    title: "Nutrition plan",
    probe: "/sports-nutrition-health/nutrition-plans?status=active&limit=5",
    empty: "No active nutrition plan",
    unavailable: "Nutrition and health data is not available yet.",
  },
  {
    id: "tournament-events.upcoming",
    module: "sports/tournament-events",
    batch: "#330",
    title: "Upcoming tournaments",
    probe: "/tournament-events/tournaments?status=published&limit=5",
    empty: "No upcoming tournaments",
    unavailable: "Tournament data is not available yet.",
  },
];

/**
 * Widgets the layout lists that no v1 batch builds, and why: they skip with this reason instead of waitingFor's.
 * (A local helper: widgets.ts has no notion of a widget that is not planned.)
 */
const NOT_BUILT: Record<string, string> = {
};
const why = (w: LayoutWidget) => NOT_BUILT[w.id] ?? waitingFor(w);

const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let admin: DashboardUser;
let user: DashboardUser;
/** Per shipped widget id: what its GET answered the athlete user. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "sports-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "athlete");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`an athlete signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("athlete widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the athlete layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the athlete layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    for (const w of SHIPPED) await expectBody(page, w, status[w.id] ?? 0);
  });

  for (const w of WIDGETS.filter((w) => !shipped(w))) {
    test(`${w.id} renders once ${w.module} ships`, async ({ page }) => {
      test.skip(!shipped(w), why(w));
      // The shell renders an unregistered id as a "Not built yet" placeholder titled with the id itself.
      await signIn(page, user);
      await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
      await expect(widget(page, w.id)).toHaveCount(0);
    });
  }
});

// Backend-dependent: these need their module's API to create the data through, so nothing here is faked. Each needs
// its module in both modules.enabled.yaml files; written as the finance-staff data journeys are written.
//
// The athlete is registered in athlete-performance once, in the first test (serial mode): sports-nutrition-health and
// tournament-events scope the athlete's own records by the athlete id they learn from the
// athlete-performance.athlete.registered event through platform/event-bus, so both later tests reuse this same
// registration rather than creating a second one for the same user.
let coach: DashboardUser;
let athlete: { id: string } | undefined;

test.describe("with sports data", () => {
  test("athlete-performance.performance-trend shows the results a coach records for the athlete", async ({ page, request }) => {
    const w = byId("athlete-performance.performance-trend");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the athlete-performance API answered ${status[w.id]} to the athlete role`);
    coach = await addUser(request, admin, "coach");
    const discipline = await created<{ id: string }>(request, admin, "/athlete-performance/disciplines", {
      name: "Athletics",
      category: "individual",
      active: true,
    });
    const metric = await created<{ id: string }>(request, admin, "/athlete-performance/metrics", {
      name: "100 m sprint",
      unit: "s",
      direction: "lower_is_better",
      discipline_id: discipline.id,
    });
    athlete = await created<{ id: string }>(request, coach, "/athlete-performance/athletes", {
      user_id: user.id,
      full_name: "E2E athlete",
      primary_discipline_id: discipline.id,
      coach_id: coach.id,
      status: "active",
    });
    await created(request, coach, "/athlete-performance/results", {
      athlete_id: athlete.id,
      metric_id: metric.id,
      value: 11.9,
      recorded_at: `${dayFromNow(-2)}T09:00:00Z`,
      context: "trial",
    });
    await created(request, coach, "/athlete-performance/results", {
      athlete_id: athlete.id,
      metric_id: metric.id,
      value: 11.6,
      recorded_at: `${dayFromNow(0)}T09:00:00Z`,
      context: "trial",
    });
    await signIn(page, user);
    const panel = widget(page, "Performance trend");
    await expect(panel.getByText("No results recorded yet")).toHaveCount(0);
    const trend = panel.getByRole("listitem", { name: "100 m sprint" });
    await expect(trend.getByText("11.6 s")).toBeVisible();
    await expect(trend.getByText(/^Improved 0\.3 s since /)).toBeVisible();
  });

  test("sports-nutrition-health.nutrition-plan shows the plan a nutritionist activates for the athlete", async ({ page, request }) => {
    const w = byId("sports-nutrition-health.nutrition-plan");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the sports-nutrition-health API answered ${status[w.id]} to the athlete role`);
    test.skip(!athlete, "athlete-performance.performance-trend did not register an athlete (its own widget is not shipped yet)");
    const nutritionist = await addUser(request, admin, "nutritionist");
    await created(request, nutritionist, "/sports-nutrition-health/nutrition-plans", {
      athlete_id: athlete!.id,
      title: "Pre-season build",
      goal: "performance",
      daily_calories: 3200,
      protein_g: 160,
      carbohydrate_g: 420,
      fat_g: 90,
      start_date: dayFromNow(0),
      review_due_on: dayFromNow(14),
      status: "active",
    });
    await signIn(page, user);
    const panel = widget(page, "Nutrition plan");
    await expect(panel.getByText("No active nutrition plan")).toHaveCount(0);
    await expect(panel.getByText("Pre-season build")).toBeVisible();
    await expect(panel.getByText("Performance")).toBeVisible();
    await expect(panel.getByText(/3,200 kcal/)).toBeVisible();
    await expect(panel.getByText(/Protein 160 g/)).toBeVisible();
  });

  test("tournament-events.upcoming lists a published tournament the athlete is entered in", async ({ page, request }) => {
    const w = byId("tournament-events.upcoming");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the tournament-events API answered ${status[w.id]} to the athlete role`);
    test.skip(!athlete, "athlete-performance.performance-trend did not register an athlete (its own widget is not shipped yet)");
    const tournament = await created<{ id: string }>(request, admin, "/tournament-events/tournaments", {
      name: "Inter-University Athletics Meet",
      discipline: "Athletics",
      level: "inter_university",
      format: "heats_and_finals",
      start_date: dayFromNow(10),
      end_date: dayFromNow(12),
      venue: "Main stadium",
      hosting: "home",
    });
    await created(request, coach, `/tournament-events/tournaments/${tournament.id}/entries`, {
      category: "100 m men",
      athlete_ids: [athlete!.id],
      status: "confirmed",
    });
    await created(request, admin, `/tournament-events/tournaments/${tournament.id}/publish`, {});
    await signIn(page, user);
    const panel = widget(page, "Upcoming tournaments");
    await expect(panel.getByText("No upcoming tournaments")).toHaveCount(0);
    await expect(panel.getByText("Inter-University Athletics Meet")).toBeVisible();
    await expect(panel.getByText("Main stadium", { exact: false })).toBeVisible();
    await expect(panel.getByText("Entered")).toBeVisible();
  });
});
