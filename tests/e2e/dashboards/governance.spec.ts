import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, dayFromNow, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Governance (Grievance / RTI / IQAC) dashboard (layout platform/identity/config/dashboards/governance.yaml; the role
 * exists in every academy profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a governance officer signs in and lands on their dashboard;
 * - for every widget of the layout whose module is in apps/frontend/config/modules.enabled.yaml: the panel renders by
 *   its registered title and shows its empty state for a new organisation (the governance role holds
 *   grievance-coordinator, rti-officer, iqac-accreditation-coordinator and regulatory-reports-coordinator through the
 *   layout's module_roles);
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it (#343);
 * - data journeys, each skipped until its module is enabled: a grievance committee the officer sets up shows in
 *   `grievance.open-by-committee`, and an IQAC action item due in 5 days shows in `iqac-accreditation.action-items`.
 *
 * The organisation is moved to Standard first, as in the other journeys. The empty-state tests run before any data is
 * created (serial mode). Loading states are covered by the modules' unit tests, not here. rti and regulatory-reports
 * have no data journey yet: their requests and filings need the officer to be assigned and a calendar to be set up,
 * which this journey leaves to the modules' own tests.
 */

const TITLE = "Governance (Grievance / RTI / IQAC)";

const WIDGETS: LayoutWidget[] = [
  {
    id: "grievance.open-by-committee",
    module: "governance/grievance",
    batch: "#343",
    title: "Open grievances by committee",
    probe: "/grievance/stats/open-by-committee",
    empty: "No committees yet",
    unavailable: "Grievance data is not available yet.",
    forbidden: "You do not have access to this.",
  },
  {
    id: "rti.nearing-deadline",
    module: "governance/rti",
    batch: "#343",
    title: "RTI requests nearing a deadline",
    probe: "/rti/stats/nearing-deadline",
    empty: "No RTI deadlines close",
    unavailable: "RTI data is not available yet.",
    forbidden: "You do not have access to this.",
  },
  {
    id: "iqac-accreditation.action-items",
    module: "governance/iqac-accreditation",
    batch: "#343",
    title: "IQAC action items",
    probe: "/iqac-accreditation/stats/action-items",
    empty: "No open action items",
    unavailable: "IQAC data is not available yet.",
    forbidden: "You do not have access to this.",
  },
  {
    id: "regulatory-reports.due",
    module: "governance/regulatory-reports",
    batch: "#343",
    title: "Regulatory filings due",
    probe: "/regulatory-reports/stats/due?scope=mine",
    empty: "Nothing due",
    unavailable: "Regulatory report data is not available yet.",
    forbidden: "You do not have access to this.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the governance officer. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "engineering-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "governance");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a governance officer signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("governance widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the governance layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the governance layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

test.describe("with grievance data", () => {
  test("grievance.open-by-committee lists a committee the officer sets up", async ({ page, request }) => {
    const w = byId("grievance.open-by-committee");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the grievance API answered ${status[w.id]} to the governance role`);
    await created(request, user, "/grievance/committees", { name: "Student Grievance Redressal Committee", kind: "sgrc" });
    await signIn(page, user);

    const panel = widget(page, "Open grievances by committee");
    await expect(panel.getByText("No committees yet")).toHaveCount(0);
    await expect(panel.getByText("0 open cases · None overdue")).toBeVisible();
    const row = panel.getByRole("list", { name: "Open cases by committee" }).getByRole("listitem").filter({ hasText: "Student Grievance Redressal Committee" });
    await expect(row).toContainText("0 open · None overdue");
  });
});

test.describe("with iqac-accreditation data", () => {
  test("iqac-accreditation.action-items lists an action item due in 5 days", async ({ page, request }) => {
    const w = byId("iqac-accreditation.action-items");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the iqac-accreditation API answered ${status[w.id]} to the governance role`);
    // owner_id is a reference the module does not validate; the officer owns the item.
    await created(request, user, "/iqac-accreditation/action-items", {
      title: "Update the AQAR evidence folder",
      owner_id: user.id,
      due_on: dayFromNow(5),
    });
    await signIn(page, user);

    const panel = widget(page, "IQAC action items");
    await expect(panel.getByText("No open action items")).toHaveCount(0);
    await expect(panel.getByText("1 open · 0 in progress · 0 overdue")).toBeVisible();
    const row = panel.getByRole("list", { name: "Action items" }).getByRole("listitem").filter({ hasText: "Update the AQAR evidence folder" });
    await expect(row).toContainText("Open");
    // The page counts days in the browser's time zone, the date above in UTC: a day either way is the same item.
    await expect(row).toContainText(/Due in [456] days/);
  });
});
