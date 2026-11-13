import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { FARM, seedPlacement } from "./field-training-data";
import { seedProject, TRIAL } from "./projects-data";
import { created, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Farm Supervisor dashboard (layout platform/identity/config/dashboards/farm-supervisor.yaml, which extends the
 * Faculty layout; the role exists in the agriculture-college profile). Issue #341.
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a farm supervisor signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Faculty ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml and exports the widget: the panel renders by its registered title and
 *   shows its empty state, or says its data is not available while the backend is missing;
 * - widgets that are not on the dashboard yet are skipped, naming the module and the sprint batch that builds it
 *   (projects and field-training #339, and the inherited timetable-attendance, lms and examinations ones). The
 *   projects and field-training entries already carry the texts of their open pull requests (#506, #504);
 * - data journeys: a consumable below its reorder level shows in inventory-equipment.low-stock, and a booking later
 *   today on a field the farm supervisor approves in facility-booking.bookings-today. Facility staff create both (the
 *   farm supervisor reads stock and approves bookings, but does not manage the stores or the resource register).
 *   A trainee the coordinator places on a farm and starts, whose log entry waits for the supervisor, shows in
 *   `field-training.trainees-to-assess`, and a research trial the research lead sets up with the supervisor as guide
 *   shows in `projects.active`; each skips until its module is enabled.
 *
 * facilities is not in the Trial plan (platform/billing/config/plans.yaml), so the super admin moves the organisation
 * to Standard first. The empty-state tests run before any data is created (serial mode). Loading states are covered
 * by the modules' unit tests, not here.
 */

const TITLE = "Farm Supervisor";

const WIDGETS: LayoutWidget[] = [
  // Inherited from the Faculty layout (extends: faculty).
  { id: "timetable-attendance.today-classes", module: "academics/timetable-attendance", batch: "#325" },
  { id: "timetable-attendance.attendance-to-mark", module: "academics/timetable-attendance", batch: "#325" },
  {
    id: "lms.assignments-to-grade",
    module: "academics/lms",
    batch: "#326",
    title: "Assignments to grade",
    probe: "/lms/me/grading-queue",
    empty: "Nothing waiting to be graded",
    unavailable: "Course data is not available yet.",
  },
  {
    id: "examinations.exam-duties",
    module: "academics/examinations",
    batch: "#325",
    title: "My exam duties",
    probe: "/examinations/me/duties",
    empty: "No upcoming exam duties.",
    unavailable: "Examinations data is not available yet.",
  },
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
  // The farm supervisor's own widgets.
  {
    // Texts of the widget in PR #504 (not merged yet).
    id: "field-training.trainees-to-assess",
    module: "practice/field-training",
    batch: "#339",
    title: "Trainees to assess",
    probe: "/field-training/me/trainees?limit=5",
    empty: "Nothing to assess right now",
    unavailable: "Field training data is not available yet.",
    forbidden: "You do not have access to this.",
  },
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
    // Texts of the widget in PR #506 (not merged yet).
    id: "projects.active",
    module: "practice/projects",
    batch: "#339",
    title: "Active projects",
    probe: "/projects/projects?status=active&limit=5",
    empty: "No active projects",
    unavailable: "Projects data is not available yet.",
    forbidden: "You do not have access to this.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let user: DashboardUser;
/** Facility staff: they run the stores and the resource register, so they create the data the journeys look for. */
let facilityStaff: DashboardUser;
/**
 * Who sets up the supervisor's data: the field-training coordinator (a module role no agriculture-college profile role
 * holds, so the user has it directly), the research lead (projects-coordinator, who creates the trial and names the
 * supervisor as guide) and the field trainee on the placement and the trial.
 */
let coordinator: DashboardUser;
let researchLead: DashboardUser;
let trainee: DashboardUser;
/** Per shipped widget id: what its GET answered the farm supervisor. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "agriculture-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "farm-supervisor");
  facilityStaff = await addUser(request, admin, "facility-staff");
  coordinator = await addUser(request, admin, "field-training-coordinator");
  researchLead = await addUser(request, admin, "research-lead");
  trainee = await addUser(request, admin, "field-trainee");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a farm supervisor signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("farm-supervisor widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the farm-supervisor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the farm-supervisor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
  test("inventory-equipment.low-stock lists a consumable below its reorder level", async ({ page, request }) => {
    const w = byId("inventory-equipment.low-stock");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the inventory-equipment API answered ${status[w.id]} to the farm-supervisor role`);
    // As in facility-staff.spec.ts, made by facility staff (stock:manage); the farm supervisor holds stock:read.
    const category = await created<{ id: string }>(request, facilityStaff, "/inventory-equipment/categories", { name: "Farm consumables" });
    const location = await created<{ id: string }>(request, facilityStaff, "/inventory-equipment/locations", { name: "Seed store" });
    const item = await created<{ id: string }>(request, facilityStaff, "/inventory-equipment/items", {
      name: "Seed trays",
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
    await expect(panel.getByText("Seed trays")).toBeVisible();
    await expect(panel.getByText("2 piece left")).toBeVisible();
  });

  test("facility-booking.bookings-today lists a booking later today on a field the farm supervisor approves", async ({ page, request }) => {
    const w = byId("facility-booking.bookings-today");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the facility-booking API answered ${status[w.id]} to the farm-supervisor role`);
    // As in facility-staff.spec.ts: the default slot grid is 30 minutes and "today" is the organisation's date in
    // FACILITY_BOOKING_TIMEZONE (UTC by default; the API inherits this process's environment), so book the next free
    // half hour, unless that runs past midnight in that zone. The stage manager sees bookings on the resources
    // whose approvers list them (scope=managed without booking:read-all).
    const zone = process.env.FACILITY_BOOKING_TIMEZONE || "UTC";
    const day = (d: Date) => d.toLocaleDateString("en-CA", { timeZone: zone }); // YYYY-MM-DD
    const slot = 30 * 60_000;
    const start = new Date(Math.ceil((Date.now() + 5 * 60_000) / slot) * slot);
    const end = new Date(start.getTime() + slot);
    test.skip(day(end) !== day(new Date()), `too close to midnight in ${zone}`);
    const type = await created<{ id: string }>(request, facilityStaff, "/facility-booking/resource-types", { name: "Field" });
    const resource = await created<{ id: string }>(request, facilityStaff, "/facility-booking/resources", {
      name: "North field",
      type_id: type.id,
      capacity: 40,
      approver_user_ids: [user.id],
    });
    await created(request, facilityStaff, "/facility-booking/bookings", {
      resource_id: resource.id,
      start_at: start.toISOString(),
      end_at: end.toISOString(),
      title: "Irrigation inspection",
    });
    await signIn(page, user);
    const panel = widget(page, "Bookings today");
    await expect(panel.getByText("No bookings today")).toHaveCount(0);
    await expect(panel.getByText("North field · Irrigation inspection")).toBeVisible();
    await expect(panel.getByLabel("Booking counts")).toContainText("1 today");
  });
});

test.describe("with field-training and projects data", () => {
  test("field-training.trainees-to-assess lists a trainee whose entry waits for the farm supervisor", async ({ page, request }) => {
    const w = byId("field-training.trainees-to-assess");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the field-training API answered ${status[w.id]} to the farm-supervisor role`);
    // The coordinator places the trainee on a farm opening and starts it; the trainee logs today's hours and the entry
    // waits for the supervisor named on the site and the opening (the farm supervisor).
    await seedPlacement(request, { coordinator, supervisor: user, trainee }, { start: true, log: true, names: FARM });
    await signIn(page, user);
    const panel = widget(page, "Trainees to assess");
    await expect(panel.getByText("Nothing to assess right now")).toHaveCount(0);
    // No identity lookup gives the module the trainee's name yet, so the row is titled "Trainee".
    const row = panel.getByRole("list", { name: "Trainees to assess" }).getByRole("listitem").filter({ hasText: FARM.opening });
    await expect(row).toContainText(FARM.site);
    await expect(row).toContainText("1 entry to verify");
  });

  test("projects.active lists a research trial the farm supervisor guides", async ({ page, request }) => {
    const w = byId("projects.active");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the projects API answered ${status[w.id]} to the farm-supervisor role`);
    // projects:guidance:read: a guide sees the projects they guide. The research lead (projects:project:manage) creates
    // the trial active, with the trainee as lead and the farm supervisor as guide.
    await seedProject(request, { coordinator: researchLead, guide: user, lead: trainee });
    await signIn(page, user);
    const panel = widget(page, "Active projects");
    await expect(panel.getByText("No active projects")).toHaveCount(0);
    const row = panel.getByRole("list", { name: "Active projects" }).getByRole("listitem").filter({ hasText: TRIAL });
    await expect(row).toContainText("Research · 1 member");
    await expect(row.getByLabel("Milestones accepted")).toHaveText("0/0");
  });
});
