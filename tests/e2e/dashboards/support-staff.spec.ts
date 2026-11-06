import { expect, test, type APIRequestContext } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { dayFromNow, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Support Staff (Helpdesk) dashboard (layout platform/identity/config/dashboards/support-staff.yaml; the role exists
 * in every academy profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a support staff member signs in and lands on their dashboard;
 * - for every widget of the layout whose module is in apps/frontend/config/modules.enabled.yaml: the panel renders by
 *   its registered title and shows its empty state for a new organisation;
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch (#342);
 * - data journey: an AMC contract the organisation admin records and activates, ending in 20 days, shows in
 *   amc-vendor-support.contracts-expiring. It needs the module enabled and org-admin holding
 *   amc-vendor-support-contract-manager through its layout; until then it skips, naming what refused it.
 *
 * The organisation is moved to Standard first, as in the other journeys. The empty-state tests run before any data is
 * created (serial mode). Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Support Staff (Helpdesk)";

const WIDGETS: LayoutWidget[] = [
  {
    id: "helpdesk.open-by-priority",
    module: "support/helpdesk",
    batch: "#113",
    title: "Open tickets by priority",
    probe: "/helpdesk/stats/open-by-priority",
    empty: "No open tickets",
    unavailable: "Helpdesk data is not available yet.",
  },
  {
    id: "sla-management.breaches",
    module: "support/sla-management",
    batch: "#342",
    title: "SLA breaches",
    probe: "/sla-management/stats/breaches?scope=mine",
    empty: "Nothing breached or at risk",
    unavailable: "SLA data is not available yet.",
  },
  {
    id: "incident-management.open",
    module: "support/incident-management",
    batch: "#342",
    title: "Open incidents",
    probe: "/incident-management/stats/open",
    empty: "No open incidents",
    unavailable: "Incident data is not available yet.",
  },
  {
    id: "amc-vendor-support.contracts-expiring",
    module: "support/amc-vendor-support",
    batch: "#342",
    title: "AMC contracts expiring",
    probe: "/amc-vendor-support/stats/contracts-expiring",
    empty: "No contracts expiring",
    unavailable: "AMC data is not available yet.",
  },
  {
    id: "knowledge-base.top-articles",
    module: "support/knowledge-base",
    batch: "#342",
    title: "Top articles",
    probe: "/knowledge-base/stats/top-articles",
    empty: "No article views yet",
    unavailable: "Knowledge base data is not available yet.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let admin: DashboardUser;
let user: DashboardUser;
/** Per shipped widget id: what its GET answered the support staff member. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "engineering-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "support-staff");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a support staff member signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("support-staff widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the support-staff layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the support-staff layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

/** POST under /api/v1 as `who`; the response, so a refusal can be turned into a skip with its reason. */
const post = (request: APIRequestContext, who: DashboardUser, path: string, data: unknown) =>
  request.post(`/api/v1${path}`, { headers: { Authorization: `Bearer ${who.token}` }, data });

test.describe("with amc-vendor-support data", () => {
  test("amc-vendor-support.contracts-expiring lists a contract the organisation admin activates, ending in 20 days", async ({ page, request }) => {
    const w = byId("amc-vendor-support.contracts-expiring");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the amc-vendor-support API answered ${status[w.id]} to the support-staff role`);
    // The organisation admin records the contract (amc-vendor-support:contract:manage through org-admin's layout).
    const contract = await post(request, admin, "/amc-vendor-support/contracts", {
      vendor_id: "11111111-1111-4111-8111-111111111111",
      title: "Lift maintenance, main block",
      coverage_type: "comprehensive",
      start_date: dayFromNow(-345),
      end_date: dayFromNow(20),
      renewal_notice_days: 60,
    });
    test.skip(contract.status() === 403, "org-admin does not hold amc-vendor-support-contract-manager through its layout yet");
    expect(contract.ok(), await contract.text()).toBeTruthy();
    const { id } = (await contract.json()) as { id: string };
    const activated = await post(request, admin, `/amc-vendor-support/contracts/${id}/activate`, {});
    expect(activated.ok(), await activated.text()).toBeTruthy();
    await signIn(page, user);

    const panel = widget(page, "AMC contracts expiring");
    await expect(panel.getByText("No contracts expiring")).toHaveCount(0);
    const row = panel.getByRole("list", { name: "Contracts expiring" }).getByRole("listitem").filter({ hasText: "Lift maintenance, main block" });
    await expect(row).toContainText("20 days left");
  });
});
