import { expect, test } from "@playwright/test";
import { organisationWithUser, type DashboardUser } from "./organisation";
import { created, dayFromNow, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Finance Staff dashboard (layout platform/identity/config/dashboards/finance-staff.yaml).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a finance-staff user signs in and lands on their dashboard;
 * - for every widget whose module is in apps/frontend/config/modules.enabled.yaml: the panel renders by its
 *   registered title and shows its empty state, or says its data is not available while the backend is missing;
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it (every
 *   widget of this layout is enabled now, payment-sbiepay through the `integrations:` list);
 * - data journeys for the two backends that allow it today: an invoice and the cash payment against it show in
 *   fees-accounts.collections-today and fees-accounts.outstanding-dues, and a grant finance records shows in
 *   budget-grants.budget-vs-spend (every scope: budgets and grants together).
 *
 * finance-operations is not in the Trial plan, so the super admin moves the organisation to Standard first.
 * The empty-state tests run before any data is created (serial mode). Loading states are covered by the modules'
 * unit tests, not here.
 */

const TITLE = "Finance Staff";

const WIDGETS: LayoutWidget[] = [
  {
    id: "fees-accounts.collections-today",
    module: "finance-operations/fees-accounts",
    batch: "#107",
    title: "Collections today",
    probe: "/fees-accounts/reports/collections",
    empty: "No collections yet today",
    unavailable: "Fee data is not available yet.",
  },
  {
    id: "fees-accounts.outstanding-dues",
    module: "finance-operations/fees-accounts",
    batch: "#107",
    title: "Outstanding dues",
    probe: "/fees-accounts/reports/outstanding",
    empty: "No outstanding dues",
    unavailable: "Fee data is not available yet.",
  },
  // An integration, not a module: listed by its folder, as apps/frontend lists it under `integrations:`.
  {
    id: "payment-sbiepay.reconciliation",
    module: "integrations/payment-sbiepay",
    batch: "#335",
    title: "Online payments reconciliation",
    probe: "/payment-sbiepay/reconciliation/summary",
    empty: "No online payments today",
    unavailable: "Payment data is not available yet.",
  },
  {
    id: "budget-grants.budget-vs-spend",
    module: "finance-operations/budget-grants",
    batch: "#128",
    title: "Budget vs spend",
    probe: "/budget-grants/reports/budget-vs-spend",
    empty: "No budget allocated",
    unavailable: "Budget data is not available yet.",
  },
  {
    id: "procurement.purchase-orders-pending",
    module: "finance-operations/procurement",
    batch: "#335",
    title: "Purchase orders pending",
    probe: "/procurement/reports/purchase-orders-pending",
    empty: "No purchase orders pending",
    unavailable: "Procurement data is not available yet.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the finance-staff user. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  user = await organisationWithUser(request, { academyType: "sports-college", role: "finance-staff" });
  await standardPlan(request, user.organisation.id);
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a finance staff user signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("finance-staff widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the finance-staff layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the finance-staff layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

test.describe("with fees-accounts data", () => {
  test("an invoice and a cash payment against it show in collections today and outstanding dues", async ({ page, request }) => {
    for (const id of ["fees-accounts.collections-today", "fees-accounts.outstanding-dues"]) {
      test.skip(!shipped(byId(id)), waitingFor(byId(id)));
      test.skip(!ready(id), `the fees-accounts API answered ${status[id]} to the finance-staff role`);
    }
    // finance-staff holds fees-accounts:fee-structure:manage, invoice:create and payment:record, so it raises an ad
    // hoc invoice to itself (person_id is a reference fees-accounts does not validate) and records part of it in cash.
    // "Today" is the server's UTC date, which dayFromNow(0) also is.
    const head = await created<{ id: string }>(request, user, "/fees-accounts/fee-heads", { code: "TUITION", name: "Tuition fee", category: "tuition" });
    const invoice = await created<{ id: string }>(request, user, "/fees-accounts/invoices", {
      person_id: user.id,
      lines: [{ fee_head_id: head.id, amount: "50000.00" }],
      due_date: dayFromNow(30),
    });
    await created(request, user, `/fees-accounts/invoices/${invoice.id}/payments`, { amount: "20000.00", mode: "cash", paid_on: dayFromNow(0) });
    await signIn(page, user);

    const today = widget(page, "Collections today");
    await expect(today.getByText("No collections yet today")).toHaveCount(0);
    const todaySummary = today.locator("dl > div");
    await expect(todaySummary.filter({ hasText: "Collected today" })).toHaveText("Collected today₹20,000.00");
    await expect(todaySummary.filter({ hasText: "Payments" })).toHaveText("Payments1");
    await expect(today.getByText("No collections the previous day", { exact: true })).toBeVisible();
    const modes = today.getByRole("list", { name: "Collections by payment mode" });
    await expect(modes).toContainText("Cash");
    await expect(modes).toContainText("1 payment");
    await expect(modes).toContainText("₹20,000.00");

    const dues = widget(page, "Outstanding dues");
    await expect(dues.getByText("No outstanding dues")).toHaveCount(0);
    const duesSummary = dues.locator("dl > div");
    await expect(duesSummary.filter({ hasText: "Outstanding" })).toHaveText("Outstanding₹30,000.00");
    await expect(duesSummary.filter({ hasText: "Overdue" })).toHaveText("Overdue₹0.00"); // due in 30 days
    await expect(duesSummary.filter({ hasText: "People with dues" })).toHaveText("People with dues1");
    const ageing = dues.getByRole("region", { name: "Ageing" });
    await expect(ageing.getByRole("listitem").filter({ hasText: "Not yet due" })).toContainText("₹30,000.00");
    await expect(ageing.getByRole("listitem").filter({ hasText: "Not yet due" })).toContainText("1 invoice");
    await expect(dues.getByRole("region", { name: "Top fee heads" })).toContainText("Tuition fee₹30,000.00");
    await expect(dues.getByText(/^As of /)).toBeVisible();
  });
});

test.describe("with budget-grants data", () => {
  test("budget-grants.budget-vs-spend shows the grant finance records against a budget head", async ({ page, request }) => {
    const w = byId("budget-grants.budget-vs-spend");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the budget-grants API answered ${status[w.id]} to the finance-staff role`);
    // finance-staff holds budget-grants:budget:manage and grant:manage. Without a scope the report counts approved
    // budgets and active grants' lines together, so a grant alone allocates its head.
    const head = await created<{ id: string }>(request, user, "/budget-grants/budget-heads", { code: "EQUIP", name: "Equipment", kind: "non_recurring" });
    await created(request, user, "/budget-grants/grants", {
      code: "DST-2026-031",
      title: "Sports science laboratory",
      funder: "DST",
      sanctioned_amount: "500000.00",
      start_date: dayFromNow(0),
      end_date: dayFromNow(730),
      investigators: [{ user_id: user.id, role: "principal" }],
      lines: [{ budget_head_id: head.id, sanctioned: "500000.00" }],
    });
    await signIn(page, user);
    const panel = widget(page, "Budget vs spend");
    await expect(panel.getByText("No budget allocated")).toHaveCount(0);
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
test.fixme("payment-sbiepay.reconciliation shows the day's gateway payments matched against the settlement", async () => {
  // The widget renders and shows its empty state above. Its data is GET /payment-sbiepay/reconciliation/summary, and
  // the payments it counts come only through the adapter's gateway: tests/e2e/playwright.config.ts does not set
  // PAYMENT_SBIEPAY_MODE=mock (nor the callback URL) for the API it starts, so none can be created in e2e yet. Then:
  // pay an invoice online through the mock gateway, run the reconciliation and expect the day's counts and amounts.
});

test.fixme("procurement.purchase-orders-pending lists an order submitted for approval", async () => {
  // The widget renders and shows its empty state above (procurement is enabled, PR #298). The journey creates a vendor, an indent that management approves and a purchase order finance submits. Approving
  // an indent needs PROCUREMENT_DIRECT_PURCHASE_LIMIT and PROCUREMENT_QUOTATION_LIMIT, and the order's budget check
  // calls budget-grants at PROCUREMENT_BUDGET_GRANTS_URL; tests/e2e/playwright.config.ts sets none of them for the
  // API it starts. Then: expect the order among those awaiting approval, with its vendor and amount.
});
