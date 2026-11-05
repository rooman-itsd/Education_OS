import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Studio Instructor dashboard (layout platform/identity/config/dashboards/studio-instructor.yaml, which extends the
 * Faculty layout; the role exists in the arts-academy profile). Part of #323.
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a studio instructor signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Faculty ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml and exports it: the panel renders by its registered title and shows its
 *   empty state, or says its data is not available while the backend is missing (the studio instructor holds the
 *   faculty role's permissions through `extends`);
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it:
 *   projects (#339) and productions (#318), and the inherited timetable-attendance, lms and examinations ones;
 * - data journey: a booking later today on a studio the instructor approves shows in facility-booking.bookings-today.
 *   Facility staff set up the studio and make the booking (the instructor holds facility-booking-approver's grants,
 *   which do not include managing resources).
 *
 * facilities is not in the Trial plan (platform/billing/config/plans.yaml), so the super admin moves the
 * organisation to Standard first. The empty-state tests run before any data is created (serial mode). Loading states
 * are covered by the modules' unit tests, not here.
 */

const TITLE = "Studio Instructor";

const WIDGETS: LayoutWidget[] = [
  // Inherited from the Faculty layout (extends: faculty).
  { id: "timetable-attendance.today-classes", module: "academics/timetable-attendance", batch: "#325" },
  { id: "timetable-attendance.attendance-to-mark", module: "academics/timetable-attendance", batch: "#325" },
  { id: "lms.assignments-to-grade", module: "academics/lms", batch: "#326" },
  { id: "examinations.exam-duties", module: "academics/examinations", batch: "#325" },
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
  // The studio instructor's own widgets.
  {
    // Texts of ReviewsPendingWidget.tsx (practice/portfolio, merged in #413).
    id: "portfolio.reviews-pending",
    module: "practice/portfolio",
    batch: "#322",
    title: "Reviews Pending",
    probe: "/portfolio/items?scope=managed&status=submitted,under_review&page_size=6",
    empty: "No reviews pending",
    unavailable: "Portfolio review data is not available yet.",
  },
  { id: "projects.to-review", module: "practice/projects", batch: "#339" },
  {
    // Texts of ToJudgeWidget.tsx in PR #414 (feat/selection-process/module-build). The widget first lists the open
    // processes; a failure there is what its panel shows.
    id: "selection-process.to-judge",
    module: "practice/selection-process",
    batch: "#322",
    title: "To Judge",
    probe: "/selection-process/processes?status=open&page_size=5",
    empty: "No candidates awaiting review",
    unavailable: "Judging tasks are not available yet.",
  },
  {
    // BookingsTodayWidget.tsx also lists GET /bookings?scope=managed&date=today; the summary answers for both.
    id: "facility-booking.bookings-today",
    module: "facilities/facility-booking",
    batch: "#331",
    title: "Bookings today",
    probe: "/facility-booking/summary?date=today",
    empty: "No bookings today",
    unavailable: "Booking data is not available yet.",
  },
  { id: "productions.in-preparation", module: "practice/productions", batch: "#318" },
];
const SHIPPED = WIDGETS.filter(shipped);

const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let admin: DashboardUser;
let user: DashboardUser;
/** Facility staff: they run the resource register, so they set up the studio the studio instructor approves. */
let facilityStaff: DashboardUser;
/** Per shipped widget id: what its GET answered the studio instructor. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "arts-academy" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "studio-instructor");
  facilityStaff = await addUser(request, admin, "facility-staff");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a studio instructor signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("studio instructor widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the studio-instructor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the studio-instructor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
  test("facility-booking.bookings-today lists a booking later today on a studio the studio instructor approves", async ({ page, request }) => {
    const w = byId("facility-booking.bookings-today");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the facility-booking API answered ${status[w.id]} to the studio-instructor role`);
    // As in facility-staff.spec.ts: the default slot grid is 30 minutes and "today" is the organisation's date in
    // FACILITY_BOOKING_TIMEZONE (UTC by default; the API inherits this process's environment), so book the next free
    // half hour, unless that runs past midnight in that zone. The studio instructor sees bookings on the resources whose
    // approvers list them (scope=managed without booking:read-all).
    const zone = process.env.FACILITY_BOOKING_TIMEZONE || "UTC";
    const day = (d: Date) => d.toLocaleDateString("en-CA", { timeZone: zone }); // YYYY-MM-DD
    const slot = 30 * 60_000;
    const start = new Date(Math.ceil((Date.now() + 5 * 60_000) / slot) * slot);
    const end = new Date(start.getTime() + slot);
    test.skip(day(end) !== day(new Date()), `too close to midnight in ${zone}`);
    const type = await created<{ id: string }>(request, facilityStaff, "/facility-booking/resource-types", { name: "Studio" });
    const resource = await created<{ id: string }>(request, facilityStaff, "/facility-booking/resources", {
      name: "Painting Studio 1",
      type_id: type.id,
      capacity: 12,
      approver_user_ids: [user.id],
    });
    await created(request, facilityStaff, "/facility-booking/bookings", {
      resource_id: resource.id,
      start_at: start.toISOString(),
      end_at: end.toISOString(),
      title: "Life drawing",
    });
    await signIn(page, user);
    const panel = widget(page, "Bookings today");
    await expect(panel.getByText("No bookings today")).toHaveCount(0);
    await expect(panel.getByText("Painting Studio 1 · Life drawing")).toBeVisible();
    await expect(panel.getByLabel("Booking counts")).toContainText("1 today");
  });
});
