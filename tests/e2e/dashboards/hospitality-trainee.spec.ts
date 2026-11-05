import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Hospitality Trainee dashboard (layout platform/identity/config/dashboards/hospitality-trainee.yaml, which extends
 * the Student layout; the role exists in the hospitality-institute profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a hospitality trainee signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Student ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml: the panel renders by its registered title and shows its empty
 *   state, or says its data is not available while the backend is missing (the trainee holds the student role's
 *   permissions through `extends`);
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it
 *   (field-training #339, skill-progress #329, productions #318, placement-career #337); facility-booking is enabled
 *   but exports facility-booking.my-bookings only once sprint batch #331 lands it (PR #395), so that widget skips
 *   until then, with its texts already filled in from the PR's MyBookingsWidget.tsx;
 * - data journey: an item the trainee asks to borrow shows in inventory-equipment.my-loans. Facility staff set up
 *   the item and receive stock; the trainee (loan:request) requests the loan. The other widgets' journeys wait for
 *   their modules.
 *
 * facilities, finance-operations and campus-life are not in the Trial plan (platform/billing/config/plans.yaml), so
 * the super admin moves the organisation to Standard first. The empty-state tests run before any data is created (serial mode). Loading
 * states are covered by the modules' unit tests, not here.
 */

const TITLE = "Hospitality Trainee";

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
  {
    // Texts of NoticesWidget.tsx in PR #473 (sprint batch #338).
    id: "transport.notices",
    module: "campus-life/transport",
    batch: "#338",
    title: "Transport notices",
    probe: "/transport/me/notices?limit=1",
    empty: "No transport notices right now",
    unavailable: "Transport data is not available yet.",
  },
  {
    // Texts of LoansWidget.tsx in PR #476 (sprint batch #338).
    id: "library.loans",
    module: "campus-life/library",
    batch: "#338",
    title: "Library loans",
    probe: "/library/me/loans",
    empty: "No books on loan",
    unavailable: "Library data is not available yet.",
  },
  // The trainee's own widgets.
  { id: "field-training.my-placement", module: "practice/field-training", batch: "#339" },
  {
    id: "skill-progress.my-progress",
    module: "practice/skill-progress",
    batch: "#329",
    title: "My progress",
    probe: "/skill-progress/me/progress",
    empty: "No assessments yet",
    unavailable: "Skill progress data is not available yet.",
    forbidden: "You do not have access to this.",
  },
  {
    // Texts of MyBookingsWidget.tsx and UpcomingBookings.tsx in PR #395 (sprint batch #331).
    id: "facility-booking.my-bookings",
    module: "facilities/facility-booking",
    batch: "#331",
    title: "My bookings",
    probe: "/facility-booking/bookings?scope=mine&from=now&status=pending,confirmed,checked_in&page_size=6",
    empty: "No upcoming bookings",
    unavailable: "Booking data is not available yet.",
  },
  { id: "productions.upcoming", module: "practice/productions", batch: "#318" },
  {
    id: "inventory-equipment.my-loans",
    module: "facilities/inventory-equipment",
    batch: "#254",
    title: "My loans",
    probe: "/inventory-equipment/loans?scope=mine&open=true&page_size=50",
    empty: "Nothing on loan",
    unavailable: "Inventory data is not available yet.",
  },
  {
    id: "placement-career.openings",
    module: "campus-life/placement-career",
    batch: "#337",
    title: "Job openings",
    probe: "/placement-career/me/openings?limit=1",
    empty: "No openings right now",
    unavailable: "Placement data is not available yet.",
    forbidden: "You do not have access to this.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);

const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let admin: DashboardUser;
let user: DashboardUser;
/** Facility staff: they run the catalogue and stores, so they set up the item the trainee borrows. */
let facilityStaff: DashboardUser;
/** Per shipped widget id: what its GET answered the hospitality trainee. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "hospitality-institute" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "hospitality-trainee");
  facilityStaff = await addUser(request, admin, "facility-staff");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a hospitality trainee signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("hospitality-trainee widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the hospitality-trainee layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the hospitality-trainee layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
  test("inventory-equipment.my-loans lists an item the hospitality trainee asks to borrow", async ({ page, request }) => {
    const w = byId("inventory-equipment.my-loans");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the inventory-equipment API answered ${status[w.id]} to the hospitality-trainee role`);
    // Facility staff (item:manage, stock:manage) set up the catalogue and receive stock, as in facility-staff.spec.ts.
    // The item is loanable by default and not consumable (consumables are refused with consumable_not_loanable); the
    // category sets no borrower_role_ids, so any role holding loan:request may borrow (check_loan_line in
    // inventory-equipment's domain/rules.py), and no rule requires approval, so the loan is approved at once.
    const category = await created<{ id: string }>(request, facilityStaff, "/inventory-equipment/categories", { name: "Kitchen tools" });
    const location = await created<{ id: string }>(request, facilityStaff, "/inventory-equipment/locations", { name: "Training kitchen" });
    const item = await created<{ id: string }>(request, facilityStaff, "/inventory-equipment/items", {
      name: "Chef knife set",
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
    await expect(panel.getByText("Chef knife set", { exact: true })).toBeVisible();
    // MyLoansWidget's shortDate: "9 Nov" in the browser's (here the host's) time zone.
    await expect(panel.getByText(`Due ${due.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`)).toBeVisible();
    await expect(panel.getByText("Ready to collect")).toBeVisible();
  });
});
