import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Research Supervisor dashboard (layout platform/identity/config/dashboards/research-supervisor.yaml, which extends
 * the Faculty layout; the role exists only in the research-university profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a research-supervisor user signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Faculty ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml: the panel renders by its registered title and shows its empty
 *   state, says its data is not available while the backend is missing, or says the role has no access
 *   (academic-management grants the faculty role, not research-supervisor);
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it.
 * The supervisor's own widgets (projects, selection-process, portfolio) have no backend yet, so their data
 * journeys are fixme below.
 *
 * The super admin moves the organisation to Standard first, as the other research journeys do, so every
 * module of the profile is entitled. Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Research Supervisor";

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
    // The widget's client treats 404 (no active term) as nothing this term, not as a failure.
    unavailable: "No courses this term",
    forbidden: "Could not load your courses",
  },
  // The supervisor's own widgets.
  { id: "projects.to-review", module: "practice/projects", batch: "#339" },
  { id: "projects.active", module: "practice/projects", batch: "#339" },
  {
    id: "selection-process.to-judge",
    module: "practice/selection-process",
    batch: "#322",
    title: "To Judge",
    probe: "/selection-process/processes?status=open&page_size=5",
    empty: "No candidates awaiting review",
    unavailable: "Selection judging data is not available yet.",
  },
  { id: "portfolio.reviews-pending", module: "practice/portfolio", batch: "#322" },
];
const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the research-supervisor user. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "research-university" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "research-supervisor");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a research supervisor signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("research supervisor widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the research-supervisor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, says its data is not available yet, or says the role has no access", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the research-supervisor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
test.fixme("projects.to-review lists the research projects waiting for the supervisor's review", async () => {
  // practice/projects (sprint batch #339); vocabulary: "Research project". Submit a scholar's milestone for
  // review; expect it with the scholar's name and how long it has waited.
});

test.fixme("projects.active counts the supervisor's active research projects", async () => {
  // practice/projects (sprint batch #339).
});

test.fixme("selection-process.to-judge lists the supervisor allocation / viva rounds the supervisor judges", async () => {
  // practice/selection-process (sprint batch #322); vocabulary: "Supervisor allocation / viva".
});

test.fixme("portfolio.reviews-pending lists the publications waiting for the supervisor's review", async () => {
  // practice/portfolio (sprint batch #322); vocabulary: "Publication".
});

test.fixme("academic-management.course-roster lists the supervisor's course offerings", async () => {
  // academic-management grants roster:read to the faculty role (contracts/permissions.yaml), not to
  // research-supervisor; write this once the contract grants it, or the profile maps the role onto faculty.
});
