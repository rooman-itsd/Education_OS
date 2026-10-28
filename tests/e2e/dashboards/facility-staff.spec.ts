import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { SUPER_ADMIN } from "../stack";
import { organisationWithUser, type DashboardUser } from "./organisation";

/**
 * Facility / Inventory Staff dashboard (issue #6; layout platform/identity/config/dashboards/facility-staff.yaml).
 *
 * The four widgets come from four facilities modules (Ashritha). What runs depends on what has shipped; each skip
 * says what it waits for:
 * - always: a facility-staff user signs in and lands on their dashboard;
 * - once the facilities modules are in apps/frontend/config/modules.enabled.yaml: the widgets render
 *   (bookings-today needs its widget too);
 * - once the facility-staff profile role has the modules' grants (contract PRs) and the backends are mounted:
 *   each widget shows its empty state for a new organisation, then the data created through the API.
 *
 * Facilities is not in the Trial plan (platform/billing/config/plans.yaml), so the super admin moves the
 * organisation to Standard first; otherwise the entitlement gate refuses every facilities request (403).
 * Loading states are covered by the modules' unit tests, not here.
 */

const repo = (path: string) => readFileSync(new URL(`../../../${path}`, import.meta.url), "utf8");

/** Whether apps/frontend registers a module's widgets (a listed, uncommented entry). */
const enabled = (module: string) =>
  repo("apps/frontend/config/modules.enabled.yaml")
    .split("\n")
    .some((line) => line.replace(/#.*/, "").trim() === `- facilities/${module}`);

const WIDGETS = [
  { module: "facility-booking", id: "facility-booking.bookings-today", title: "Bookings today", empty: "No bookings today" },
  { module: "maintenance", id: "maintenance.tickets", title: "Maintenance tickets", empty: "No open tickets" },
  { module: "inventory-equipment", id: "inventory-equipment.low-stock", title: "Low stock", empty: "Stock is healthy" },
  { module: "asset-management", id: "asset-management.audit-due", title: "Asset verification due", empty: "Nothing due for verification" },
] as const;

/** A widget is on the dashboard once its module is enabled and the module exports it. */
const shipped = (w: (typeof WIDGETS)[number]) =>
  enabled(w.module) && repo(`modules/facilities/${w.module}/frontend/src/widgets/index.ts`).includes(`"${w.id}"`);
const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
let auth: { Authorization: string };
/** Per module: the backend is mounted and the facility-staff role may read it. */
const live: Record<string, boolean> = {};

test.describe.configure({ mode: "serial" });

async function asSuperAdmin(request: APIRequestContext) {
  const r = await request.post("/api/v1/identity/auth/login", { data: SUPER_ADMIN });
  expect(r.ok(), await r.text()).toBeTruthy();
  return { Authorization: `Bearer ${(await r.json()).token}` };
}

test.beforeAll(async ({ request }) => {
  user = await organisationWithUser(request, { academyType: "sports-college", role: "facility-staff" });
  auth = { Authorization: `Bearer ${user.token}` };
  const root = await asSuperAdmin(request);
  const plan = await request.put(`/api/v1/billing/admin/subscriptions/${user.organisation.id}`, {
    headers: root,
    data: { plan: "standard", reason: "e2e: facilities is not in the trial plan" },
  });
  expect(plan.ok(), await plan.text()).toBeTruthy();
  const probes: Record<string, string> = {
    "facility-booking": "/api/v1/facility-booking/summary",
    maintenance: "/api/v1/maintenance/summary",
    "inventory-equipment": "/api/v1/inventory-equipment/low-stock",
    "asset-management": "/api/v1/asset-management/verifications/due",
  };
  for (const [module, path] of Object.entries(probes)) {
    live[module] = (await request.get(path, { headers: auth })).ok();
  }
});

async function signIn(page: Page) {
  await page.goto("/app"); // the dashboard app lives at /app; / is the public site
  // exact: the organisation field's hint also says "email"
  await page.getByLabel("Email", { exact: true }).fill(user.email);
  await page.getByLabel("Password", { exact: true }).fill(user.password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** The panel a widget renders in, found by its heading. */
const widget = (page: Page, title: string) =>
  page.locator(".eos-widget").filter({ has: page.getByRole("heading", { name: title, exact: true }) });

async function created<T>(request: APIRequestContext, path: string, data: unknown): Promise<T> {
  const r = await request.post(`/api/v1${path}`, { headers: auth, data });
  expect(r.ok(), `${path} → ${r.status()} ${await r.text()}`).toBeTruthy();
  return (await r.json()) as T;
}

test("a facility staff member signs in and lands on the Facility / Inventory Staff dashboard", async ({ page }) => {
  await signIn(page);
  await expect(page.getByRole("region", { name: "Facility / Inventory Staff dashboard" })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · Facility / Inventory Staff dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("facilities widgets", () => {
  test.skip(SHIPPED.length === 0, "the facilities modules are not in apps/frontend/config/modules.enabled.yaml yet");

  test("every shipped facilities widget renders", async ({ page }) => {
    await signIn(page);
    const dashboard = page.getByRole("region", { name: "Facility / Inventory Staff dashboard" });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title, exact: true })).toBeVisible();
  });

  test("each widget shows its empty state for a new organisation", async ({ page }) => {
    const ready = SHIPPED.filter((w) => live[w.module]);
    test.skip(ready.length === 0, "no facilities backend answers the facility-staff role yet (contract PRs and enable PR)");
    await signIn(page);
    for (const w of ready) await expect(widget(page, w.title).getByText(w.empty)).toBeVisible();
  });
});

test.describe("with facilities data", () => {
  const ready = (module: string) => SHIPPED.some((w) => w.module === module) && live[module];

  test("maintenance.tickets lists an urgent ticket with the counts", async ({ page, request }) => {
    test.skip(!ready("maintenance"), "maintenance is not live for the facility-staff role yet");
    const category = await created<{ id: string }>(request, "/maintenance/categories", { name: "Electrical" });
    await created(request, "/maintenance/tickets", {
      title: "Projector flickering",
      category_id: category.id,
      priority: "urgent",
      target: { kind: "location", label: "Seminar hall" },
    });
    await signIn(page);
    const panel = widget(page, "Maintenance tickets");
    await expect(panel.getByText(/· Projector flickering$/)).toBeVisible();
    await expect(panel.getByText("Seminar hall · Unassigned")).toBeVisible();
    await expect(panel.getByLabel("Ticket counts")).toHaveText("1 open · 1 unassigned · 0 on hold");
  });

  test("inventory-equipment.low-stock lists an item below its reorder level", async ({ page, request }) => {
    test.skip(!ready("inventory-equipment"), "inventory-equipment is not live for the facility-staff role yet");
    const category = await created<{ id: string }>(request, "/inventory-equipment/categories", { name: "Consumables" });
    const location = await created<{ id: string }>(request, "/inventory-equipment/locations", { name: "Main store" });
    const item = await created<{ id: string }>(request, "/inventory-equipment/items", {
      name: "Whiteboard markers",
      category_id: category.id,
      tracking: "quantity",
      consumable: true,
      reorder_level: 5,
    });
    await created(request, "/inventory-equipment/movements", { kind: "receipt", item_id: item.id, quantity: 2, to_location_id: location.id });
    await signIn(page);
    const panel = widget(page, "Low stock");
    await expect(panel.getByText("Whiteboard markers")).toBeVisible();
    await expect(panel.getByText("2 piece left")).toBeVisible();
  });

  test("asset-management.audit-due lists an asset overdue for verification", async ({ page, request }) => {
    test.skip(!ready("asset-management"), "asset-management is not live for the facility-staff role yet");
    const category = await created<{ id: string }>(request, "/asset-management/categories", { name: "Furniture", code: "FN" });
    const twoYearsAgo = new Date(Date.now() - 730 * 86_400_000).toISOString().slice(0, 10);
    const asset = await created<{ tag: string }>(request, "/asset-management/assets", {
      name: "Lecture podium",
      category_id: category.id,
      location: "Seminar hall",
      in_service_date: twoYearsAgo,
    });
    await signIn(page);
    const panel = widget(page, "Asset verification due");
    await expect(panel.getByText(`${asset.tag} · Lecture podium`)).toBeVisible();
    await expect(panel.getByText("Overdue", { exact: true })).toBeVisible();
    await expect(panel.getByLabel("Verification counts")).toContainText("1 overdue");
  });

  test("facility-booking.bookings-today lists a booking made for later today", async ({ page, request }) => {
    test.skip(!ready("facility-booking"), "facility-booking is not live for the facility-staff role yet");
    // The default slot grid is 30 minutes and "today" is the organisation's date (FACILITY_BOOKING_TIMEZONE, UTC
    // by default): book the next free half hour, unless that runs past midnight UTC.
    const slot = 30 * 60_000;
    const start = new Date(Math.ceil((Date.now() + 5 * 60_000) / slot) * slot);
    const end = new Date(start.getTime() + slot);
    test.skip(end.toISOString().slice(0, 10) !== new Date().toISOString().slice(0, 10), "too close to midnight UTC");
    const type = await created<{ id: string }>(request, "/facility-booking/resource-types", { name: "Hall" });
    const resource = await created<{ id: string }>(request, "/facility-booking/resources", {
      name: "Seminar hall",
      type_id: type.id,
      capacity: 80,
    });
    await created(request, "/facility-booking/bookings", {
      resource_id: resource.id,
      start_at: start.toISOString(),
      end_at: end.toISOString(),
      title: "Guest lecture",
    });
    await signIn(page);
    const panel = widget(page, "Bookings today");
    await expect(panel.getByText("Seminar hall · Guest lecture")).toBeVisible();
    await expect(panel.getByLabel("Booking counts")).toContainText("1 today");
  });
});
