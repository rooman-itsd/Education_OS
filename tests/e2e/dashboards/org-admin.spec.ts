import { expect, test, type Page } from "@playwright/test";
import { organisationAdmin, type DashboardUser } from "./organisation";

/**
 * Organisation Admin dashboard (issue #1; layout platform/identity/config/dashboards/org-admin.yaml).
 *
 * The admin who registered the organisation signs in and sees the six platform widgets. billing, tenancy and
 * identity are mounted in the API, so their widgets show real data; platform/audit is not mounted yet, so its
 * widget says its data is not available. The package change is exercised through the API-less path: the local
 * stack runs with BILLING_PAYMENT_ADAPTER=none, so switching plan applies at once and the dashboard reloads
 * on the new plan.
 */

const WIDGETS = [
  { id: "billing.plan-and-trial", title: "Plan and trial" },
  { id: "billing.usage-vs-limits", title: "Usage against limits" },
  { id: "tenancy.enabled-modules", title: "Enabled modules" },
  { id: "identity.users-and-roles", title: "Users and roles" },
  { id: "billing.invoices", title: "Invoices" },
  { id: "audit.recent-activity", title: "Recent activity" },
] as const;

let admin: DashboardUser;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "music-academy" });
});

async function signIn(page: Page) {
  await page.goto("/app"); // the dashboard app lives at /app; / is the public site
  await page.getByLabel("Email", { exact: true }).fill(admin.email);
  await page.getByLabel("Password", { exact: true }).fill(admin.password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** The panel a widget renders in, found by its heading. */
const widget = (page: Page, title: string) =>
  page.locator(".eos-widget").filter({ has: page.getByRole("heading", { name: title, exact: true }) });

test("the organisation admin signs in and sees every widget of the layout", async ({ page }) => {
  await signIn(page);
  const dashboard = page.getByRole("region", { name: "Organisation Admin dashboard" });
  await expect(dashboard).toBeVisible();
  for (const w of WIDGETS) await expect(dashboard.getByRole("heading", { name: w.title, exact: true })).toBeVisible();
});

test("plan, usage, modules, users and invoices show the organisation's real data", async ({ page }) => {
  await signIn(page);
  const plan = widget(page, "Plan and trial");
  await expect(plan.getByText("Trial", { exact: true })).toBeVisible();
  await expect(plan.getByText(/Trial ends/)).toBeVisible();
  await expect(widget(page, "Usage against limits").getByText("1 of 25 users")).toBeVisible();
  await expect(widget(page, "Enabled modules").getByRole("list", { name: "Modules by suite" })).toBeVisible();
  const users = widget(page, "Users and roles");
  await expect(users.getByText("1 user")).toBeVisible();
  await expect(users.getByText("Org admin")).toBeVisible();
  await expect(widget(page, "Invoices").getByText("No invoices yet")).toBeVisible();
});

test("recent activity says its data is not available until platform/audit is mounted", async ({ page, request }) => {
  const probe = await request.get("/api/v1/audit/records?limit=1", { headers: { Authorization: `Bearer ${admin.token}` } });
  test.skip(probe.status() !== 404, "platform/audit is mounted; this journey is for the time before it");
  await signIn(page);
  const alert = widget(page, "Recent activity").getByRole("alert");
  await expect(alert).toContainText("Audit data is not available yet.");
  await expect(alert.getByRole("button", { name: "Try again" })).toBeVisible();
});

test("the package change switches the plan and the dashboard comes back on it, with an invoice", async ({ page }) => {
  await signIn(page);
  const plan = widget(page, "Plan and trial");
  await plan.getByRole("button", { name: "Switch to Standard" }).click();
  await expect(widget(page, "Plan and trial").getByText("Standard", { exact: true })).toBeVisible();
  await expect(widget(page, "Plan and trial").getByText("Active", { exact: true })).toBeVisible();
  await expect(widget(page, "Invoices").getByText(/Standard · ₹24,999/)).toBeVisible();
  await expect(widget(page, "Usage against limits").getByText("1 of 500 users")).toBeVisible();
});
