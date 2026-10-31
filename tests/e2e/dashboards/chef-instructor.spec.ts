import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Chef / Operations Instructor dashboard (layout platform/identity/config/dashboards/chef-instructor.yaml, which
 * extends the Faculty layout; the role exists in the hospitality-institute profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a chef instructor signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Faculty ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml: the panel renders by its registered title and shows its empty
 *   state, or says its data is not available while the backend is missing (the chef instructor holds the faculty
 *   role's permissions through `extends`);
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it
 *   (skill-progress #329, productions #318, and the inherited timetable-attendance, lms and examinations ones);
 * - data journey: an item a store keeper (facility-staff) receives below its reorder level shows in
 *   inventory-equipment.low-stock. facility-booking.bookings-today has none here: it lists bookings of the resources
 *   the viewer approves, which needs the chef instructor set as a resource's approver (facility-staff.spec.ts covers
 *   the widget with a booking).
 *
 * facilities is not in the Trial plan (platform/billing/config/plans.yaml), so the super admin moves the organisation
 * to Standard first. The empty-state tests run before any data is created (serial mode). Loading states are covered
 * by the modules' unit tests, not here.
 */

const TITLE = "Chef / Operations Instructor";

const WIDGETS: LayoutWidget[] = [
  // Inherited from the Faculty layout (extends: faculty).
  { id: "timetable-attendance.today-classes", module: "academics/timetable-attendance", batch: "#325" },
  { id: "timetable-attendance.attendance-to-mark", module: "academics/timetable-attendance", batch: "#325" },
  { id: "lms.assignments-to-grade", module: "academics/lms", batch: "#326" },
  { id: "examinations.exam-duties", module: "academics/examinations", batch: "#325" },
  {
    id: "academic-management.course-roster",
    module: "academics/academic-management",
    batch: "#100",
    title: "Course roster",
    probe: "/academic-management/me/offerings",
    empty: "No courses this term",
    // A new organisation has no active term: GET /me/offerings answers 404 active_term_not_found, which the widget's
    // client turns into an empty page ("No courses this term").
    emptyCode: "active_term_not_found",
    unavailable: "No courses this term",
    forbidden: "Could not load your courses",
  },
  // The chef instructor's own widgets.
  { id: "skill-progress.assessments-due", module: "practice/skill-progress", batch: "#329" },
  {
    id: "facility-booking.bookings-today",
    module: "facilities/facility-booking",
    batch: "#331",
    title: "Bookings today",
    probe: "/facility-booking/summary",
    empty: "No bookings today",
    unavailable: "Booking data is not available yet.",
  },
  {
    id: "inventory-equipment.low-stock",
    module: "facilities/inventory-equipment",
    batch: "#254",
    title: "Low stock",
    probe: "/inventory-equipment/low-stock",
    empty: "Stock is healthy",
    unavailable: "Inventory data is not available yet.",
  },
  { id: "productions.in-preparation", module: "practice/productions", batch: "#318" },
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let user: DashboardUser;
/** A store keeper: the facility-staff role manages stock, which the chef instructor only reads. */
let storeKeeper: DashboardUser;
/** Per shipped widget id: what its GET answered the chef instructor. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "hospitality-institute" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "chef-instructor");
  storeKeeper = await addUser(request, admin, "facility-staff");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a chef instructor signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("chef-instructor widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the chef-instructor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the chef-instructor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

test.describe("with inventory-equipment data", () => {
  test("inventory-equipment.low-stock lists an item received below its reorder level", async ({ page, request }) => {
    const w = byId("inventory-equipment.low-stock");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the inventory-equipment API answered ${status[w.id]} to the chef-instructor role`);
    // The store keeper (facility-staff: item:manage, stock:manage) adds a consumable with a reorder level of 5 and
    // receives 2 into a store; the chef instructor (stock:read) sees it on the low-stock list.
    const category = await created<{ id: string }>(request, storeKeeper, "/inventory-equipment/categories", { name: "Kitchen consumables" });
    const location = await created<{ id: string }>(request, storeKeeper, "/inventory-equipment/locations", { name: "Training kitchen store" });
    const item = await created<{ id: string }>(request, storeKeeper, "/inventory-equipment/items", {
      name: "Piping bags",
      category_id: category.id,
      tracking: "quantity",
      consumable: true,
      reorder_level: 5,
    });
    await created(request, storeKeeper, "/inventory-equipment/movements", { kind: "receipt", item_id: item.id, quantity: 2, to_location_id: location.id });
    await signIn(page, user);

    const panel = widget(page, "Low stock");
    await expect(panel.getByText("Stock is healthy")).toHaveCount(0);
    const row = panel.getByRole("list", { name: "Items low on stock" }).getByRole("listitem").filter({ hasText: "Piping bags" });
    await expect(row).toContainText("Reorder level 5 piece");
    await expect(row).toContainText("2 piece left");
  });
});
