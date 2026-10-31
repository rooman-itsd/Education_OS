import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Ensemble / Orchestra Director dashboard (layout platform/identity/config/dashboards/ensemble-director.yaml; the
 * role exists in the music-academy profile and extends no other layout). Part of #332.
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: an ensemble director signs in and lands on their dashboard;
 * - for every widget whose module is in apps/frontend/config/modules.enabled.yaml: the panel renders by its
 *   registered title and shows its empty state, or says its data is not available while the backend is missing;
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it:
 *   productions (#318) and selection-process (#322, PR #414);
 * - a data journey once inventory-equipment.low-stock has shipped and its API answers the ensemble-director role:
 *   an instrument the store staff stock below its reorder level shows in the director's low-stock panel (the
 *   director holds inventory-equipment:stock:read but not stock:manage, so a facility-staff user stocks it).
 *
 * facilities is not in the Trial plan (platform/billing/config/plans.yaml), so the super admin moves the
 * organisation to Standard first. The empty-state tests run before any data is created (serial mode). Loading states
 * are covered by the modules' unit tests, not here.
 */

const TITLE = "Ensemble / Orchestra Director";

const WIDGETS: LayoutWidget[] = [
  { id: "productions.in-preparation", module: "practice/productions", batch: "#318" },
  { id: "productions.calendar", module: "practice/productions", batch: "#318" },
  {
    // Texts of OpenCallsWidget.tsx in PR #414 (feat/selection-process/module-build).
    id: "selection-process.open-calls",
    module: "practice/selection-process",
    batch: "#322",
    title: "Open Calls",
    probe: "/selection-process/processes?status=open&page_size=6",
    empty: "No open calls right now",
    unavailable: "Open calls are not available yet.",
  },
  {
    id: "inventory-equipment.low-stock",
    module: "facilities/inventory-equipment",
    batch: "#331",
    title: "Low stock",
    probe: "/inventory-equipment/low-stock",
    empty: "Stock is healthy",
    unavailable: "Inventory data is not available yet.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let user: DashboardUser;
/** A facility-staff user (inventory-equipment item:manage and stock:manage), who stocks the store. */
let store: DashboardUser;
/** Per shipped widget id: what its GET answered the ensemble director. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "music-academy" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "ensemble-director");
  store = await addUser(request, admin, "facility-staff");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`an ensemble director signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("ensemble director widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the ensemble-director layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the ensemble-director layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
  test("inventory-equipment.low-stock lists an instrument below its reorder level", async ({ page, request }) => {
    const w = byId("inventory-equipment.low-stock");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the inventory-equipment API answered ${status[w.id]} to the ensemble-director role`);
    // As in facility-staff.spec.ts: the store staff add a category, a location and a consumable item with a reorder
    // level of 5, and receive 2 of it.
    const category = await created<{ id: string }>(request, store, "/inventory-equipment/categories", { name: "Strings" });
    const location = await created<{ id: string }>(request, store, "/inventory-equipment/locations", { name: "Instrument store" });
    const item = await created<{ id: string }>(request, store, "/inventory-equipment/items", {
      name: "Violin string sets",
      category_id: category.id,
      tracking: "quantity",
      consumable: true,
      reorder_level: 5,
    });
    await created(request, store, "/inventory-equipment/movements", { kind: "receipt", item_id: item.id, quantity: 2, to_location_id: location.id });
    await signIn(page, user);

    const panel = widget(page, "Low stock");
    await expect(panel.getByText("Stock is healthy")).toHaveCount(0);
    await expect(panel.getByText("Violin string sets")).toBeVisible();
    await expect(panel.getByText("2 piece left")).toBeVisible();
  });
});

// Backend-dependent: these need their module's API to create the data through, so nothing here is faked.
test.describe("with productions and selection data", () => {
  test.fixme("productions.in-preparation and productions.calendar show a recital in rehearsal", async () => {
    // practice/productions (sprint batch #318) has no frontend or API yet. Then: create a production ("Spring
    // recital") with a performance date in the next weeks, move it into preparation, and expect it in both panels.
  });

  test.fixme("selection-process.open-calls lists an audition opened for the orchestra", async () => {
    // practice/selection-process (sprint batch #322, PR #414). As the ensemble director
    // (selection-process-coordinator through module_roles) create a process with a stage and open it; expect
    // "No open calls right now" gone and the row with its title, "1 stage" and "Open".
  });
});
