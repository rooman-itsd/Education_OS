import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { FARM, seedPlacement } from "./field-training-data";
import { MILESTONE, seedProject, TRIAL } from "./projects-data";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Research Lead dashboard (layout platform/identity/config/dashboards/research-lead.yaml, a role of the
 * agriculture-college profile; the layout extends nothing, so these four widgets are all it shows). Issue #341.
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a research lead signs in and lands on their dashboard;
 * - for every widget of the layout whose module is in apps/frontend/config/modules.enabled.yaml and exports it: the
 *   panel renders by its registered title and shows its empty state, or says its data is not available while the
 *   backend is missing;
 * - widgets of modules not enabled yet, or not exported yet, are skipped, naming the module and the sprint batch that
 *   builds it: projects and field-training (#339, texts of PRs #506 and #504) and productions (#318, PR #454);
 * - data journeys: a research trial the research lead (projects:project:manage) creates, guided by the lead
 *   (projects-guide), shows in `projects.active`; a milestone the trainee submits on it shows in `projects.to-review`;
 *   an opening the field-training coordinator publishes, with one of its two seats taken, shows in
 *   `field-training.placements-open`. Each skips until its module is enabled. `productions.upcoming` has no data
 *   journey here; its data journeys live in the productions-owning journeys.
 *
 * The super admin moves the organisation to Standard first, as the other journeys do (platform/billing/config/plans.yaml).
 * The empty-state tests run before any data is created (serial mode).
 * Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Research Lead";

const WIDGETS: LayoutWidget[] = [
  {
    // Texts of the widget in PR #506 (not merged yet).
    id: "projects.active",
    module: "practice/projects",
    batch: "#339",
    title: "Active projects",
    probe: "/projects/projects?status=active&limit=5",
    empty: "No active projects",
    unavailable: "Projects data is not available yet.",
    forbidden: "You do not have access to this.",
  },
  {
    // Texts of the widget in PR #506 (not merged yet).
    id: "projects.to-review",
    module: "practice/projects",
    batch: "#339",
    title: "To review",
    probe: "/projects/me/reviews?limit=5",
    empty: "Nothing waiting for your review",
    unavailable: "Projects data is not available yet.",
    forbidden: "You do not have access to this.",
  },
  {
    // Texts of UpcomingWidget.tsx in PR #454 (feat/productions/module), not merged yet.
    id: "productions.upcoming",
    module: "practice/productions",
    batch: "#318",
    title: "Upcoming productions",
    probe: "/productions/upcoming",
    empty: "Nothing coming up",
    unavailable: "Production data is not available yet.",
  },
  {
    // Texts of the widget in PR #504 (not merged yet).
    id: "field-training.placements-open",
    module: "practice/field-training",
    batch: "#339",
    title: "Open placements",
    probe: "/field-training/openings?status=open&has_seats=true&limit=5",
    empty: "No open placements with seats",
    unavailable: "Field training data is not available yet.",
    forbidden: "You do not have access to this.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let user: DashboardUser;
/**
 * Who sets up the rest: the field-training coordinator (a module role no agriculture-college profile role holds, so the
 * user has it directly), a farm supervisor named on the site, and the field trainee on the placement and the trial.
 */
let coordinator: DashboardUser;
let supervisor: DashboardUser;
let trainee: DashboardUser;

/** Per shipped widget id: what its GET answered the research lead. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "agriculture-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "research-lead");
  coordinator = await addUser(request, admin, "field-training-coordinator");
  supervisor = await addUser(request, admin, "farm-supervisor");
  trainee = await addUser(request, admin, "field-trainee");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a research lead signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("research-lead widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the research-lead layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the research-lead layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

test.describe("with projects and field-training data", () => {
  test("projects.active and projects.to-review show the trial the research lead guides and the milestone the trainee submits", async ({ page, request }) => {
    for (const id of ["projects.active", "projects.to-review"]) {
      test.skip(!shipped(byId(id)), waitingFor(byId(id)));
      test.skip(!ready(id), `the projects API answered ${status[id]} to the research-lead role`);
    }
    // The research lead creates the trial active (projects-coordinator) with the trainee as lead and themself as guide
    // (projects-guide), adds a milestone, and the trainee submits it.
    await seedProject(request, { coordinator: user, guide: user, lead: trainee }, { milestone: true, submit: true });
    await signIn(page, user);

    const active = widget(page, "Active projects");
    await expect(active.getByText("No active projects")).toHaveCount(0);
    const trial = active.getByRole("list", { name: "Active projects" }).getByRole("listitem").filter({ hasText: TRIAL });
    await expect(trial).toContainText("Research · 1 member");
    await expect(trial.getByLabel("Milestones accepted")).toHaveText("0/1");

    const review = widget(page, "To review");
    await expect(review.getByText("Nothing waiting for your review")).toHaveCount(0);
    const item = review.getByRole("list", { name: "Work to review" }).getByRole("listitem").filter({ hasText: MILESTONE });
    await expect(item).toContainText(`${TRIAL} · version 1`);
    await expect(item).toContainText("Today");
  });

  test("field-training.placements-open lists the opening with a seat left", async ({ page, request }) => {
    const w = byId("field-training.placements-open");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the field-training API answered ${status[w.id]} to the research-lead role`);
    // The coordinator publishes an opening with two seats and assigns the trainee to one; the research lead
    // (field-training-viewer) sees it with one seat left.
    await seedPlacement(request, { coordinator, supervisor, trainee }, { names: FARM });
    await signIn(page, user);
    const panel = widget(page, "Open placements");
    await expect(panel.getByText("No open placements with seats")).toHaveCount(0);
    const row = panel.getByRole("list", { name: "Open placements" }).getByRole("listitem").filter({ hasText: FARM.opening });
    await expect(row).toContainText(FARM.site);
    await expect(row).toContainText("1 seat left"); // two seats, one taken by the placement
  });
});
