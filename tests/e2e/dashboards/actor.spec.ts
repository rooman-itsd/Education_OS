import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Actor dashboard (layout platform/identity/config/dashboards/actor.yaml, which extends the Student layout; the role exists in the
 * theatre-academy profile). Issue #319.
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: an actor signs in and lands on their dashboard;
 * - for every widget of the layout whose module is in apps/frontend/config/modules.enabled.yaml and exports it: the
 *   panel renders by its registered title and shows its empty state, or says its data is not available while the
 *   backend is missing;
 * - widgets of modules not enabled yet, or not exported yet, are skipped, naming the module and the sprint batch that
 *   builds it: productions (#318, PR #454), timetable-attendance and examinations (#325), lms (#326), transport and
 *   library (#338);
 * - data journey: an item the actor asks to borrow shows in inventory-equipment.my-loans. Facility staff set up the
 *   item and receive stock; the actor (loan:request) requests the loan. The other widgets' journeys wait for their
 *   modules.
 *
 * facilities is not in the Trial plan (platform/billing/config/plans.yaml), so the super admin moves the organisation
 * to Standard first. The empty-state tests run before any data is created (serial mode). Loading states are covered
 * by the modules' unit tests, not here.
 */

const TITLE = "Actor";

const WIDGETS: LayoutWidget[] = [
  // Inherited from the Student layout (extends: student).
  { id: "timetable-attendance.today", module: "academics/timetable-attendance", batch: "#325" },
  { id: "timetable-attendance.attendance-summary", module: "academics/timetable-attendance", batch: "#325" },
  { id: "examinations.upcoming-assessments", module: "academics/examinations", batch: "#325" },
  {
    id: "lms.course-materials",
    module: "academics/lms",
    batch: "#326",
    title: "Course materials",
    probe: "/lms/me/course-materials?limit=1",
    empty: "No new course materials",
    unavailable: "Course data is not available yet.",
  },

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
  {
    id: "transport.notices",
    module: "campus-life/transport",
    batch: "#338",
    title: "Transport notices",
    probe: "/transport/me/notices?limit=1",
    empty: "No transport notices right now",
    unavailable: "Transport data is not available yet.",
  },
  {
    id: "library.loans",
    module: "campus-life/library",
    batch: "#338",
    title: "Library loans",
    probe: "/library/me/loans",
    empty: "No books on loan",
    unavailable: "Library data is not available yet.",
  },
  // The actor's own widgets.
  {
    id: "productions.my-roles",
    module: "practice/productions",
    batch: "#318",
    title: "My parts",
    probe: "/productions/my-roles",
    empty: "No parts yet",
    unavailable: "Production data is not available yet.",
  },
  {
    // Texts of UpcomingWidget.tsx (practice/selection-process, merged in #414).
    id: "selection-process.upcoming",
    module: "practice/selection-process",
    batch: "#322",
    title: "Upcoming Selection Events",
    probe: "/selection-process/slots/upcoming?limit=6",
    empty: "No upcoming selection rounds",
    unavailable: "Schedule data is not available yet.",
  },
  {
    // Texts of MyBookingsWidget.tsx and UpcomingBookings.tsx (facility-booking, merged in #395).
    id: "facility-booking.my-bookings",
    module: "facilities/facility-booking",
    batch: "#331",
    title: "My bookings",
    probe: "/facility-booking/bookings?scope=mine&from=now&status=pending,confirmed,checked_in&page_size=6",
    empty: "No upcoming bookings",
    unavailable: "Booking data is not available yet.",
  },
  {
    // Texts of MyPortfolioWidget.tsx (practice/portfolio, merged in #413).
    id: "portfolio.my-portfolio",
    module: "practice/portfolio",
    batch: "#322",
    title: "My Portfolio",
    probe: "/portfolio/items?scope=mine&page_size=6",
    empty: "No portfolio items yet",
    unavailable: "Portfolio data is not available yet.",
  },
  {
    id: "inventory-equipment.my-loans",
    module: "facilities/inventory-equipment",
    batch: "#331",
    title: "My loans",
    probe: "/inventory-equipment/loans?scope=mine&open=true&page_size=50",
    empty: "Nothing on loan",
    unavailable: "Inventory data is not available yet.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let admin: DashboardUser;
let user: DashboardUser;
/** Facility staff: they run the catalogue and stores, so they set up the item the actor borrows. */
let facilityStaff: DashboardUser;
/** Per shipped widget id: what its GET answered the actor. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "theatre-academy" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "actor");
  facilityStaff = await addUser(request, admin, "facility-staff");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`an actor signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("actor widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the actor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the actor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
  test("inventory-equipment.my-loans lists an item the actor asks to borrow", async ({ page, request }) => {
    const w = byId("inventory-equipment.my-loans");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the inventory-equipment API answered ${status[w.id]} to the actor role`);
    // Facility staff (item:manage, stock:manage) set up the catalogue and receive stock, as in production-manager.spec.ts.
    // The item is loanable by default and not consumable (consumables are refused with consumable_not_loanable); the
    // category sets no borrower_role_ids, so any role holding loan:request may borrow (check_loan_line in
    // inventory-equipment's domain/rules.py), and no rule requires approval, so the loan is approved at once.
    const category = await created<{ id: string }>(request, facilityStaff, "/inventory-equipment/categories", { name: "Costumes" });
    const location = await created<{ id: string }>(request, facilityStaff, "/inventory-equipment/locations", { name: "Wardrobe store" });
    const item = await created<{ id: string }>(request, facilityStaff, "/inventory-equipment/items", {
      name: "Velvet cloak",
      category_id: category.id,
      tracking: "quantity",
    });
    await created(request, facilityStaff, "/inventory-equipment/movements", {
      kind: "receipt",
      item_id: item.id,
      quantity: 2,
      to_location_id: location.id,
    });
    // A week ahead: within the default max_loan_days of 14.
    const due = new Date(Date.now() + 7 * 86_400_000);
    await created(request, user, "/inventory-equipment/loans", { lines: [{ item_id: item.id, quantity: 1 }], due_at: due.toISOString() });
    await signIn(page, user);
    const panel = widget(page, "My loans");
    await expect(panel.getByText("Nothing on loan")).toHaveCount(0);
    await expect(panel.getByText("Velvet cloak", { exact: true })).toBeVisible();
    // MyLoansWidget's shortDate: "9 Nov" in the browser's (here the host's) time zone.
    await expect(panel.getByText(`Due ${due.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`)).toBeVisible();
    await expect(panel.getByText("Ready to collect")).toBeVisible();
  });
});
