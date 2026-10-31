import { expect, test } from "@playwright/test";
import { organisationWithUser, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Music Teacher dashboard (layout platform/identity/config/dashboards/music-teacher.yaml, which extends the Faculty
 * layout; the role exists in the music-academy profile). Part of #332.
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a music teacher signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Faculty ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml: the panel renders by its registered title and shows its empty
 *   state, or says its data is not available while the backend is missing (the music teacher holds the faculty
 *   role's permissions through `extends`);
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it:
 *   skill-progress (#329), selection-process and portfolio (#322, PRs #414 and #413);
 * - the data journey is fixme (see the end of this file).
 *
 * facilities is not in the Trial plan (platform/billing/config/plans.yaml), so the super admin moves the
 * organisation to Standard first. The empty-state tests run before any data is created (serial mode). Loading states
 * are covered by the modules' unit tests, not here.
 */

const TITLE = "Music Teacher";

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
  // The music teacher's own widgets.
  { id: "skill-progress.assessments-due", module: "practice/skill-progress", batch: "#329" },
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
    // Texts of ReviewsPendingWidget.tsx in PR #413 (feat/portfolio/module-build).
    id: "portfolio.reviews-pending",
    module: "practice/portfolio",
    batch: "#322",
    title: "Reviews Pending",
    probe: "/portfolio/items?scope=managed&status=submitted,under_review&page_size=6",
    empty: "No reviews pending",
    unavailable: "Portfolio review data is not available yet.",
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
];
const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the music teacher. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  user = await organisationWithUser(request, { academyType: "music-academy", role: "music-teacher" });
  await standardPlan(request, user.organisation.id);
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a music teacher signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("music teacher widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the music-teacher layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the music-teacher layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

// Backend-dependent: these need their module's API to create the data through, so nothing here is faked.
test.describe("with facilities data", () => {
  test.fixme("facility-booking.bookings-today lists a booking of a practice room the music teacher approves", async () => {
    // facilities/facility-booking is enabled and exports the widget. The music teacher (facility-booking-approver
    // grants) sees today's bookings only on the resources they approve, so set up with organisationAdmin + addUser:
    // a facility-staff user adds a resource type and a resource with approver_user_ids: [<music teacher id>]
    // (POST /facility-booking/resource-types, /resources), then a booking later today as in facility-staff.spec.ts
    // (the next free half hour in FACILITY_BOOKING_TIMEZONE, skipped near midnight). Confirm which role may create a
    // resource with approvers before writing this.
    // Expect: "No bookings today" is gone; the row shows the time window and "<resource> · <title>", and the
    // "Booking counts" line says "1 today".
  });
});
