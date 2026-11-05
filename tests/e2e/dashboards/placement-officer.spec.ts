import { expect, test } from "@playwright/test";
import { organisationWithUser, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Placement Officer dashboard (layout platform/identity/config/dashboards/placement-officer.yaml; the role exists in
 * the management-institute profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a placement officer signs in and lands on their dashboard;
 * - for every widget whose module is in apps/frontend/config/modules.enabled.yaml: the panel renders by its
 *   registered title and shows its empty state, or says its data is not available while the backend is missing;
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it
 *   (field-training #339, placement-career #337, productions #318). None of them is built yet, so each widget's
 *   title, probe and wording are filled in once its module exports it;
 * - no data journeys yet: every widget waits for its module (fixme below).
 *
 * placement-career (campus-life) is not in the Trial plan (platform/billing/config/plans.yaml), so the super admin
 * moves the organisation to Standard first. The empty-state tests run before any data is created (serial mode).
 * Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Placement Officer";

const WIDGETS: LayoutWidget[] = [
  { id: "field-training.placements-open", module: "practice/field-training", batch: "#339" },
  // The staff view of openings (#424 splits it from the learner widget placement-career.openings).
  { id: "placement-career.openings-summary", module: "campus-life/placement-career", batch: "#337" },
  { id: "placement-career.drives", module: "campus-life/placement-career", batch: "#337" },
  {
    id: "productions.calendar",
    module: "practice/productions",
    batch: "#318",
    title: "Production calendar",
    probe: "/productions/calendar",
    empty: "Nothing scheduled",
    unavailable: "Production data is not available yet.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the placement officer. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  user = await organisationWithUser(request, { academyType: "management-institute", role: "placement-officer" });
  await standardPlan(request, user.organisation.id);
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a placement officer signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("placement-officer widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the placement-officer layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the placement-officer layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

// Backend-dependent: these need their module's API to create the data through, so nothing here is faked.
test.fixme("field-training.placements-open lists the internships still looking for trainees", async () => {
  // practice/field-training (sprint batch #339); vocabulary: "Internship". The layout grants field-training-coordinator.
});

test.fixme("placement-career.openings-summary counts the openings the placement office has posted", async () => {
  // campus-life/placement-career (sprint batch #337); contract on contract/placement-career/v1 (PR #424), which adds
  // placement-career-officer to the layout.
});

test.fixme("placement-career.drives lists the upcoming campus drives", async () => {
  // campus-life/placement-career (sprint batch #337).
});

test.fixme("productions.calendar shows the case competitions and industry events in the coming weeks", async () => {
  // practice/productions (sprint batch #318); vocabulary: "Case competition / industry event".
});
