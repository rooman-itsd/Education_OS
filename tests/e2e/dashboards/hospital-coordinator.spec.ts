import { expect, test } from "@playwright/test";
import { organisationWithUser, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Hospital Coordinator dashboard (layout platform/identity/config/dashboards/hospital-coordinator.yaml; the role exists in the medical-college
 * profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a hospital coordinator signs in and lands on their dashboard;
 * - for every widget of the layout whose module is in apps/frontend/config/modules.enabled.yaml and exports the
 *   widget: the panel renders by its registered title and shows its empty state, or says its data is not available
 *   while the backend is missing;
 * - widgets that are not on the dashboard yet are skipped, naming the module and the sprint batch that builds it
 *   (field-training #339 and regulatory-reports #343 (governance is not enabled yet)). Entries whose module is already merged carry that widget's texts, so the journey starts checking them the
 *   day the module is enabled;
 * - no data journeys yet: facility-booking.bookings-today lists bookings of the resources the viewer approves (see clinical-supervisor.spec.ts), and the other widgets wait for their module.
 *
 * facilities and practice are not in the Trial plan (platform/billing/config/plans.yaml), so the super admin moves
 * the organisation to Standard first. Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Hospital Coordinator";

const WIDGETS: LayoutWidget[] = [
  { id: "field-training.active-placements", module: "practice/field-training", batch: "#339" },
  { id: "field-training.placements-open", module: "practice/field-training", batch: "#339" },
  {
    id: "facility-booking.bookings-today",
    module: "facilities/facility-booking",
    batch: "#331",
    title: "Bookings today",
    probe: "/facility-booking/summary",
    empty: "No bookings today",
    unavailable: "Booking data is not available yet.",
  },
  { id: "regulatory-reports.due", module: "governance/regulatory-reports", batch: "#343" },
];
const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the hospital coordinator. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  user = await organisationWithUser(request, { academyType: "medical-college", role: "hospital-coordinator" });
  await standardPlan(request, user.organisation.id);
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a hospital coordinator signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("hospital-coordinator widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the hospital-coordinator layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the hospital-coordinator layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
