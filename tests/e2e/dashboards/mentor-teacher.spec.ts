import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Mentor Teacher dashboard (layout platform/identity/config/dashboards/mentor-teacher.yaml, which extends
 * the Faculty layout; the role exists in the
 * teacher-education-college profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a mentor teacher signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Faculty ones included, whose module is in apps/frontend/config/modules.enabled.yaml and
 *   exports the widget: the panel renders by its registered title and shows its empty state, or says its data is not
 *   available while the backend is missing;
 * - widgets that are not on the dashboard yet are skipped, naming the module and the sprint batch that builds it
 *   (field-training and projects #339, and the inherited timetable-attendance, examinations and lms ones). Entries whose module is built already carry that widget's texts, so the journey starts checking them
 *   the day the module is enabled;
 * - no data journeys yet: every widget that holds data waits for its module (field-training, projects), and the
 *   shared ones need a term or a framework first. The data journeys are added with the modules.
 *
 * The super admin moves the organisation to Standard first, so every module of the profile is entitled (campus-life and
 * facilities are not in the Trial plan, platform/billing/config/plans.yaml).
 * Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Mentor Teacher";

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
    // A new organisation has no active term: GET /me/offerings answers 404 active_term_not_found, which the widget
    // shows as nothing this term.
    emptyCode: "active_term_not_found",
    unavailable: "No courses this term",
    forbidden: "Could not load your courses",
  },
  // The mentor teacher's own widgets.
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
    // Texts of ReviewsPendingWidget.tsx (practice/portfolio, merged in #413).
    id: "portfolio.reviews-pending",
    module: "practice/portfolio",
    batch: "#322",
    title: "Reviews Pending",
    probe: "/portfolio/items?scope=managed&status=submitted,under_review&page_size=6",
    empty: "No reviews pending",
    unavailable: "Portfolio review data is not available yet.",
  },
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
    id: "skill-progress.assessments-due",
    module: "practice/skill-progress",
    batch: "#329",
    title: "Assessments to verify",
    probe: "/skill-progress/assessments?status=submitted&limit=1",
    empty: "Nothing to verify",
    unavailable: "Skill progress data is not available yet.",
    forbidden: "You do not have access to this.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the mentor teacher. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "teacher-education-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "mentor-teacher");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a mentor teacher signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("mentor-teacher widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the mentor-teacher layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the mentor-teacher layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
