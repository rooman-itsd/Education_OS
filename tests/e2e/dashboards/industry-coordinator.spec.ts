import { expect, test } from "@playwright/test";
import { organisationWithUser, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Industry Coordinator dashboard (layout platform/identity/config/dashboards/industry-coordinator.yaml; the role
 * exists in the hospitality-institute profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: an industry coordinator signs in and lands on their dashboard;
 * - for every widget whose module is in apps/frontend/config/modules.enabled.yaml: the panel renders by its
 *   registered title and shows its empty state, or says its data is not available while the backend is missing;
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it
 *   (field-training #339, placement-career #337, productions #318). None of them is built yet, so each widget's
 *   title, probe and wording are filled in once its module exports it;
 * - no data journeys yet: every widget waits for its module.
 *
 * placement-career (campus-life) is not in the Trial plan (platform/billing/config/plans.yaml), so the super admin
 * moves the organisation to Standard first. The empty-state tests run before any data is created (serial mode).
 * Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Industry Coordinator";

const WIDGETS: LayoutWidget[] = [
  { id: "field-training.placements-open", module: "practice/field-training", batch: "#339" },
  { id: "field-training.active-placements", module: "practice/field-training", batch: "#339" },
  { id: "placement-career.openings", module: "campus-life/placement-career", batch: "#337" },
  { id: "productions.calendar", module: "practice/productions", batch: "#318" },
];
const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the industry coordinator. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  user = await organisationWithUser(request, { academyType: "hospitality-institute", role: "industry-coordinator" });
  await standardPlan(request, user.organisation.id);
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`an industry coordinator signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("industry-coordinator widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the industry-coordinator layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the industry-coordinator layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
