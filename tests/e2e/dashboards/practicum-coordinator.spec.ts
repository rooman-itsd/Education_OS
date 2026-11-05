import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Practicum Coordinator dashboard (layout platform/identity/config/dashboards/practicum-coordinator.yaml; the role exists in the
 * teacher-education-college profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a practicum coordinator signs in and lands on their dashboard;
 * - for every widget of the layout whose module is in apps/frontend/config/modules.enabled.yaml and
 *   exports the widget: the panel renders by its registered title and shows its empty state, or says its data is not
 *   available while the backend is missing;
 * - widgets that are not on the dashboard yet are skipped, naming the module and the sprint batch that builds it
 *   (field-training #339, placement-career #337). Entries whose module is built already carry that widget's texts, so the journey starts checking them
 *   the day the module is enabled;
 * - no data journeys yet: every widget that holds data waits for its module (field-training, projects), and the
 *   shared ones need a term or a framework first. The data journeys are added with the modules.
 *
 * The super admin moves the organisation to Standard first, so every module of the profile is entitled (campus-life and
 * facilities are not in the Trial plan, platform/billing/config/plans.yaml).
 * Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Practicum Coordinator";

const WIDGETS: LayoutWidget[] = [
  { id: "field-training.placements-open", module: "practice/field-training", batch: "#339" },
  { id: "field-training.active-placements", module: "practice/field-training", batch: "#339" },
  {
    // Texts of CohortOverviewWidget.tsx (practice/skill-progress): a summary of every assessed learner per framework.
    id: "skill-progress.cohort-overview",
    module: "practice/skill-progress",
    batch: "#329",
    title: "Skill levels",
    probe: "/skill-progress/reports/framework-summary",
    empty: "No assessments yet",
    unavailable: "Skill progress data is not available yet.",
    forbidden: "You do not have access to this.",
  },
  {
    // Texts of OpeningsSummary.tsx (campus-life/placement-career, on main; the module is not enabled yet). The staff
    // view of openings (#424 splits it from the learner widget placement-career.openings).
    id: "placement-career.openings-summary",
    module: "campus-life/placement-career",
    batch: "#337",
    title: "Placement openings",
    probe: "/placement-career/reports/openings-summary?limit=1",
    empty: "No openings yet",
    unavailable: "Placement data is not available yet.",
    forbidden: "You do not have access to this.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the practicum coordinator. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "teacher-education-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "practicum-coordinator");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a practicum coordinator signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("practicum-coordinator widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the practicum-coordinator layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the practicum-coordinator layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
