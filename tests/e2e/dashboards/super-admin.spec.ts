import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { SUPER_ADMIN } from "../stack";
import { login, organisationAdmin, pendingOrganisation } from "./organisation";
import { shipped, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Super Admin dashboard (#346; layout platform/identity/config/dashboards/super-admin.yaml).
 *
 * The platform operator signs in and lands on their dashboard. Three organisations are set up through the API so
 * every widget has something of this run to show:
 * - A, registered and verified but not approved: it waits in the approval queue;
 * - B, approved and moved to the Standard plan: it earns, so it shows in revenue and subscriptions;
 * - C, approved and still on Trial, its trial set to end in three days: it shows in trials ending soon.
 * Then A is approved and leaves the queue.
 *
 * The suite shares one database across its specs, and other journeys register organisations while this one runs,
 * so every check looks for this run's organisations by name and treats platform-wide counts as "at least", never
 * exact. Widgets whose module is not enabled or does not export them yet skip, naming what they wait for; the
 * approval itself goes through the API until the super admin screens (#95) have an approve button.
 */

const TITLE = "Super Admin";

const WIDGETS: Array<LayoutWidget & { title: string }> = [
  { id: "tenancy.approval-queue", module: "platform/tenancy", batch: "#346", title: "Approval queue" },
  { id: "tenancy.organisations-by-status", module: "platform/tenancy", batch: "#346", title: "Organisations by status" },
  { id: "tenancy.recent-registrations", module: "platform/tenancy", batch: "#346", title: "Recent registrations" },
  { id: "billing.trials-expiring", module: "platform/billing", batch: "#346", title: "Trials ending soon" },
  { id: "billing.revenue-by-plan", module: "platform/billing", batch: "#346", title: "Revenue by plan" },
  { id: "billing.subscriptions-by-plan", module: "platform/billing", batch: "#346", title: "Subscriptions by plan" },
  { id: "audit.super-admin-actions", module: "platform/audit", batch: "#317", title: "Super admin actions" },
];
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;
const SHIPPED = WIDGETS.filter(shipped);

let pending: { id: string; name: string };
let trial: { id: string; name: string };
let root: Record<string, string>;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  root = { Authorization: `Bearer ${await login(request, SUPER_ADMIN.email, SUPER_ADMIN.password)}` };
  pending = await pendingOrganisation(request, { academyType: "music-academy", label: "waiting" });
  const b = await organisationAdmin(request, { academyType: "music-academy" });
  await standardPlan(request, b.organisation.id);
  const c = await organisationAdmin(request, { academyType: "dance-academy" });
  trial = c.organisation;
  await setTrialEnd(request, trial.id, 3);
});

/** As the super admin: the organisation's trial ends `days` days from now (same time of day, so `days` whole dates). */
async function setTrialEnd(request: APIRequestContext, organisationId: string, days: number) {
  const r = await request.put(`/api/v1/billing/admin/subscriptions/${organisationId}`, {
    headers: root,
    data: { trial_ends_at: new Date(Date.now() + days * 86_400_000).toISOString(), reason: "e2e: a trial ending soon" },
  });
  expect(r.ok(), await r.text()).toBeTruthy();
}

async function signInAsSuperAdmin(page: Page) {
  await page.goto("/app"); // the dashboard app lives at /app; / is the public site
  await page.getByLabel("Email", { exact: true }).fill(SUPER_ADMIN.email);
  await page.getByLabel("Password", { exact: true }).fill(SUPER_ADMIN.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
}

/** Skips the test, naming what it waits for, unless the widget is on the dashboard. */
function needs(id: string) {
  const w = byId(id);
  test.skip(!shipped(w), waitingFor(w));
  return w;
}

/** The panel's list rows as text, once the widget has loaded. */
async function rowsOf(page: Page, title: string): Promise<string[]> {
  const panel = widget(page, title);
  await expect(panel.getByRole("listitem").first()).toBeVisible();
  return panel.getByRole("listitem").allTextContents();
}

test(`the super admin signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signInAsSuperAdmin(page);
  await expect(page.getByText("Preview mode")).toHaveCount(0);
  for (const w of SHIPPED) await expect(page.getByRole("heading", { name: w.title, exact: true })).toBeVisible();
});

test("the approval queue shows the organisation waiting for approval", async ({ page }) => {
  const w = needs("tenancy.approval-queue");
  await signInAsSuperAdmin(page);
  const panel = widget(page, w.title);
  await expect(panel.getByText(/\d+ waiting/)).toBeVisible();
  const row = panel.getByRole("listitem").filter({ hasText: pending.name });
  await expect(row).toBeVisible();
  await expect(row).toContainText("New registration · Music academy");
  await expect(row.getByText("Registration", { exact: true })).toBeVisible();
});

test("organisations by status counts the waiting and the active ones", async ({ page }) => {
  const w = needs("tenancy.organisations-by-status");
  await signInAsSuperAdmin(page);
  const rows = await rowsOf(page, w.title);
  const count = (label: string) => Number(rows.find((r) => r.startsWith(label))?.slice(label.length) ?? "-1");
  expect(rows.map((r) => r.replace(/\d+$/, ""))).toEqual(["Pending verification", "Pending approval", "Active", "Suspended", "Archived"]);
  expect(count("Pending approval")).toBeGreaterThanOrEqual(1); // A
  expect(count("Active")).toBeGreaterThanOrEqual(2); // B and C
});

test("recent registrations lists this run's organisations with their package and status", async ({ page }) => {
  const w = needs("tenancy.recent-registrations");
  await signInAsSuperAdmin(page);
  const panel = widget(page, w.title);
  await expect(panel.getByRole("listitem").first()).toBeVisible();
  // The five newest platform-wide: other journeys may register in between, so only the newest of ours is certain.
  const row = panel.getByRole("listitem").filter({ hasText: trial.name });
  await expect(row).toContainText("Dance academy");
  await expect(row).toContainText("Active");
});

test("trials ending soon shows the trial that ends in three days", async ({ page }) => {
  const w = needs("billing.trials-expiring");
  await signInAsSuperAdmin(page);
  const row = widget(page, w.title).getByRole("listitem").filter({ hasText: trial.name });
  await expect(row).toBeVisible();
  await expect(row).toContainText("ends in 3 days");
  await expect(row).toContainText("Trial");
});

test("revenue and subscriptions by plan count the Standard organisation", async ({ page }) => {
  const revenue = needs("billing.revenue-by-plan");
  const subscriptions = needs("billing.subscriptions-by-plan");
  await signInAsSuperAdmin(page);
  const earning = widget(page, revenue.title).getByRole("listitem").filter({ hasText: "Standard" });
  await expect(earning).toBeVisible();
  await expect(earning).toContainText(/\d+ active/);
  await expect(earning).toContainText(/\/mo/);
  await expect(widget(page, revenue.title).getByText(/a month/)).toBeVisible();
  const plans = widget(page, subscriptions.title);
  await expect(plans.getByRole("listitem").filter({ hasText: "Standard" })).toContainText(/\d+ active/);
  await expect(plans.getByRole("listitem").filter({ hasText: "Trial" })).toContainText(/\d+ trialing/);
});

test("an approved organisation leaves the approval queue", async ({ page, request }) => {
  const w = needs("tenancy.approval-queue");
  const approved = await request.post(`/api/v1/tenancy/admin/organisations/${pending.id}/approve`, { headers: root, data: { reason: "e2e" } });
  expect(approved.ok(), await approved.text()).toBeTruthy();
  await signInAsSuperAdmin(page);
  const panel = widget(page, w.title);
  await expect(panel.getByText(/\d+ waiting|Nothing waiting for approval/)).toBeVisible();
  await expect(panel.getByText(pending.name)).toHaveCount(0);
});

test("super admin actions waits for platform/audit", async ({ page }) => {
  const w = needs("audit.super-admin-actions");
  await signInAsSuperAdmin(page);
  await expect(widget(page, w.title)).toBeVisible();
});
