import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Project Guide dashboard (layout platform/identity/config/dashboards/project-guide.yaml, which extends the Faculty
 * layout; the role exists in the engineering-college profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a project guide signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Faculty ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml and exports the widget: the panel renders by its registered title and
 *   shows its empty state, or says its data is not available while the backend is missing (the project guide holds
 *   the faculty role's permissions through `extends`);
 * - widgets that are not on the dashboard yet are skipped, naming the module and the sprint batch that builds it
 *   (projects and field-training #339, skill-progress #329, and the inherited timetable-attendance, lms and
 *   examinations ones). skill-progress.assessments-due is built in an open pull request and already carries its
 *   texts, so the journey starts checking it the day the module is enabled.
 *
 * There is no data journey yet: every widget of this layout that holds data (projects, skill-progress,
 * field-training) waits for its module, and the inherited course roster has nothing to show until a term is active.
 * The data journeys are added with the modules.
 *
 * finance-operations and campus-life are not in the Trial plan (platform/billing/config/plans.yaml), so the super
 * admin moves the organisation to Standard first. Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Project Guide";

const WIDGETS: LayoutWidget[] = [
  // Inherited from the Faculty layout (extends: faculty).
  {
    id: "timetable-attendance.today-classes",
    module: "academics/timetable-attendance",
    batch: "#325",
    title: "Teaching today",
    probe: "/timetable-attendance/me/teaching-schedule",
    empty: "No classes to teach today",
    unavailable: "Timetable and attendance are not available yet.",
  },
  {
    id: "timetable-attendance.attendance-to-mark",
    module: "academics/timetable-attendance",
    batch: "#325",
    title: "Attendance to mark",
    probe: "/timetable-attendance/me/attendance-to-mark",
    empty: "No attendance waiting to be marked",
    unavailable: "Timetable and attendance are not available yet.",
  },
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
  // The project guide's own widgets.
  {
    id: "projects.to-review",
    module: "practice/projects",
    batch: "#339",
    title: "To review",
    probe: "/projects/me/reviews?limit=1",
    empty: "Nothing waiting for your review",
    unavailable: "Projects data is not available yet.",
  },
  {
    id: "projects.active",
    module: "practice/projects",
    batch: "#339",
    title: "Active projects",
    probe: "/projects/projects?status=active&limit=1",
    empty: "No active projects",
    unavailable: "Projects data is not available yet.",
  },
  {
    // Texts of the widget in PR #456 (feat/skill-progress/due-and-cohort-widgets), not merged yet.
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
    id: "field-training.trainees-to-assess",
    module: "practice/field-training",
    batch: "#339",
    title: "Trainees to assess",
    probe: "/field-training/me/trainees?limit=1",
    empty: "Nothing to assess right now",
    unavailable: "Field training data is not available yet.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the project guide. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "engineering-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "project-guide");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a project guide signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("project-guide widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the project-guide layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the project-guide layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
