import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { OPENING, REQUIRED_HOURS, seedPlacement, SITE } from "./field-training-data";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Clinical Supervisor dashboard (layout platform/identity/config/dashboards/clinical-supervisor.yaml, which extends the Faculty layout; the role exists in the medical-college
 * profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a clinical supervisor signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Faculty ones included, whose module is in apps/frontend/config/modules.enabled.yaml and exports the
 *   widget: the panel renders by its registered title and shows its empty state, or says its data is not available
 *   while the backend is missing;
 * - widgets that are not on the dashboard yet are skipped, naming the module and the sprint batch that builds it
 *   (field-training #339, and the inherited timetable-attendance, lms and examinations ones). Entries whose module is already merged carry that widget's texts, so the journey starts checking them the
 *   day the module is enabled;
 * - data journey: a medical student the hospital coordinator places and starts, whose log entry waits for the supervisor,
 *   shows in `field-training.trainees-to-assess` ("1 entry to verify"), and the opening with a seat left in
 *   `field-training.placements-open`; it skips until field-training is enabled. No data journey for
 *   facility-booking.bookings-today, which lists bookings of the resources the viewer approves and needs the supervisor
 *   set as a resource's approver (facility-staff.spec.ts covers the widget with a booking), or for skill-progress.
 *
 * facilities and practice are not in the Trial plan (platform/billing/config/plans.yaml), so the super admin moves
 * the organisation to Standard first. Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Clinical Supervisor";

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
  {
    // Inherited from the Faculty layout (#421): the instructor's own upcoming bookings (MyBookingsWidget.tsx).
    id: "facility-booking.my-bookings",
    module: "facilities/facility-booking",
    batch: "#421",
    title: "My bookings",
    probe: "/facility-booking/bookings?scope=mine&from=now&status=pending,confirmed,checked_in&page_size=6",
    empty: "No upcoming bookings",
    unavailable: "Booking data is not available yet.",
  },
  // The clinical supervisor's own widgets.
  {
    id: "field-training.trainees-to-assess",
    module: "practice/field-training",
    batch: "#339",
    title: "Trainees to assess",
    probe: "/field-training/me/trainees?limit=1",
    empty: "Nothing to assess right now",
    unavailable: "Field training data is not available yet.",
  },
  {
    id: "skill-progress.assessments-due",
    module: "practice/skill-progress",
    batch: "#329",
    title: "Assessments to verify",
    probe: "/skill-progress/assessments?status=submitted&limit=1",
    empty: "Nothing to verify",
    unavailable: "Skill progress data is not available yet.",
    forbidden: "You do not have access to this.",
  },
  {
    id: "field-training.placements-open",
    module: "practice/field-training",
    batch: "#339",
    title: "Open placements",
    probe: "/field-training/openings?status=open&has_seats=true&limit=1",
    empty: "No open placements with seats",
    unavailable: "Field training data is not available yet.",
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
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let admin: DashboardUser;
let user: DashboardUser;
/** The hospital coordinator who sets up the placement, and the medical student on it. */
let coordinator: DashboardUser;
let trainee: DashboardUser;
/** Per shipped widget id: what its GET answered the clinical supervisor. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "medical-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "clinical-supervisor");
  coordinator = await addUser(request, admin, "hospital-coordinator");
  trainee = await addUser(request, admin, "medical-student");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a clinical supervisor signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("clinical-supervisor widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the clinical-supervisor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the clinical-supervisor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

test.describe("with field-training data", () => {
  test("field-training.trainees-to-assess and placements-open show a trainee with an entry to verify and the opening's free seat", async ({ page, request }) => {
    for (const id of ["field-training.trainees-to-assess", "field-training.placements-open"]) {
      test.skip(!shipped(byId(id)), waitingFor(byId(id)));
      test.skip(!ready(id), `the field-training API answered ${status[id]} to the clinical-supervisor role`);
    }
    // The coordinator places the medical student on an opening with two seats and starts it; the student logs today's
    // hours and the entry waits for the supervisor named on the site and the opening (the clinical supervisor).
    await seedPlacement(request, { coordinator, supervisor: user, trainee }, { start: true, log: true });
    await signIn(page, user);

    const toAssess = widget(page, "Trainees to assess");
    await expect(toAssess.getByText("Nothing to assess right now")).toHaveCount(0);
    // No identity lookup gives the module the trainee's name yet, so the row is titled "Trainee".
    const row = toAssess.getByRole("list", { name: "Trainees to assess" }).getByRole("listitem").filter({ hasText: OPENING });
    await expect(row).toContainText(SITE);
    await expect(row).toContainText("1 entry to verify");

    const open = widget(page, "Open placements");
    await expect(open.getByText("No open placements with seats")).toHaveCount(0);
    const opening = open.getByRole("list", { name: "Open placements" }).getByRole("listitem").filter({ hasText: OPENING });
    await expect(opening).toContainText(SITE);
    await expect(opening).toContainText("1 seat left"); // two seats, one taken by the placement
  });
});
