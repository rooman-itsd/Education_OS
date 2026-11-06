import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Field Trainee dashboard (layout platform/identity/config/dashboards/field-trainee.yaml, which extends the Student
 * layout; the role exists in the agriculture-college profile). Issue #341.
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a field trainee signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Student ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml and exports the widget: the panel renders by its registered title and
 *   shows its empty state, or says its data is not available while the backend is missing (the field trainee holds
 *   the trainee role's permissions through `extends`);
 * - widgets that are not on the dashboard yet are skipped, naming the module and the sprint batch that builds it
 *   (projects and field-training #339, and the inherited timetable-attendance, examinations and lms ones, and
 *   transport and library until they are enabled). The projects and field-training entries already carry the texts
 *   of their open pull requests (#506, #504), so the journey starts checking them the day the module is enabled;
 * - data journey: a booking the trainee makes for a resource facility staff set up shows in
 *   facility-booking.my-bookings (the trainee has booking:create). The other widgets' journeys wait for their modules.
 *
 * facilities, finance-operations and campus-life are not in the Trial plan (platform/billing/config/plans.yaml), so
 * the super admin moves the organisation to Standard first. The empty-state tests run before any data is created
 * (serial mode). Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Field Trainee";

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
    // Texts of NoticesWidget.tsx in PR #473 (sprint batch #338), which is on main; the module is not enabled yet.
    id: "transport.notices",
    module: "campus-life/transport",
    batch: "#338",
    title: "Transport notices",
    probe: "/transport/me/notices?limit=1",
    empty: "No transport notices right now",
    unavailable: "Transport data is not available yet.",
  },
  {
    // Texts of LoansWidget.tsx in PR #476 (sprint batch #338), which is on main; the module is not enabled yet.
    id: "library.loans",
    module: "campus-life/library",
    batch: "#338",
    title: "Library loans",
    probe: "/library/me/loans",
    empty: "No books on loan",
    unavailable: "Library data is not available yet.",
  },
  // The field trainee's own widgets.
  {
    // Texts of the widget in PR #504 (not merged yet).
    id: "field-training.my-placement",
    module: "practice/field-training",
    batch: "#339",
    title: "My placement",
    probe: "/field-training/me/placements",
    empty: "No placement yet",
    unavailable: "Field training data is not available yet.",
    forbidden: "You do not have access to this.",
  },
  {
    // Texts of the widget in PR #504 (not merged yet).
    id: "field-training.hours-logged",
    module: "practice/field-training",
    batch: "#339",
    title: "Hours logged",
    probe: "/field-training/me/hours",
    empty: "No hours to show yet",
    unavailable: "Field training data is not available yet.",
    forbidden: "You do not have access to this.",
  },
  {
    // Texts of the widget in PR #506 (not merged yet).
    id: "projects.my-projects",
    module: "practice/projects",
    batch: "#339",
    title: "My projects",
    probe: "/projects/me/projects",
    empty: "You are not on a project yet",
    unavailable: "Projects data is not available yet.",
    forbidden: "You do not have access to this.",
  },
  {
    // Texts of MyBookingsWidget.tsx and UpcomingBookings.tsx.
    id: "facility-booking.my-bookings",
    module: "facilities/facility-booking",
    batch: "#331",
    title: "My bookings",
    probe: "/facility-booking/bookings?scope=mine&from=now&status=pending,confirmed,checked_in&page_size=6",
    empty: "No upcoming bookings",
    unavailable: "Booking data is not available yet.",
  },
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
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let user: DashboardUser;
/** Facility staff set up the bookable resource; the trainee only books it. */
let staff: DashboardUser;
/** Per shipped widget id: what its GET answered the field trainee. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "agriculture-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "field-trainee");
  staff = await addUser(request, admin, "facility-staff");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a field trainee signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("field-trainee widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the field-trainee layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the field-trainee layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

test.describe("with facility-booking data", () => {
  test("facility-booking.my-bookings lists a booking the trainee made for later today", async ({ page, request }) => {
    const w = byId("facility-booking.my-bookings");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the facility-booking API answered ${status[w.id]} to the field-trainee role`);
    // The default slot grid is 30 minutes and "today" is the organisation's date in FACILITY_BOOKING_TIMEZONE
    // (UTC by default; the API inherits this process's environment): book the next free half hour, unless that
    // runs past midnight in that zone.
    const zone = process.env.FACILITY_BOOKING_TIMEZONE || "UTC";
    const day = (d: Date) => d.toLocaleDateString("en-CA", { timeZone: zone }); // YYYY-MM-DD
    const slot = 30 * 60_000;
    const start = new Date(Math.ceil((Date.now() + 5 * 60_000) / slot) * slot);
    const end = new Date(start.getTime() + slot);
    test.skip(day(end) !== day(new Date()), `too close to midnight in ${zone}`);
    const type = await created<{ id: string }>(request, staff, "/facility-booking/resource-types", { name: "Farm" });
    const resource = await created<{ id: string }>(request, staff, "/facility-booking/resources", {
      name: "Demonstration farm",
      type_id: type.id,
      capacity: 25,
    });
    await created(request, user, "/facility-booking/bookings", {
      resource_id: resource.id,
      start_at: start.toISOString(),
      end_at: end.toISOString(),
      title: "Soil sampling practical",
    });
    await signIn(page, user);
    const panel = widget(page, "My bookings");
    await expect(panel.getByText("No upcoming bookings")).toHaveCount(0);
    await expect(panel.getByRole("list", { name: "My bookings" }).getByText("Demonstration farm · Soil sampling practical")).toBeVisible();
  });
});
