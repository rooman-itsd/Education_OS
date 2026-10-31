import { expect, test } from "@playwright/test";
import { organisationWithUser, type DashboardUser } from "./organisation";
import { created, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Exhibition & Gallery Manager dashboard (layout platform/identity/config/dashboards/exhibition-manager.yaml; the
 * role exists in the arts-academy profile, ADR-0004).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: an exhibition-manager user signs in and lands on their dashboard;
 * - for every widget of the layout whose module is in apps/frontend/config/modules.enabled.yaml: the panel renders
 *   by its registered title and shows its empty state, or says its data is not available while the backend is missing;
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it;
 * - with inventory-equipment data: consumable art or gallery supplies below reorder level appear in
 *   inventory-equipment.low-stock;
 * - with facility-booking data: today's reservations for galleries or exhibition spaces appear in
 *   facility-booking.bookings-today.
 *
 * facilities, finance-operations and campus-life are not in the Trial plan, so the super admin moves the organisation
 * to Standard first. The empty-state tests run before any data is created (serial mode). Loading states are covered
 * by the modules' unit tests, not here.
 */

const TITLE = "Exhibition & Gallery Manager";

const WIDGETS: LayoutWidget[] = [
  { id: "productions.calendar", module: "practice/productions", batch: "#318" },
  { id: "productions.upcoming", module: "practice/productions", batch: "#318" },
  {
    id: "facility-booking.bookings-today",
    module: "facilities/facility-booking",
    batch: "#287",
    title: "Bookings today",
    probe: "/facility-booking/summary",
    empty: "No bookings today",
    unavailable: "Facility booking data is not available yet.",
  },
  {
    id: "inventory-equipment.low-stock",
    module: "facilities/inventory-equipment",
    batch: "#109",
    title: "Low stock",
    probe: "/inventory-equipment/low-stock",
    empty: "Stock is healthy",
    unavailable: "Inventory and equipment data is not available yet.",
  },
];

const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the exhibition manager user. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  user = await organisationWithUser(request, {
    academyType: "arts-academy",
    role: "exhibition-manager",
    extraRoles: ["facility-staff"],
  });
  await standardPlan(request, user.organisation.id);
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`an exhibition manager signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("exhibition manager widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the exhibition-manager layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, says its data is not available yet, or says the role has no access", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the exhibition-manager layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    for (const w of SHIPPED) await expectBody(page, w, status[w.id] ?? 0);
  });

  test("shipped facilities widgets display correct titles and empty states before data seeding", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the exhibition-manager layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);

    const lowStockPanel = widget(page, "Low stock");
    await expect(lowStockPanel).toBeVisible();
    await expect(lowStockPanel.getByRole("heading", { name: "Low stock", exact: true })).toBeVisible();
    await expect(lowStockPanel.getByText("Stock is healthy", { exact: true })).toBeVisible();

    const bookingsPanel = widget(page, "Bookings today");
    await expect(bookingsPanel).toBeVisible();
    await expect(bookingsPanel.getByRole("heading", { name: "Bookings today", exact: true })).toBeVisible();
    await expect(bookingsPanel.getByText("No bookings today", { exact: true })).toBeVisible();
    await expect(
      bookingsPanel.getByText("Bookings on the spaces and equipment you look after appear here.", { exact: true }),
    ).toBeVisible();
  });

  for (const w of WIDGETS.filter((w) => !shipped(w))) {
    test(`${w.id} renders once ${w.module} ships`, async ({ page }) => {
      test.skip(!shipped(w), waitingFor(w));
      await signIn(page, user);
      await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
      await expect(widget(page, w.id)).toHaveCount(0);
    });
  }
});

test.describe("with facilities data", () => {
  test("inventory-equipment.low-stock lists consumable items below reorder level", async ({ page, request }) => {
    const w = byId("inventory-equipment.low-stock");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(status[w.id] !== 200, `the inventory-equipment API answered ${status[w.id]} to the exhibition-manager role`);

    const category = await created<{ id: string }>(request, user, "/inventory-equipment/categories", {
      name: "Gallery Mounting",
    });
    const location = await created<{ id: string }>(request, user, "/inventory-equipment/locations", {
      name: "Gallery Storage",
    });
    const item = await created<{ id: string }>(request, user, "/inventory-equipment/items", {
      name: "Picture Hanging Wire",
      category_id: category.id,
      tracking: "quantity",
      consumable: true,
      reorder_level: 5,
    });
    await created(request, user, "/inventory-equipment/movements", {
      kind: "receipt",
      item_id: item.id,
      quantity: 2,
      to_location_id: location.id,
    });

    await signIn(page, user);
    const panel = widget(page, "Low stock");
    await expect(panel.getByText("Picture Hanging Wire")).toBeVisible();
    await expect(panel.getByText("2 piece left")).toBeVisible();
    await expect(panel.getByText("Stock is healthy")).toHaveCount(0);
  });

  test("facility-booking.bookings-today lists today's exhibition gallery reservation", async ({ page, request }) => {
    const w = byId("facility-booking.bookings-today");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(status[w.id] !== 200, `the facility-booking API answered ${status[w.id]} to the exhibition-manager role`);

    const zone = process.env.FACILITY_BOOKING_TIMEZONE || "UTC";
    const day = (d: Date) => d.toLocaleDateString("en-CA", { timeZone: zone });
    const slot = 30 * 60_000;
    const start = new Date(Math.ceil((Date.now() + 5 * 60_000) / slot) * slot);
    const end = new Date(start.getTime() + slot);
    test.skip(day(end) !== day(new Date()), `too close to midnight in ${zone}`);

    const type = await created<{ id: string }>(request, user, "/facility-booking/resource-types", {
      name: "Exhibition Gallery",
    });
    const resource = await created<{ id: string }>(request, user, "/facility-booking/resources", {
      name: "Main Gallery Wing A",
      type_id: type.id,
      capacity: 100,
    });
    await created(request, user, "/facility-booking/bookings", {
      resource_id: resource.id,
      start_at: start.toISOString(),
      end_at: end.toISOString(),
      title: "Graduate Showcase Setup",
    });

    await signIn(page, user);
    const panel = widget(page, "Bookings today");
    await expect(panel.getByText("Main Gallery Wing A · Graduate Showcase Setup")).toBeVisible();
    await expect(panel.getByLabel("Booking counts")).toContainText("1 today");
    await expect(panel.getByText("No bookings today")).toHaveCount(0);
  });
});

// Backend-dependent: these need their module's API to create data through once the modules are merged.
test.fixme("productions.calendar and productions.upcoming show upcoming exhibitions and dates", async () => {
  // practice/productions (sprint batch #318); exhibition manager tracks scheduled exhibitions.
});
