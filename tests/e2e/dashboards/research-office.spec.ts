import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, dayFromNow, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Research Office dashboard (layout platform/identity/config/dashboards/research-office.yaml; the role exists only
 * in the research-university profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a research-office user signs in and lands on their dashboard;
 * - for every widget whose module is in apps/frontend/config/modules.enabled.yaml: the panel renders by its
 *   registered title and shows its empty state, or says its data is not available while the backend is missing;
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it;
 * - the data journey the budget-grants backend allows today: a grant the research office records shows in
 *   budget-grants.budget-vs-spend, which that role sees with scope=grants.
 *
 * finance-operations is not in the Trial plan, so the super admin moves the organisation to Standard first.
 * Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Research Office";

const WIDGETS: LayoutWidget[] = [
  {
    id: "selection-process.open-calls",
    module: "practice/selection-process",
    batch: "#322",
    title: "Open Calls",
    probe: "/selection-process/processes?status=open&page_size=6",
    empty: "No open calls right now",
    unavailable: "Open calls are not available yet.",
  },
  { id: "projects.active", module: "practice/projects", batch: "#339" },
  {
    id: "budget-grants.budget-vs-spend",
    module: "finance-operations/budget-grants",
    batch: "#128",
    title: "Budget vs spend",
    probe: "/budget-grants/reports/budget-vs-spend?scope=grants",
    empty: "No grants to show",
    unavailable: "Budget data is not available yet.",
  },
  { id: "productions.calendar", module: "practice/productions", batch: "#318" },
  { id: "regulatory-reports.due", module: "governance/regulatory-reports", batch: "#343" },
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let user: DashboardUser;
/** Finance staff create budget heads (budget-grants:budget:manage); the research office records the grant itself. */
let finance: DashboardUser;
/** Per shipped widget id: what its GET answered the research-office user. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "research-university" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "research-office");
  finance = await addUser(request, admin, "finance-staff");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a research office user signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("research office widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the research-office layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the research-office layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

test.describe("with budget-grants data", () => {
  test("budget-grants.budget-vs-spend shows the grant the research office records", async ({ page, request }) => {
    const w = byId("budget-grants.budget-vs-spend");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(status[w.id] !== 200, `the budget-grants API answered ${status[w.id]} to the research-office role`);
    const head = await created<{ id: string }>(request, finance, "/budget-grants/budget-heads", { code: "EQUIP", name: "Equipment", kind: "non_recurring" });
    // The research office holds budget-grants:grant:manage, so it records the sanctioned grant itself.
    await created(request, user, "/budget-grants/grants", {
      code: "SERB-2026-014",
      title: "Catalysts for green hydrogen",
      funder: "SERB",
      sanctioned_amount: "500000.00",
      start_date: dayFromNow(0),
      end_date: dayFromNow(730),
      investigators: [{ user_id: finance.id, role: "principal" }],
      lines: [{ budget_head_id: head.id, sanctioned: "500000.00" }],
    });
    await signIn(page, user);
    const panel = widget(page, "Budget vs spend");
    await expect(panel.getByText("No grants to show")).toHaveCount(0);
    await expect(panel.getByText("Allocated", { exact: true })).toBeVisible();
    await expect(panel.getByText("Available", { exact: true })).toBeVisible();
    await expect(panel.getByText("0% used", { exact: true }).first()).toBeVisible();
    const heads = panel.getByRole("region", { name: "Budget heads" });
    await expect(heads).toContainText("Equipment");
    await expect(heads).toContainText("₹0.00 of ₹5,00,000.00");
    const grants = panel.getByRole("region", { name: "Grants" });
    await expect(grants).toContainText("Active grants");
    await expect(grants).toContainText("₹5,00,000.00");
    await expect(panel.getByText(/^Financial year /)).toBeVisible();
  });
});

// Backend-dependent: these need their module's API to create the data through, so nothing here is faked.
test.fixme("selection-process.open-calls lists the open supervisor allocation / viva calls", async () => {
  // practice/selection-process (sprint batch #322); vocabulary: "Supervisor allocation / viva". Open a call
  // closing next month; expect it with its closing date and the applications so far.
});

test.fixme("projects.active counts the organisation's active research projects", async () => {
  // practice/projects (sprint batch #339); vocabulary: "Research project".
});

test.fixme("productions.calendar shows next month's conferences", async () => {
  // practice/productions (sprint batch #318); vocabulary: a production is a "Conference".
});

test.fixme("regulatory-reports.due lists the regulatory reports due soon", async () => {
  // governance/regulatory-reports (sprint batch #343). Register a report due in two weeks; expect it with its
  // due date and the regulator.
});
