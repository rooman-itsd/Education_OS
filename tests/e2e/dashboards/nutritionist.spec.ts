import { expect, test } from "@playwright/test";
import { organisationWithUser, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Nutritionist dashboard (layout platform/identity/config/dashboards/nutritionist.yaml; the role exists in the
 * sports-college profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a nutritionist signs in and lands on their dashboard;
 * - for every widget whose module is in apps/frontend/config/modules.enabled.yaml: the panel renders by its
 *   registered title and shows its empty state, says its data is not available while the backend is missing, or
 *   says the role has no access;
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it;
 * - the data journeys are fixme: each needs a sports module enabled, and sports-nutrition-health learns athletes
 *   only from the athlete-performance.athlete.registered event.
 *
 * Every widget is a sports module and the sports suite is the profile's one specialized suite, which the Trial plan
 * includes, so the organisation stays on Trial. The empty-state tests run before any data is created (serial mode).
 * Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Nutritionist";

const WIDGETS: LayoutWidget[] = [
  {
    id: "sports-nutrition-health.athletes-on-plans",
    module: "sports/sports-nutrition-health",
    batch: "#330",
    title: "Athletes on plans",
    probe: "/sports-nutrition-health/nutrition-plans?status=active&limit=200",
    empty: "No athletes on a plan",
    unavailable: "Nutrition and health data is not available yet.",
  },
  {
    id: "sports-nutrition-health.plan-reviews-due",
    module: "sports/sports-nutrition-health",
    batch: "#330",
    title: "Plan reviews due",
    probe: "/sports-nutrition-health/nutrition-plans?status=active&limit=1",
    empty: "No reviews due",
    unavailable: "Nutrition and health data is not available yet.",
  },
  {
    // athlete-performance's contract grants nothing to the nutritionist profile role today (only coach, medical-staff,
    // athlete, management and org-admin), so once enabled this probe may answer 403 and the panel say
    // "You do not have access to this." until the contract grants report:read to nutritionist.
    id: "athlete-performance.body-composition-trend",
    module: "sports/athlete-performance",
    batch: "#330",
    title: "Body composition trend",
    probe: "/athlete-performance/reports/squad-summary",
    empty: "No body composition results yet",
    unavailable: "Athlete performance data is not available yet.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the nutritionist. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  user = await organisationWithUser(request, { academyType: "sports-college", role: "nutritionist" });
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a nutritionist signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("nutritionist widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the nutritionist layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, says its data is not available yet, or says the role has no access", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the nutritionist layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    for (const w of SHIPPED) await expectBody(page, w, status[w.id] ?? 0);
  });

  for (const w of WIDGETS.filter((w) => !shipped(w))) {
    test(`${w.id} renders once ${w.module} ships`, async ({ page }) => {
      test.skip(!shipped(w), waitingFor(w));
      // The shell renders an unregistered id as a "Not built yet" placeholder titled with the id itself.
      await signIn(page, user);
      await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
      await expect(widget(page, w.id)).toHaveCount(0);
    });
  }
});

// Backend-dependent: these need their module's API to create the data through, so nothing here is faked. Each needs
// its module in both modules.enabled.yaml files; write them as the finance-staff data journeys are written then.
// Every one starts from athletes registered in athlete-performance: set up with organisationAdmin + addUser, as the
// org admin POST /athlete-performance/disciplines and, as a coach, POST /athlete-performance/athletes for "Asha Rao"
// and "Ben Okafor". sports-nutrition-health accepts those athlete ids only once the
// athlete-performance.athlete.registered event has reached it through platform/event-bus.
test.describe("with sports data", () => {
  test.fixme("sports-nutrition-health athletes-on-plans and plan-reviews-due show an active plan due for review in 3 days", async () => {
    // sports/sports-nutrition-health (sprint batch #330, PR #389). As the nutritionist (plan:write through
    // sports-nutrition-health-nutritionist) POST /sports-nutrition-health/nutrition-plans { athlete_id: <Asha>,
    // title: "Cutting phase", goal: "weight_loss", daily_calories: 2200, start_date: dayFromNow(-14),
    // review_due_on: dayFromNow(3), status: "active" }, and a "draft" plan for Ben that must count in neither.
    // Expect: athletes-on-plans drops "No athletes on a plan" and lists "Asha Rao" with "Cutting phase" and the goal;
    // plan-reviews-due drops "No reviews due" and lists the plan as due in 3 days. After
    // POST /nutrition-plans/{id}/reviews { reviewed_on: dayFromNow(0), outcome, next_review_on: dayFromNow(28) }
    // it leaves plan-reviews-due.
  });

  test.fixme("athlete-performance.body-composition-trend shows body-fat results for two athletes", async () => {
    // sports/athlete-performance (sprint batch #330, PR #385). As the org admin POST /athlete-performance/metrics
    // { name: "Body fat", unit: "%", direction: "lower_is_better" }; as the coach POST /athlete-performance/results
    // { athlete_id, metric_id, value, recorded_at, context: "training" } twice for each athlete (Asha 18.0 then 16.5,
    // Ben 14.0 then 14.4). Needs the nutritionist to hold athlete-performance report:read (see the WIDGETS note).
    // Expect: "No body composition results yet" is gone; both athletes appear with their latest body fat, Asha's
    // trend improving and Ben's worsening.
  });
});
