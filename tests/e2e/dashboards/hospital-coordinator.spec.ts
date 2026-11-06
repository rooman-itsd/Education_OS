import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { OPENING, REQUIRED_HOURS, seedPlacement, SITE } from "./field-training-data";
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
 * - data journey: the coordinator records a site and an opening with two seats, assigns and starts a medical student's
 *   placement (whose entry the clinical supervisor verifies); it shows in `field-training.active-placements` with the
 *   verified hours and the opening in `field-training.placements-open` with one seat left. It skips until field-training
 *   is enabled. No data journey for facility-booking.bookings-today, which lists bookings of the resources the viewer
 *   approves (see clinical-supervisor.spec.ts), or for regulatory-reports, which waits for its module.
 *
 * facilities and practice are not in the Trial plan (platform/billing/config/plans.yaml), so the super admin moves
 * the organisation to Standard first. Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Hospital Coordinator";

const WIDGETS: LayoutWidget[] = [
  {
    id: "field-training.active-placements",
    module: "practice/field-training",
    batch: "#339",
    title: "Active placements",
    probe: "/field-training/placements?status=active&limit=1",
    empty: "No placements under way",
    unavailable: "Field training data is not available yet.",
  },
  {
    id: "field-training.placements-open",
    module: "practice/field-training",
    batch: "#339",
    title: "Open placements",
    probe: "/field-training/openings?status=open&has_seats=true&limit=1",
    empty: "No open placements with seats",
    unavailable: "Field training data is not available yet.",
  },
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
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let admin: DashboardUser;
let user: DashboardUser;
/** The clinical supervisor named on the site and opening, and the medical student placed there. */
let supervisor: DashboardUser;
let trainee: DashboardUser;
/** Per shipped widget id: what its GET answered the hospital coordinator. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "medical-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "hospital-coordinator");
  supervisor = await addUser(request, admin, "clinical-supervisor");
  trainee = await addUser(request, admin, "medical-student");
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

test.describe("with field-training data", () => {
  test("field-training.active-placements and placements-open show the placement the coordinator starts and the opening's free seat", async ({ page, request }) => {
    for (const id of ["field-training.active-placements", "field-training.placements-open"]) {
      test.skip(!shipped(byId(id)), waitingFor(byId(id)));
      test.skip(!ready(id), `the field-training API answered ${status[id]} to the hospital-coordinator role`);
    }
    // Site, opening (two seats, 40 required hours), assignment and start are the coordinator's own (field-training-coordinator);
    // the trainee logs today's hours and the supervisor named on the opening verifies them.
    await seedPlacement(request, { coordinator: user, supervisor, trainee }, { start: true, log: true, verify: true });
    await signIn(page, user);

    const active = widget(page, "Active placements");
    await expect(active.getByText("No placements under way")).toHaveCount(0);
    // No identity lookup gives the module the trainee's name yet, so the row is titled "Trainee".
    const row = active.getByRole("list", { name: "Active placements" }).getByRole("listitem").filter({ hasText: OPENING });
    await expect(row).toContainText(SITE);
    await expect(row).toContainText(`4 of ${REQUIRED_HOURS} h`);

    const open = widget(page, "Open placements");
    await expect(open.getByText("No open placements with seats")).toHaveCount(0);
    const opening = open.getByRole("list", { name: "Open placements" }).getByRole("listitem").filter({ hasText: OPENING });
    await expect(opening).toContainText(SITE);
    await expect(opening).toContainText("1 seat left");
  });
});
