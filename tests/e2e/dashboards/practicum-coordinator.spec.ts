import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { OPENING, REQUIRED_HOURS, SITE, seedPlacement } from "./field-training-data";
import { created, dayFromNow, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Practicum Coordinator dashboard (layout platform/identity/config/dashboards/practicum-coordinator.yaml; the role exists in the
 * teacher-education-college profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a practicum coordinator signs in and lands on their dashboard;
 * - for every widget of the layout whose module is in apps/frontend/config/modules.enabled.yaml and
 *   exports the widget: the panel renders by its registered title and shows its empty state, or says its data is not
 *   available while the backend is missing;
 * - a widget that is not on the dashboard is skipped, naming the module and the sprint batch that builds it. All
 *   three modules of the layout (field-training #339, skill-progress #329 and placement-career #337) are
 *   enabled in apps/frontend/config/modules.enabled.yaml, so every entry below is checked; the skip only applies if a
 *   module is taken out of the list or stops exporting a widget;
 * - with data: placements-open, active-placements and openings-summary show a started placement with its free seat and a
 *   published opening, a coordinator of another organisation sees none of it, and a trainee is refused the reports that
 *   are the coordinator's. skill-progress.cohort-overview has no data journey yet.
 *
 * The super admin moves the organisation to Standard first, so every module of the profile is entitled (campus-life and
 * facilities are not in the Trial plan, platform/billing/config/plans.yaml).
 * Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Practicum Coordinator";

const WIDGETS: LayoutWidget[] = [
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
    id: "field-training.active-placements",
    module: "practice/field-training",
    batch: "#339",
    title: "Active placements",
    probe: "/field-training/placements?status=active&limit=1",
    empty: "No placements under way",
    unavailable: "Field training data is not available yet.",
  },
  {
    // Texts of CohortOverviewWidget.tsx (practice/skill-progress): a summary of every assessed learner per framework.
    id: "skill-progress.cohort-overview",
    module: "practice/skill-progress",
    batch: "#329",
    title: "Skill levels",
    probe: "/skill-progress/reports/framework-summary",
    empty: "No assessments yet",
    unavailable: "Skill progress data is not available yet.",
    forbidden: "You do not have access to this.",
  },
  {
    // Texts of OpeningsSummary.tsx (campus-life/placement-career, enabled in the backend and on the dashboard since
    // #542). The staff view of openings: #424 split it from the learner widget placement-career.openings, which is
    // not on this layout.
    id: "placement-career.openings-summary",
    module: "campus-life/placement-career",
    batch: "#337",
    title: "Placement openings",
    probe: "/placement-career/reports/openings-summary?limit=1",
    empty: "No openings yet",
    unavailable: "Placement data is not available yet.",
    forbidden: "You do not have access to this.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
let mentor: DashboardUser;
let trainee: DashboardUser;
let outsider: DashboardUser;
/** Per shipped widget id: what its GET answered the practicum coordinator. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "teacher-education-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "practicum-coordinator");
  mentor = await addUser(request, admin, "mentor-teacher");
  trainee = await addUser(request, admin, "teacher-trainee");
  // A practicum coordinator of another organisation: what the first one creates is not theirs to see.
  const elsewhere = await organisationAdmin(request, { academyType: "teacher-education-college" });
  await standardPlan(request, elsewhere.organisation.id);
  outsider = await addUser(request, elsewhere, "practicum-coordinator");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a practicum coordinator signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("practicum-coordinator widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the practicum-coordinator layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the practicum-coordinator layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

test.describe("with field-training and placement-career data", () => {
  const ids = ["field-training.placements-open", "field-training.active-placements", "placement-career.openings-summary"];
  const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;
  const skipUnlessReady = (test_: typeof test) => {
    for (const id of ids) {
      test_.skip(!shipped(byId(id)), waitingFor(byId(id)));
      test_.skip(status[id] !== 200, `the ${byId(id).module} API answered ${status[id]} to the practicum-coordinator role`);
    }
  };

  test("the placement they start, its open seat and a published opening show with their counts", async ({ page, request }) => {
    skipUnlessReady(test);
    // The layout grants field-training-coordinator (site, opening with two seats and 40 required hours, assignment,
    // start) and placement-career-officer (company and opening). The trainee logs today's hours and the mentor verifies them.
    await seedPlacement(request, { coordinator: user, supervisor: mentor, trainee }, { start: true, log: true, verify: true });
    const company = await created<{ id: string }>(request, user, "/placement-career/companies", { name: "Greenfield Public School", industry: "Education" });
    const opening = await created<{ id: string }>(request, user, "/placement-career/openings", {
      company_id: company.id,
      title: "Assistant teacher",
      location: "Pune",
      ctc_per_annum: "360000",
      positions: 2,
      applications_close_on: dayFromNow(7),
    });
    await created(request, user, `/placement-career/openings/${opening.id}/publish`, {});
    await signIn(page, user);

    const active = widget(page, "Active placements");
    await expect(active.getByText("No placements under way")).toHaveCount(0);
    const row = active.getByRole("list", { name: "Active placements" }).getByRole("listitem").filter({ hasText: OPENING });
    await expect(row).toContainText(SITE);
    await expect(row).toContainText(`4 of ${REQUIRED_HOURS} h`);

    const open = widget(page, "Open placements");
    await expect(open.getByText("No open placements with seats")).toHaveCount(0);
    const seat = open.getByRole("list", { name: "Open placements" }).getByRole("listitem").filter({ hasText: OPENING });
    await expect(seat).toContainText(SITE);
    await expect(seat).toContainText("1 seat left"); // two seats, one taken

    const summary = widget(page, "Placement openings");
    await expect(summary.getByText("No openings yet")).toHaveCount(0);
    const figures = summary.locator("dl > div");
    await expect(figures.filter({ hasText: "Open openings" })).toHaveText("Open openings1");
    await expect(figures.filter({ hasText: "Applications" })).toHaveText("Applications0");
    await expect(figures.filter({ hasText: "Students placed" })).toHaveText("Students placed0");
    const closing = summary.getByRole("list", { name: "Openings closing soonest" }).getByRole("listitem").filter({ hasText: "Assistant teacher" });
    await expect(closing).toContainText("Greenfield Public School");
    await expect(closing).toContainText("0 applications");
  });

  test("a practicum coordinator of another organisation sees none of it", async ({ page }) => {
    skipUnlessReady(test);
    await signIn(page, outsider);
    await expect(widget(page, "Active placements").getByText("No placements under way", { exact: true })).toBeVisible();
    await expect(widget(page, "Open placements").getByText("No open placements with seats", { exact: true })).toBeVisible();
    await expect(widget(page, "Placement openings").getByText("No openings yet", { exact: true })).toBeVisible();
    await expect(page.getByText(OPENING)).toHaveCount(0);
    await expect(page.getByText("Assistant teacher")).toHaveCount(0);
  });

  test("a trainee cannot read every placement or the openings report", async ({ request }) => {
    skipUnlessReady(test);
    // Open placements stay readable to a trainee (they look for one); the placements under way and the report are the coordinator's.
    for (const w of ["field-training.active-placements", "placement-career.openings-summary"].map(byId)) {
      const response = await request.get(`/api/v1${w.probe}`, { headers: { Authorization: `Bearer ${trainee.token}` } });
      expect(response.status(), w.probe).toBe(403);
    }
  });
});
