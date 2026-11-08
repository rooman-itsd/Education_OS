import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
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
 * - there is no data journey: all four widgets belong to modules that have not shipped, and those modules' own
 *   journeys cover their data. The empty states are what this checks.
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

let user: DashboardUser;

/** Per shipped widget id: what its GET answered the research lead. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "agriculture-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "research-lead");
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
