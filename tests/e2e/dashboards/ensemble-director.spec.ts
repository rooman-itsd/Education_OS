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
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it;
 * - data journeys, each once its widget has shipped and its API answers the ensemble-director role:
 *   - an instrument the store staff stock below its reorder level shows in the low-stock panel (the director holds
 *     inventory-equipment:stock:read but not stock:manage, so a facility-staff user stocks it);
 *   - a recital the director puts into preparation shows in productions.in-preparation, and one they schedule
 *     shows in productions.calendar (the music-academy profile role holds productions:production:manage);
 *   - an orchestra audition the director opens shows in selection-process.open-calls (selection-process-coordinator
 *     through module_roles).
 *
 * facilities is not in the Trial plan (platform/billing/config/plans.yaml), so the super admin moves the
 * organisation to Standard first. The empty-state tests run before any data is created (serial mode). Loading states
 * are covered by the modules' unit tests, not here.
 */

const TITLE = "Ensemble / Orchestra Director";

const WIDGETS: LayoutWidget[] = [
  {
    id: "productions.in-preparation",
    module: "practice/productions",
    batch: "#318",
    title: "In preparation",
    probe: "/productions/in-preparation",
    empty: "Nothing in preparation",
    unavailable: "Production data is not available yet.",
  },
  {
    id: "productions.calendar",
    module: "practice/productions",
    batch: "#318",
    title: "Production calendar",
    probe: "/productions/calendar",
    empty: "Nothing scheduled",
    unavailable: "Production data is not available yet.",
  },
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

test.describe("with productions and selection data", () => {
  test("productions.in-preparation and productions.calendar show the director's recitals", async ({ page, request }) => {
    const prep = byId("productions.in-preparation");
    const cal = byId("productions.calendar");
    test.skip(!shipped(prep), waitingFor(prep));
    test.skip(!ready(prep.id), `the productions API answered ${status[prep.id]} to the ensemble-director role`);
    test.skip(!ready(cal.id), `the productions API answered ${status[cal.id]} to the ensemble-director role`);
    // A production is in one panel or the other: in-preparation lists planned and in-preparation ones, the calendar
    // scheduled ones (PREPARING_STATUSES and CALENDAR_STATUSES in productions' domain/rules.py). So the director
    // puts one recital into preparation and schedules another two weeks out, at 19:00 in this host's time zone,
    // which the browser shares (CalendarWidget shows the venue and shortTime).
    const spring = await created<{ id: string }>(request, user, "/productions/productions", { title: "Spring recital", kind: "recital" });
    await created(request, user, `/productions/productions/${spring.id}/preparation`, {});
    const evening = await created<{ id: string }>(request, user, "/productions/productions", { title: "Chamber evening", kind: "recital" });
    const starts = new Date(Date.now() + 14 * 86_400_000);
    starts.setHours(19, 0, 0, 0);
    await created(request, user, `/productions/productions/${evening.id}/schedule`, {
      starts_at: starts.toISOString(),
      ends_at: new Date(starts.getTime() + 2 * 60 * 60_000).toISOString(),
      venue: "Concert hall",
    });
    await signIn(page, user);

    const preparing = widget(page, "In preparation");
    await expect(preparing.getByText("Nothing in preparation")).toHaveCount(0);
    const prepRow = preparing.getByRole("list", { name: "In preparation" }).getByRole("listitem").filter({ hasText: "Spring recital" });
    await expect(prepRow).toContainText("ready to schedule");
    await expect(prepRow).toContainText("No date");
    await expect(preparing.getByText("Chamber evening")).toHaveCount(0);

    const calendar = widget(page, "Production calendar");
    await expect(calendar.getByText("Nothing scheduled")).toHaveCount(0);
    const calRow = calendar.getByRole("list", { name: "What is on" }).getByRole("listitem").filter({ hasText: "Chamber evening" });
    await expect(calRow).toContainText("Concert hall · 19:00");
    await expect(calRow).toContainText("Recital");
    await expect(calendar.getByText("Spring recital")).toHaveCount(0);
  });

  test("selection-process.open-calls lists an audition opened for the orchestra", async ({ page, request }) => {
    const w = byId("selection-process.open-calls");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the selection-process API answered ${status[w.id]} to the ensemble-director role`);
    // As in moot-court-coordinator.spec.ts: the director names the kind of selection, creates a process with one
    // stage and opens it for registration.
    const type = await created<{ id: string }>(request, user, "/selection-process/process-types", { name: "Orchestra audition" });
    const audition = await created<{ id: string }>(request, user, "/selection-process/processes", {
      type_id: type.id,
      title: "Symphony orchestra auditions 2026",
      stages: [{ name: "Prepared excerpt", sequence: 1 }],
    });
    await created(request, user, `/selection-process/processes/${audition.id}/open`, {});
    await signIn(page, user);

    const panel = widget(page, "Open Calls");
    await expect(panel.getByText("No open calls right now")).toHaveCount(0);
    const row = panel.getByRole("list", { name: "Open selection calls" }).getByRole("listitem").filter({ hasText: "Symphony orchestra auditions 2026" });
    await expect(row).toContainText("1 stage");
    await expect(row).toContainText("Open");
  });
});
