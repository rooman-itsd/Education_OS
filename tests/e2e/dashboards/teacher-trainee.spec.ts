import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { OPENING, REQUIRED_HOURS, SITE, seedPlacement } from "./field-training-data";
import { created, dayFromNow, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Teacher Trainee dashboard (layout platform/identity/config/dashboards/teacher-trainee.yaml, which extends
 * the Student layout; the role exists in the
 * teacher-education-college profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a teacher trainee signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Student ones included, whose module is in apps/frontend/config/modules.enabled.yaml and
 *   exports the widget: the panel renders by its registered title and shows its empty state, or says its data is not
 *   available while the backend is missing;
 * - widgets that are not on the dashboard yet are skipped, naming the module and the sprint batch that builds it
 *   (field-training and projects #339, skill-progress #329, and the inherited timetable-attendance, examinations and lms ones, and transport and library until they are enabled). Entries whose module is built already carry that widget's texts, so the journey starts checking them
 *   the day the module is enabled;
 * - with data: my-placement, hours-logged and my-projects show the trainee's own placement, verified hours and project,
 *   and a second trainee sees none of them; the inherited Student widgets need a term, courses and registrations first
 *   (skill-progress and portfolio have no data journey yet).
 *
 * The super admin moves the organisation to Standard first, so every module of the profile is entitled (campus-life and
 * facilities are not in the Trial plan, platform/billing/config/plans.yaml).
 * Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Teacher Trainee";

const WIDGETS: LayoutWidget[] = [
  // Inherited from the Student layout (extends: student).
  {
    id: "timetable-attendance.today",
    module: "academics/timetable-attendance",
    batch: "#325",
    title: "Today's classes",
    probe: "/timetable-attendance/me/schedule",
    empty: "No classes today",
    unavailable: "Timetable and attendance are not available yet.",
  },
  {
    id: "timetable-attendance.attendance-summary",
    module: "academics/timetable-attendance",
    batch: "#325",
    title: "My attendance",
    probe: "/timetable-attendance/me/attendance-summary",
    empty: "No attendance recorded yet",
    // No active term: timetable-attendance answers 404 active_term_not_found, which the widget shows as nothing recorded yet.
    emptyCode: "active_term_not_found",
    unavailable: "Timetable and attendance are not available yet.",
  },
  {
    // Texts of UpcomingAssessments.tsx and errorMessage in examinations/frontend/src/widgets/useWidgetData.tsx.
    id: "examinations.upcoming-assessments",
    module: "academics/examinations",
    batch: "#325",
    title: "Upcoming assessments",
    probe: "/examinations/me/exam-schedule",
    empty: "No upcoming exams.",
    unavailable: "Examinations data is not available yet.",
    forbidden: "You do not have access to this.",
  },
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
  // The teacher trainee's own widgets.
  {
    id: "field-training.my-placement",
    module: "practice/field-training",
    batch: "#339",
    title: "My placement",
    probe: "/field-training/me/placements",
    empty: "No placement yet",
    unavailable: "Field training data is not available yet.",
  },
  {
    id: "projects.my-projects",
    module: "practice/projects",
    batch: "#339",
    title: "My projects",
    probe: "/projects/me/projects",
    empty: "You are not on a project yet",
    unavailable: "Projects data is not available yet.",
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
    id: "field-training.hours-logged",
    module: "practice/field-training",
    batch: "#339",
    title: "Hours logged",
    probe: "/field-training/me/hours",
    empty: "No hours to show yet",
    unavailable: "Field training data is not available yet.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
let otherTrainee: DashboardUser;
let coordinator: DashboardUser;
let mentor: DashboardUser;
/** Per shipped widget id: what its GET answered the teacher trainee. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "teacher-education-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "teacher-trainee");
  otherTrainee = await addUser(request, admin, "teacher-trainee", "trainee-two");
  coordinator = await addUser(request, admin, "practicum-coordinator");
  mentor = await addUser(request, admin, "mentor-teacher");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a teacher trainee signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("teacher-trainee widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the teacher-trainee layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the teacher-trainee layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
  const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;
  const skipUnlessReady = (test_: typeof test, ids: string[]) => {
    for (const id of ids) {
      test_.skip(!shipped(byId(id)), waitingFor(byId(id)));
      test_.skip(status[id] !== 200, `the ${byId(id).module} API answered ${status[id]} to the teacher-trainee role`);
    }
  };

  test("my-placement, hours-logged and my-projects show the trainee's own placement, verified hours and project", async ({ page, request }) => {
    skipUnlessReady(test, ["field-training.my-placement", "field-training.hours-logged", "projects.my-projects"]);
    // The practicum coordinator places the trainee at a school and starts the placement; the trainee logs today's
    // hours and the mentor named on the opening verifies them. Only verified hours count. The trainee proposes a project.
    await seedPlacement(request, { coordinator, supervisor: mentor, trainee: user }, { start: true, log: true, verify: true });
    await created(request, user, "/projects/projects", {
      title: "Classroom questioning study",
      kind: "Research",
      starts_on: dayFromNow(0),
      ends_on: dayFromNow(90),
    });
    await signIn(page, user);

    const placement = widget(page, "My placement");
    await expect(placement.getByText("No placement yet")).toHaveCount(0);
    const row = placement.getByRole("list", { name: "Your placements" }).getByRole("listitem").filter({ hasText: OPENING });
    await expect(row).toContainText(SITE);
    await expect(row).toContainText(`4 of ${REQUIRED_HOURS} h verified`);
    await expect(row).toContainText("Active");

    const hours = widget(page, "Hours logged");
    await expect(hours.getByText("No hours to show yet")).toHaveCount(0);
    await expect(hours).toContainText(`4 of ${REQUIRED_HOURS} hours verified`);
    await expect(hours.getByText("Awaiting verification: 0 h")).toBeVisible();

    const projects = widget(page, "My projects");
    await expect(projects.getByText("You are not on a project yet")).toHaveCount(0);
    const project = projects.getByRole("list", { name: "My projects" }).getByRole("listitem").filter({ hasText: "Classroom questioning study" });
    await expect(project).toContainText("Lead · No milestones yet");
    await expect(project).toContainText("Proposed");
  });

  test("another trainee sees none of it", async ({ page, request }) => {
    skipUnlessReady(test, ["field-training.my-placement", "field-training.hours-logged", "projects.my-projects"]);
    await signIn(page, otherTrainee);
    await expect(widget(page, "My placement").getByText("No placement yet", { exact: true })).toBeVisible();
    await expect(widget(page, "Hours logged").getByText("No hours to show yet", { exact: true })).toBeVisible();
    await expect(widget(page, "My projects").getByText("You are not on a project yet", { exact: true })).toBeVisible();
    await expect(page.getByText(OPENING)).toHaveCount(0);
    await expect(page.getByText("Classroom questioning study")).toHaveCount(0);
    // The same through the API the widgets call: the first trainee's records, and nothing for the second.
    const mine = async (who: DashboardUser, path: string) => {
      const response = await request.get(`/api/v1${path}`, { headers: { Authorization: `Bearer ${who.token}` } });
      expect(response.status(), path).toBe(200);
      return (await response.json()) as unknown[]; // both answer a plain list
    };
    expect(await mine(user, "/field-training/me/placements")).toHaveLength(1);
    expect(await mine(otherTrainee, "/field-training/me/placements")).toEqual([]);
    expect(await mine(user, "/projects/me/projects")).toHaveLength(1);
    expect(await mine(otherTrainee, "/projects/me/projects")).toEqual([]);
  });
});
