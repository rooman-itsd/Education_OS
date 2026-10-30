import { expect, test } from "@playwright/test";
import { organisationWithUser, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Management (VC, Registrar) dashboard (layout platform/identity/config/dashboards/management.yaml).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a management user signs in and lands on their dashboard;
 * - for every widget whose module is in apps/frontend/config/modules.enabled.yaml: the panel renders by its
 *   registered title and shows its empty state, or says its data is not available while the backend is missing;
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it;
 * - data journeys for the two backends that exist today: an application submitted on the public admissions page
 *   reaches the funnel, and the collection targets management sets show against collections.
 *
 * fees-accounts is finance-operations, which the Trial plan does not include, so the super admin moves the
 * organisation to Standard first. Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Management (VC, Registrar)";

const WIDGETS: LayoutWidget[] = [
  {
    id: "admissions.funnel",
    module: "student-lifecycle/admissions",
    batch: "#321",
    title: "Admissions funnel",
    probe: "/admissions/reports/funnel",
    empty: "No applications yet",
    unavailable: "Admissions data is not available yet.",
  },
  {
    id: "fees-accounts.collection-vs-target",
    module: "finance-operations/fees-accounts",
    batch: "#107",
    title: "Collection vs target",
    probe: "/fees-accounts/reports/collection-vs-target",
    empty: "No collection targets set",
    unavailable: "Fee data is not available yet.",
  },
  { id: "reporting.attendance-and-results-by-department", module: "platform/reporting", batch: "#317" },
  { id: "grievance.open", module: "governance/grievance", batch: "#343" },
  { id: "regulatory-reports.compliance-calendar", module: "governance/regulatory-reports", batch: "#343" },
  { id: "productions.upcoming", module: "practice/productions", batch: "#318" },
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the management user. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  user = await organisationWithUser(request, { academyType: "sports-college", role: "management" });
  await standardPlan(request, user.organisation.id);
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a management user signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("management widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the management layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the management layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

test.describe("with admissions and fees data", () => {
  test.fixme("admissions.funnel counts an application submitted on the public admissions page", async () => {
    // Applications are only created by applicants (POST /public/{org_slug}/applications, no session; the contract
    // has no staff route that creates one). The host does not reach that route yet: its entitlement gate
    // (apps/backend/src/eos_backend/gateway.py) wants a bearer token on every module path, and admissions'
    // public_organisation expects the host to resolve the slug into request.state (anonymous: 401; with a
    // session: 404 unknown_organisation). Until then the funnel's empty state above is what the dashboard shows.
    // Then: submit one application for the organisation's slug (a programme id is a reference admissions does not
    // validate) and expect the four stages Applied, Eligible, Offered, Accepted, and the summary
    // "Overall acceptance 0% · 1 application".
  });

  test("fees-accounts.collection-vs-target shows the targets management sets for the academic year", async ({ page, request }) => {
    test.skip(!shipped(byId("fees-accounts.collection-vs-target")), waitingFor(byId("fees-accounts.collection-vs-target")));
    test.skip(!ready("fees-accounts.collection-vs-target"), `the fees-accounts API answered ${status["fees-accounts.collection-vs-target"]} to the management role`);
    // The report names the current academic year and its months; set one month's target for that year
    // (PUT /collection-targets, permission fees-accounts:target:manage, which management holds).
    const auth = { Authorization: `Bearer ${user.token}` };
    const before = await request.get("/api/v1/fees-accounts/reports/collection-vs-target", { headers: auth });
    const report = (await before.json()) as { academic_year: string; periods: { period: string }[] };
    const period = report.periods[0]!.period;
    const set = await request.put("/api/v1/fees-accounts/collection-targets", {
      headers: auth,
      data: { academic_year: report.academic_year, targets: [{ period, amount: "120000.00" }] },
    });
    expect(set.ok(), await set.text()).toBeTruthy();
    await signIn(page, user);
    const panel = widget(page, "Collection vs target");
    await expect(panel.getByText("No collection targets set")).toHaveCount(0);
    await expect(panel.getByText("Target", { exact: true })).toBeVisible();
    await expect(panel.getByText("₹1,20,000.00", { exact: true })).toBeVisible();
    await expect(panel.getByText("Achieved", { exact: true })).toBeVisible();
    await expect(panel.getByText("0%", { exact: true })).toBeVisible();
    await expect(panel.getByRole("list", { name: "Collected against target by month" })).toContainText("₹0.00 of ₹1,20,000.00 · 0%");
    await expect(panel.getByText(`Academic year ${report.academic_year}`)).toBeVisible();
  });
});

// Backend-dependent: these need their module's API to create the data through, so nothing here is faked.
test.fixme("reporting.attendance-and-results-by-department shows each department's attendance and pass rate", async () => {
  // platform/reporting (sprint batch #317). Record attendance and results for two departments; expect one row
  // per department with its attendance percent and results summary.
});

test.fixme("grievance.open lists open grievances with the oldest first", async () => {
  // governance/grievance (sprint batch #343). File two grievances and resolve one; expect the open one with
  // its age and the open count.
});

test.fixme("regulatory-reports.compliance-calendar shows the next filings due", async () => {
  // governance/regulatory-reports (sprint batch #343). Register a report due next month; expect it with its
  // due date and the regulator.
});

test.fixme("productions.upcoming lists the next productions", async () => {
  // practice/productions (sprint batch #318). Schedule a production next week; expect it with its date and venue.
});
