import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Design Mentor dashboard (layout platform/identity/config/dashboards/design-mentor.yaml, which extends the Faculty
 * layout; the role exists in the design-fashion-institute profile). Part of #324.
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a design mentor signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Faculty ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml and exports the widget: the panel renders by its registered title and
 *   shows its empty state, or says its data is not available while the backend is missing (the design mentor holds the
 *   faculty role's permissions through `extends`);
 * - widgets that are not on the dashboard yet are skipped, naming the module and the sprint batch that builds it
 *   (projects and field-training #339, and the inherited timetable-attendance, lms and examinations ones).
 *
 * There is no data journey yet: every widget of this layout that holds data (portfolio reviews, selection-process,
 * projects, field-training) either waits for its module or needs a submission by a learner, and the inherited course
 * roster has nothing to show until a term is active. The data journeys are added with the modules.
 *
 * finance-operations and campus-life are not in the Trial plan (platform/billing/config/plans.yaml), so the super
 * admin moves the organisation to Standard first. Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Design Mentor";

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
  // The design mentor's own widgets.
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
    // Texts of ToJudgeWidget.tsx (practice/selection-process, merged in #414). The widget first lists the open
    // processes; a failure there is what its panel shows.
    id: "selection-process.to-judge",
    module: "practice/selection-process",
    batch: "#322",
    title: "To Judge",
    probe: "/selection-process/processes?status=open&page_size=5",
    empty: "No candidates awaiting review",
    unavailable: "Judging tasks are not available yet.",
  },
  { id: "field-training.trainees-to-assess", module: "practice/field-training", batch: "#339" },
];
const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the design mentor. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "design-fashion-institute" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "design-mentor");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a design mentor signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("design-mentor widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the design-mentor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the design-mentor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
