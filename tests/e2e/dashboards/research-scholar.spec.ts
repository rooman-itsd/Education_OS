import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, dayFromNow, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Research Scholar dashboard (layout platform/identity/config/dashboards/research-scholar.yaml, which extends the
 * Student layout; the role exists only in the research-university profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a research-scholar user signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Student ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml: the panel renders by its registered title and shows its empty
 *   state, says its data is not available while the backend is missing, or says the role has no access (the
 *   Student widgets' APIs grant the student role, not research-scholar);
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it;
 * - the data journey the budget-grants backend allows today: a grant recorded with the scholar as principal
 *   investigator appears in budget-grants.my-grants.
 *
 * finance-operations and campus-life are not in the Trial plan, so the super admin moves the organisation to
 * Standard first. Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Research Scholar";

const WIDGETS: LayoutWidget[] = [
  // Inherited from the Student layout (extends: student).
  { id: "timetable-attendance.today", module: "academics/timetable-attendance", batch: "#325" },
  { id: "timetable-attendance.attendance-summary", module: "academics/timetable-attendance", batch: "#325" },
  { id: "examinations.upcoming-assessments", module: "academics/examinations", batch: "#325" },
  { id: "lms.course-materials", module: "academics/lms", batch: "#326" },
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
  { id: "transport.notices", module: "campus-life/transport", batch: "#338" },
  { id: "library.loans", module: "campus-life/library", batch: "#338" },
  // The scholar's own widgets.
  { id: "projects.my-projects", module: "practice/projects", batch: "#339" },
  { id: "projects.milestones-due", module: "practice/projects", batch: "#339" },
  {
    id: "portfolio.my-portfolio",
    module: "practice/portfolio",
    batch: "#322",
    title: "My Portfolio",
    probe: "/portfolio/items?scope=mine",
    empty: "No portfolio items yet",
    unavailable: "Portfolio data is not available yet.",
  },
  { id: "productions.upcoming", module: "practice/productions", batch: "#318" },
  { id: "selection-process.my-applications", module: "practice/selection-process", batch: "#322" },
  {
    id: "budget-grants.my-grants",
    module: "finance-operations/budget-grants",
    batch: "#128",
    title: "My grants",
    probe: "/budget-grants/me/grants",
    empty: "No grants yet",
    unavailable: "Budget data is not available yet.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let user: DashboardUser;
/** Finance staff record budget heads and grants (budget-grants:budget:manage and grant:manage). */
let finance: DashboardUser;
/** Per shipped widget id: what its GET answered the research-scholar user. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "research-university" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "research-scholar");
  finance = await addUser(request, admin, "finance-staff");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a research scholar signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("research scholar widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the research-scholar layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, says its data is not available yet, or says the role has no access", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the research-scholar layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
  test("budget-grants.my-grants lists a grant where the scholar is the principal investigator", async ({ page, request }) => {
    const w = byId("budget-grants.my-grants");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(status[w.id] !== 200, `the budget-grants API answered ${status[w.id]} to the research-scholar role`);
    const head = await created<{ id: string }>(request, finance, "/budget-grants/budget-heads", { code: "EQUIP", name: "Equipment", kind: "non_recurring" });
    await created(request, finance, "/budget-grants/grants", {
      code: "DST-2026-001",
      title: "Nanomaterials for water purification",
      funder: "DST",
      sanctioned_amount: "500000.00",
      start_date: dayFromNow(0),
      end_date: dayFromNow(730),
      investigators: [{ user_id: user.id, role: "principal" }],
      lines: [{ budget_head_id: head.id, sanctioned: "500000.00" }],
    });
    await signIn(page, user);
    const panel = widget(page, "My grants");
    const rows = panel.getByRole("list", { name: "My grants" }).getByRole("listitem");
    await expect(rows).toHaveCount(1);
    await expect(rows.first()).toContainText("Nanomaterials for water purification");
    await expect(rows.first()).toContainText("DST · DST-2026-001 · Principal investigator");
    await expect(rows.first()).toContainText("Sanctioned ₹5,00,000.00 · Spent ₹0.00");
    await expect(panel.getByText("No grants yet")).toHaveCount(0);
  });
});

// Backend-dependent: these need their module's API to create the data through, so nothing here is faked.
test.fixme("projects.my-projects and projects.milestones-due show the scholar's research project and next thesis milestone", async () => {
  // practice/projects (sprint batch #339); the research-university vocabulary calls a project "Research project"
  // and a milestone "Thesis milestone". Create a project with the scholar as member and a milestone due next week.
});

test.fixme("portfolio.my-portfolio lists the scholar's publications", async () => {
  // practice/portfolio (sprint batch #322); vocabulary: a portfolio item is a "Publication".
});

test.fixme("selection-process.my-applications shows the scholar's supervisor allocation / viva applications", async () => {
  // practice/selection-process (sprint batch #322).
});

test.fixme("fees-accounts.fee-dues and hostel.notices show the scholar's own dues and notices", async () => {
  // The Student widgets' APIs grant the student role (contracts/permissions.yaml of fees-accounts and hostel);
  // write these once those contracts grant research-scholar too, or the profile maps the role onto student.
});
