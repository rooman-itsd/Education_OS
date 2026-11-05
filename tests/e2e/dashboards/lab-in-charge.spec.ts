import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Lab In-charge dashboard (layout platform/identity/config/dashboards/lab-in-charge.yaml, a role of the
 * engineering-college profile; the layout extends nothing, so these four widgets are all it shows).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a lab in-charge signs in and lands on their dashboard;
 * - for every widget of the layout whose module is in apps/frontend/config/modules.enabled.yaml: the panel renders by
 *   its registered title and shows its empty state, or says its data is not available while the backend is missing;
 * - data journeys, one per widget the lab in-charge's grants allow today:
 *   - maintenance.tickets: a ticket raised for a lab shows with the counts;
 *   - inventory-equipment.low-stock: the lab in-charge (item:manage, stock:manage) adds a consumable with a reorder
 *     level and receives less than that into a store;
 *   - facility-booking.bookings-today: a booking made for later today on a resource the lab in-charge approves
 *     (bookings-today lists the resources the viewer approves, so the store keeper sets them as its approver).
 * - inventory-equipment.overdue-loans has no data journey: a loan is "overdue" once the scheduler sweep finds it past
 *   its due date, and the API refuses a due date in the past (due_in_past), so a journey would wait for the sweep.
 *   The empty state is covered below; the list is covered by the module's widget tests.
 *
 * facilities is not in the Trial plan (platform/billing/config/plans.yaml), so the super admin moves the organisation
 * to Standard first. The empty-state tests run before any data is created (serial mode). Loading states are covered
 * by the modules' unit tests, not here.
 */

const TITLE = "Lab In-charge";

const WIDGETS: LayoutWidget[] = [
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
  {
    id: "inventory-equipment.overdue-loans",
    module: "facilities/inventory-equipment",
    batch: "#254",
    title: "Overdue loans",
    probe: "/inventory-equipment/loans?scope=managed&status=overdue&page_size=1",
    empty: "No overdue loans",
    unavailable: "Inventory data is not available yet.",
  },
  {
    id: "maintenance.tickets",
    module: "facilities/maintenance",
    batch: "#254",
    title: "Maintenance tickets",
    probe: "/maintenance/summary",
    empty: "No open tickets",
    unavailable: "Maintenance data is not available yet.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let user: DashboardUser;
/** The Facility / Inventory Staff role manages resources and tickets, which the lab in-charge only reads or approves. */
let storeKeeper: DashboardUser;
/** Per shipped widget id: what its GET answered the lab in-charge. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "engineering-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "lab-in-charge");
  storeKeeper = await addUser(request, admin, "facility-staff");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a lab in-charge signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("lab-in-charge widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the lab-in-charge layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the lab-in-charge layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
  test("maintenance.tickets lists an urgent ticket with the counts", async ({ page, request }) => {
    const w = byId("maintenance.tickets");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the maintenance API answered ${status[w.id]} to the lab-in-charge role`);
    const category = await created<{ id: string }>(request, storeKeeper, "/maintenance/categories", { name: "Lab equipment" });
    await created(request, user, "/maintenance/tickets", {
      title: "Oscilloscope not powering on",
      category_id: category.id,
      priority: "urgent",
      target: { kind: "location", label: "Electronics lab" },
    });
    await signIn(page, user);
    const panel = widget(page, "Maintenance tickets");
    await expect(panel.getByText(/· Oscilloscope not powering on$/)).toBeVisible();
    await expect(panel.getByText("Electronics lab · Unassigned")).toBeVisible();
    await expect(panel.getByLabel("Ticket counts")).toHaveText("1 open · 1 unassigned · 0 on hold");
  });

  test("inventory-equipment.low-stock lists an item received below its reorder level", async ({ page, request }) => {
    const w = byId("inventory-equipment.low-stock");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the inventory-equipment API answered ${status[w.id]} to the lab-in-charge role`);
    // The lab in-charge runs the lab store: item:manage and stock:manage let them add a consumable with a reorder
    // level of 5 and receive 2 into the store themselves.
    const category = await created<{ id: string }>(request, user, "/inventory-equipment/categories", { name: "Lab consumables" });
    const location = await created<{ id: string }>(request, user, "/inventory-equipment/locations", { name: "Electronics lab store" });
    const item = await created<{ id: string }>(request, user, "/inventory-equipment/items", {
      name: "Solder wire",
      category_id: category.id,
      tracking: "quantity",
      consumable: true,
      reorder_level: 5,
    });
    await created(request, user, "/inventory-equipment/movements", { kind: "receipt", item_id: item.id, quantity: 2, to_location_id: location.id });
    await signIn(page, user);

    const panel = widget(page, "Low stock");
    await expect(panel.getByText("Stock is healthy")).toHaveCount(0);
    const row = panel.getByRole("list", { name: "Items low on stock" }).getByRole("listitem").filter({ hasText: "Solder wire" });
    await expect(row).toContainText("Reorder level 5 piece");
    await expect(row).toContainText("2 piece left");
  });

  test("facility-booking.bookings-today lists a booking made for later today on a resource they approve", async ({ page, request }) => {
    const w = byId("facility-booking.bookings-today");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the facility-booking API answered ${status[w.id]} to the lab-in-charge role`);
    // The default slot grid is 30 minutes and "today" is the organisation's date in FACILITY_BOOKING_TIMEZONE
    // (UTC by default; the API inherits this process's environment): book the next free half hour, unless that
    // runs past midnight in that zone.
    const zone = process.env.FACILITY_BOOKING_TIMEZONE || "UTC";
    const day = (d: Date) => d.toLocaleDateString("en-CA", { timeZone: zone }); // YYYY-MM-DD
    const slot = 30 * 60_000;
    const start = new Date(Math.ceil((Date.now() + 5 * 60_000) / slot) * slot);
    const end = new Date(start.getTime() + slot);
    test.skip(day(end) !== day(new Date()), `too close to midnight in ${zone}`);
    const type = await created<{ id: string }>(request, storeKeeper, "/facility-booking/resource-types", { name: "Lab" });
    const resource = await created<{ id: string }>(request, storeKeeper, "/facility-booking/resources", {
      name: "Electronics lab",
      type_id: type.id,
      capacity: 30,
      approver_user_ids: [user.id],
    });
    await created(request, storeKeeper, "/facility-booking/bookings", {
      resource_id: resource.id,
      start_at: start.toISOString(),
      end_at: end.toISOString(),
      title: "Circuits practical",
    });
    await signIn(page, user);
    const panel = widget(page, "Bookings today");
    await expect(panel.getByText("Electronics lab · Circuits practical")).toBeVisible();
    await expect(panel.getByLabel("Booking counts")).toContainText("1 today");
  });
});
