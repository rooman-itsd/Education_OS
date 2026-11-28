import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { OPENING, SITE, seedPlacement } from "./field-training-data";
import { MILESTONE, TRIAL, seedProject } from "./projects-data";
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
 * - with data: field-training.trainees-to-assess and projects.to-review show the trainee the practicum coordinator
 *   places with the mentor teacher and the milestone the trainee submits to them, and none of it reaches another mentor
 *   teacher; the inherited Faculty widgets need a term, courses and registrations (faculty.spec.ts seeds them).
 *
 * The super admin moves the organisation to Standard first, so every module of the profile is entitled (campus-life and
 * facilities are not in the Trial plan, platform/billing/config/plans.yaml).
 * Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Mentor Teacher";

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
    // A new organisation has no active term: GET /me/offerings answers 404 active_term_not_found, which the widget
    // shows as nothing this term.
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
let otherMentor: DashboardUser;
let coordinator: DashboardUser;
let projectsLead: DashboardUser;
let trainee: DashboardUser;
/** Per shipped widget id: what its GET answered the mentor teacher. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "teacher-education-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "mentor-teacher");
  otherMentor = await addUser(request, admin, "mentor-teacher", "mentor-two");
  coordinator = await addUser(request, admin, "practicum-coordinator");
  projectsLead = await addUser(request, admin, "projects-coordinator");
  trainee = await addUser(request, admin, "teacher-trainee");
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

test.describe("with field-training and projects data", () => {
  test("trainees-to-assess and to-review show the trainee placed with this mentor and the milestone they submit", async ({ page, request }) => {
    for (const id of ["field-training.trainees-to-assess", "projects.to-review"]) {
      const w = WIDGETS.find((x) => x.id === id)!;
      test.skip(!shipped(w), waitingFor(w));
      test.skip(status[id] !== 200, `the ${w.module} API answered ${status[id]} to the mentor-teacher role`);
    }
    // The practicum coordinator places the trainee at a school (site and opening name the mentor as supervisor), the
    // trainee logs today's hours and the entry waits for the mentor. The projects coordinator creates the trainee's
    // project with the mentor as guide; the guide adds a milestone and the trainee submits it.
    await seedPlacement(request, { coordinator, supervisor: user, trainee }, { start: true, log: true });
    await seedProject(request, { coordinator: projectsLead, guide: user, lead: trainee }, { milestone: true, submit: true });
    await signIn(page, user);

    const toAssess = widget(page, "Trainees to assess");
    await expect(toAssess.getByText("Nothing to assess right now")).toHaveCount(0);
    // No identity lookup gives the module the trainee's name yet, so the row is titled "Trainee".
    const row = toAssess.getByRole("list", { name: "Trainees to assess" }).getByRole("listitem").filter({ hasText: OPENING });
    await expect(row).toContainText(SITE);
    await expect(row).toContainText("1 entry to verify");

    const review = widget(page, "To review");
    await expect(review.getByText("Nothing waiting for your review")).toHaveCount(0);
    const item = review.getByRole("list", { name: "Work to review" }).getByRole("listitem").filter({ hasText: MILESTONE });
    await expect(item).toContainText(`${TRIAL} · version 1`);
  });

  test("another mentor teacher sees none of it", async ({ page }) => {
    for (const id of ["field-training.trainees-to-assess", "projects.to-review"]) {
      const w = WIDGETS.find((x) => x.id === id)!;
      test.skip(!shipped(w), waitingFor(w));
    }
    await signIn(page, otherMentor);
    await expect(widget(page, "Trainees to assess").getByText("Nothing to assess right now", { exact: true })).toBeVisible();
    await expect(widget(page, "To review").getByText("Nothing waiting for your review", { exact: true })).toBeVisible();
    await expect(page.getByText(OPENING)).toHaveCount(0);
    await expect(page.getByText(MILESTONE)).toHaveCount(0);
  });

  test("the trainee is refused what only a supervisor reads", async ({ request }) => {
    // The mentor review queue and assessment list belong to supervisors: the trainee being assessed may not read them.
    for (const [who, path] of [
      [trainee, "/api/v1/projects/me/reviews?limit=1"],
      [trainee, "/api/v1/field-training/me/trainees?limit=1"],
    ] as const) {
      const response = await request.get(path, { headers: { Authorization: `Bearer ${who.token}` } });
      expect(response.status(), path).toBe(403);
    }
  });
});
