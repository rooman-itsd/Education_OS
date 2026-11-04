import { expect, test } from "@playwright/test";
import { organisationWithUser, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

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
 *   athlete-performance.training-schedule is not built at all (see NOT_BUILT);
 * - the data journeys are fixme: each needs a sports module enabled, and the athlete's scoping in
 *   sports-nutrition-health and tournament-events needs the athlete-performance.athlete.registered event.
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
  { id: "lms.course-materials", module: "academics/lms", batch: "#326" },
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
  { id: "transport.notices", module: "campus-life/transport", batch: "#338" },
  { id: "library.loans", module: "campus-life/library", batch: "#338" },
  // The athlete's own widgets.
  { id: "athlete-performance.training-schedule", module: "sports/athlete-performance", batch: "#330" },
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
  "athlete-performance.training-schedule":
    "not built: training plans and sessions belong to training-video-analysis, and sprint batch #330 proposes moving this widget there",
};
const why = (w: LayoutWidget) => NOT_BUILT[w.id] ?? waitingFor(w);

const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the athlete user. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  user = await organisationWithUser(request, { academyType: "sports-college", role: "athlete" });
  await standardPlan(request, user.organisation.id);
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
// its module in both modules.enabled.yaml files; write them as the finance-staff data journeys are written then.
test.describe("with sports data", () => {
  test.fixme("athlete-performance.performance-trend shows the results a coach records for the athlete", async () => {
    // sports/athlete-performance (sprint batch #330, PR #385). Set up with organisationAdmin + addUser so a coach
    // exists beside the athlete. The coach (profile role coach: catalogue:read, athlete:write, result:record) needs a
    // discipline and a metric, which only athlete-performance-admin (org-admin) may write: as the org admin
    // POST /athlete-performance/disciplines { name: "Athletics", category: "individual", active: true } and
    // POST /athlete-performance/metrics { name: "100 m sprint", unit: "s", direction: "lower_is_better", discipline_id }.
    // Then as the coach POST /athlete-performance/athletes { user_id: <athlete user id>, full_name, primary_discipline_id,
    // coach_id: <coach id>, status: "active" } and two POST /athlete-performance/results { athlete_id, metric_id,
    // value: 11.9 then 11.6, recorded_at: two days, context: "trial" }.
    // Expect, signed in as the athlete: "No results recorded yet" is gone; the panel names "100 m sprint" with the
    // latest value 11.6 s and shows the trend as improving (lower is better).
  });

  test.fixme("sports-nutrition-health.nutrition-plan shows the plan a nutritionist activates for the athlete", async () => {
    // sports/sports-nutrition-health (sprint batch #330, PR #389). The athlete must first be registered in
    // athlete-performance as above: sports-nutrition-health scopes the athlete's own plans by the athlete id it
    // learns from the athlete-performance.athlete.registered event, so the event has to reach it through
    // platform/event-bus (the e2e API runs the bus in-process; confirm the subscriber is wired before writing this).
    // As a nutritionist (addUser "nutritionist": plan:write) POST /sports-nutrition-health/nutrition-plans
    // { athlete_id, title: "Pre-season build", goal: "performance", daily_calories: 3200, protein_g: 160,
    // carbohydrate_g: 420, fat_g: 90, start_date: dayFromNow(0), review_due_on: dayFromNow(14), status: "active" }.
    // Expect, as the athlete: "No active nutrition plan" is gone; the panel shows "Pre-season build", the goal, the
    // daily calories and macros, and the review date.
  });

  test.fixme("tournament-events.upcoming lists a published tournament the athlete is entered in", async () => {
    // sports/tournament-events (sprint batch #330, PR #388). Creating and publishing a tournament needs
    // tournament-events:tournament:write and :publish (tournament-events-admin; check that org-admin holds it).
    // POST /tournament-events/tournaments { name: "Inter-University Athletics Meet", discipline: "Athletics",
    // level: "inter_university", format: "heats_and_finals", start_date: dayFromNow(10), end_date: dayFromNow(12),
    // venue: "Main stadium", hosting: "home" }, then as the coach (entry:write) POST
    // /tournaments/{id}/entries { category: "100 m men", athlete_ids: [<athlete id>], status: "confirmed" } and
    // POST /tournaments/{id}/publish. The athlete id comes from athlete-performance, so again the
    // athlete-performance.athlete.registered event must have reached tournament-events.
    // Expect, as the athlete: "No upcoming tournaments" is gone; the row shows the meet's name, dates and venue and
    // marks the athlete's entry ("100 m men").
  });
});
