import { expect, test } from "@playwright/test";
import { organisationWithUser, type DashboardUser } from "./organisation";
import { created, dayFromNow, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Artist dashboard (layout platform/identity/config/dashboards/artist.yaml, which extends the Student layout; the
 * role exists in the arts-academy profile, ADR-0004).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: an artist user signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Student ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml: the panel renders by its registered title and shows its empty
 *   state, or says its data is not available while the backend is missing (the artist holds the student role's
 *   permissions through `extends`);
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it;
 * - with inventory-equipment data: a loan requested for studio equipment appears in inventory-equipment.my-loans.
 *
 * facilities, finance-operations and campus-life are not in the Trial plan, so the super admin moves the organisation
 * to Standard first. The empty-state tests run before any data is created (serial mode). Loading states are covered
 * by the modules' unit tests, not here.
 */

const TITLE = "Artist";

const WIDGETS: LayoutWidget[] = [
  // Inherited from the Student layout (extends: student).
  { id: "timetable-attendance.today", module: "academics/timetable-attendance", batch: "#325" },
  { id: "timetable-attendance.attendance-summary", module: "academics/timetable-attendance", batch: "#325" },
  { id: "examinations.upcoming-assessments", module: "academics/examinations", batch: "#325" },
  { id: "lms.course-materials", module: "academics/lms", batch: "#326" },
  {
    id: "fees-accounts.fee-dues",
    module: "finance-operations/fees-accounts",
    batch: "#107",
    title: "Fee dues",
    probe: "/fees-accounts/me/dues",
    empty: "No fees due",
    unavailable: "Fee data is not available yet.",
  },
  {
    id: "hostel.notices",
    module: "campus-life/hostel",
    batch: "#338",
    title: "Hostel notices",
    probe: "/hostel/me/notices?limit=1",
    empty: "No hostel notices right now",
    unavailable: "Could not load hostel notices",
    forbidden: "Could not load hostel notices",
  },
  { id: "transport.notices", module: "campus-life/transport", batch: "#338" },
  { id: "library.loans", module: "campus-life/library", batch: "#338" },
  // The artist's own widgets.
  {
    id: "portfolio.my-portfolio",
    module: "practice/portfolio",
    batch: "#322",
    title: "My Portfolio",
    probe: "/portfolio/items?scope=mine",
    empty: "No portfolio items yet",
    unavailable: "Portfolio data is not available yet.",
  },
  { id: "projects.my-projects", module: "practice/projects", batch: "#339" },
  { id: "facility-booking.my-bookings", module: "facilities/facility-booking", batch: "#331" },
  {
    id: "selection-process.upcoming",
    module: "practice/selection-process",
    batch: "#322",
    title: "Upcoming Selections",
    probe: "/selection-process/processes?status=open&limit=5",
    empty: "No upcoming selection processes",
    unavailable: "Selection process data is not available yet.",
  },
  { id: "productions.upcoming", module: "practice/productions", batch: "#318" },
  {
    id: "inventory-equipment.my-loans",
    module: "facilities/inventory-equipment",
    batch: "#109",
    title: "My loans",
    probe: "/inventory-equipment/loans?scope=mine&open=true",
    empty: "Nothing on loan",
    unavailable: "Inventory and equipment data is not available yet.",
  },
];

const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the artist user. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  user = await organisationWithUser(request, {
    academyType: "arts-academy",
    role: "artist",
    extraRoles: ["facility-staff"],
  });
  await standardPlan(request, user.organisation.id);
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`an artist signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("artist widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the artist layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, says its data is not available yet, or says the role has no access", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the artist layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    for (const w of SHIPPED) await expectBody(page, w, status[w.id] ?? 0);
  });

  test("inventory-equipment.my-loans displays correct title and empty state before data seeding", async ({ page }) => {
    const w = byId("inventory-equipment.my-loans");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(status[w.id] !== 200, `the inventory-equipment API answered ${status[w.id]} to the artist role`);
    await signIn(page, user);
    const panel = widget(page, "My loans");
    await expect(panel).toBeVisible();
    await expect(panel.getByRole("heading", { name: "My loans", exact: true })).toBeVisible();
    await expect(panel.getByText("Nothing on loan", { exact: true })).toBeVisible();
    await expect(panel.getByText("Equipment you borrow appears here with its due date.", { exact: true })).toBeVisible();
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

test.describe("with inventory-equipment data", () => {
  test("inventory-equipment.my-loans lists open equipment borrowed by the artist and enforces tenant isolation", async ({ page, request }) => {
    const w = byId("inventory-equipment.my-loans");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(status[w.id] !== 200, `the inventory-equipment API answered ${status[w.id]} to the artist role`);

    // 1. Seed equipment and loan in the primary organisation (user).
    const category = await created<{ id: string }>(request, user, "/inventory-equipment/categories", {
      name: "Studio Gear",
    });
    const location = await created<{ id: string }>(request, user, "/inventory-equipment/locations", {
      name: "Art Studio Store",
    });
    const item = await created<{ id: string }>(request, user, "/inventory-equipment/items", {
      name: "Easels & Canvas Stand",
      category_id: category.id,
      tracking: "quantity",
      consumable: false,
    });
    await created(request, user, "/inventory-equipment/movements", {
      kind: "receipt",
      item_id: item.id,
      quantity: 5,
      to_location_id: location.id,
    });
    await created(request, user, "/inventory-equipment/loans", {
      lines: [{ item_id: item.id, quantity: 1 }],
      due_at: dayFromNow(3),
      purpose: "Oil painting practicals",
    });

    // 2. Cross-tenant isolation check: create an isolated second organisation with its own loan.
    const orgBUser = await organisationWithUser(request, {
      academyType: "arts-academy",
      role: "artist",
      extraRoles: ["facility-staff"],
    });
    await standardPlan(request, orgBUser.organisation.id);

    const catB = await created<{ id: string }>(request, orgBUser, "/inventory-equipment/categories", {
      name: "Sculpture Studio Gear",
    });
    const locB = await created<{ id: string }>(request, orgBUser, "/inventory-equipment/locations", {
      name: "Sculpture Storage B",
    });
    const itemB = await created<{ id: string }>(request, orgBUser, "/inventory-equipment/items", {
      name: "Stone Carving Chisels - Org B",
      category_id: catB.id,
      tracking: "quantity",
      consumable: false,
    });
    await created(request, orgBUser, "/inventory-equipment/movements", {
      kind: "receipt",
      item_id: itemB.id,
      quantity: 3,
      to_location_id: locB.id,
    });
    await created(request, orgBUser, "/inventory-equipment/loans", {
      lines: [{ item_id: itemB.id, quantity: 1 }],
      due_at: dayFromNow(5),
      purpose: "Monumental sculpture",
    });

    // 3. Sign in as the primary organisation's artist.
    await signIn(page, user);
    const panel = widget(page, "My loans");

    // Primary organisation's loan must be visible.
    await expect(panel.getByText("Easels & Canvas Stand")).toBeVisible();
    await expect(panel.getByText(/^Due /)).toBeVisible();
    await expect(panel.getByText("Nothing on loan")).toHaveCount(0);

    // Cross-tenant assertion: second organisation's loan must NEVER appear on this dashboard.
    await expect(panel.getByText("Stone Carving Chisels - Org B")).toHaveCount(0);
  });
});

// Backend-dependent: these need their module's API to create data through once the modules are merged.
test.fixme("portfolio.my-portfolio lists the artist's artworks and creative submissions", async () => {
  // practice/portfolio (sprint batch #322, PR #413); an artwork is a portfolio item.
});

test.fixme("projects.my-projects lists the artist's studio projects", async () => {
  // practice/projects (sprint batch #339).
});

test.fixme("facility-booking.my-bookings lists the artist's reserved art studio or darkroom slots", async () => {
  // facilities/facility-booking (sprint batch #331).
});

test.fixme("selection-process.upcoming lists casting calls or residency selections open for submission", async () => {
  // practice/selection-process (sprint batch #322).
});

test.fixme("productions.upcoming lists fine art exhibitions or gallery showcases the artist participates in", async () => {
  // practice/productions (sprint batch #318).
});

