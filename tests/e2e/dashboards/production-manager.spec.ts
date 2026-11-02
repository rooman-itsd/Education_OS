import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Production Manager dashboard (layout platform/identity/config/dashboards/production-manager.yaml; the role exists in
 * the dance-academy profile). Issue #333.
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a production manager signs in and lands on their dashboard;
 * - for every widget whose module is in apps/frontend/config/modules.enabled.yaml and exports it: the panel renders by
 *   its registered title and shows its empty state, or says its data is not available while the backend is missing;
 * - productions.calendar and productions.upcoming are skipped until practice/productions ships (sprint batch #318);
 * - data journeys: a costume below its reorder level shows in inventory-equipment.low-stock, and a booking later today
 *   on a stage the production manager approves in facility-booking.bookings-today. Facility staff create both (the
 *   production manager reads stock and approves bookings, but does not manage the stores or the resource register).
 *
 * facilities is not in the Trial plan (platform/billing/config/plans.yaml), so the super admin moves the organisation
 * to Standard first. The empty-state tests run before any data is created (serial mode). Loading states are covered
 * by the modules' unit tests, not here.
 */

const TITLE = "Production Manager";

const WIDGETS: LayoutWidget[] = [
  { id: "productions.calendar", module: "practice/productions", batch: "#318" },
  { id: "productions.upcoming", module: "practice/productions", batch: "#318" },
  {
    id: "inventory-equipment.low-stock",
    module: "facilities/inventory-equipment",
    batch: "#331",
    title: "Low stock",
    probe: "/inventory-equipment/low-stock",
    empty: "Stock is healthy",
    unavailable: "Inventory data is not available yet.",
  },
  {
    id: "facility-booking.bookings-today",
    module: "facilities/facility-booking",
    batch: "#331",
    title: "Bookings today",
    probe: "/facility-booking/summary?date=today",
    empty: "No bookings today",
    unavailable: "Booking data is not available yet.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let admin: DashboardUser;
let user: DashboardUser;
/** Facility staff: they run the stores and the resource register, so they create the data the journeys look for. */
let facilityStaff: DashboardUser;
/** Per shipped widget id: what its GET answered the production manager. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "dance-academy" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "production-manager");
  facilityStaff = await addUser(request, admin, "facility-staff");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a production manager signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("production-manager widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the production-manager layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the production-manager layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

test.describe("with facilities data", () => {
  test("inventory-equipment.low-stock lists a costume below its reorder level", async ({ page, request }) => {
    const w = byId("inventory-equipment.low-stock");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the inventory-equipment API answered ${status[w.id]} to the production-manager role`);
    // As in facility-staff.spec.ts, made by facility staff (stock:manage); the production manager holds stock:read.
    const category = await created<{ id: string }>(request, facilityStaff, "/inventory-equipment/categories", { name: "Costumes" });
    const location = await created<{ id: string }>(request, facilityStaff, "/inventory-equipment/locations", { name: "Wardrobe" });
    const item = await created<{ id: string }>(request, facilityStaff, "/inventory-equipment/items", {
      name: "Ghungroo bells",
      category_id: category.id,
      tracking: "quantity",
      consumable: true,
      reorder_level: 5,
    });
    await created(request, facilityStaff, "/inventory-equipment/movements", {
      kind: "receipt",
      item_id: item.id,
      quantity: 2,
      to_location_id: location.id,
    });
    await signIn(page, user);
    const panel = widget(page, "Low stock");
    await expect(panel.getByText("Stock is healthy")).toHaveCount(0);
    await expect(panel.getByText("Ghungroo bells")).toBeVisible();
    await expect(panel.getByText("2 piece left")).toBeVisible();
  });

  test("facility-booking.bookings-today lists a booking later today on a stage the production manager approves", async ({ page, request }) => {
    const w = byId("facility-booking.bookings-today");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the facility-booking API answered ${status[w.id]} to the production-manager role`);
    // As in facility-staff.spec.ts: the default slot grid is 30 minutes and "today" is the organisation's date in
    // FACILITY_BOOKING_TIMEZONE (UTC by default; the API inherits this process's environment), so book the next free
    // half hour, unless that runs past midnight in that zone. The production manager sees bookings on the resources
    // whose approvers list them (scope=managed without booking:read-all).
    const zone = process.env.FACILITY_BOOKING_TIMEZONE || "UTC";
    const day = (d: Date) => d.toLocaleDateString("en-CA", { timeZone: zone }); // YYYY-MM-DD
    const slot = 30 * 60_000;
    const start = new Date(Math.ceil((Date.now() + 5 * 60_000) / slot) * slot);
    const end = new Date(start.getTime() + slot);
    test.skip(day(end) !== day(new Date()), `too close to midnight in ${zone}`);
    const type = await created<{ id: string }>(request, facilityStaff, "/facility-booking/resource-types", { name: "Stage" });
    const resource = await created<{ id: string }>(request, facilityStaff, "/facility-booking/resources", {
      name: "Main stage",
      type_id: type.id,
      capacity: 200,
      approver_user_ids: [user.id],
    });
    await created(request, facilityStaff, "/facility-booking/bookings", {
      resource_id: resource.id,
      start_at: start.toISOString(),
      end_at: end.toISOString(),
      title: "Technical rehearsal",
    });
    await signIn(page, user);
    const panel = widget(page, "Bookings today");
    await expect(panel.getByText("No bookings today")).toHaveCount(0);
    await expect(panel.getByText("Main stage · Technical rehearsal")).toBeVisible();
    await expect(panel.getByLabel("Booking counts")).toContainText("1 today");
  });
});
