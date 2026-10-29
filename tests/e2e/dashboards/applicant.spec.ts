import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { organisationAdmin, type DashboardUser } from "./organisation";

/**
 * Applicant dashboard (layout platform/identity/config/dashboards/applicant.yaml): the web-portal-cms.announcements
 * widget shows the organisation's current announcements to a signed-in applicant, and never a draft.
 * The organisation admin (who holds web-portal-cms:announcement:manage) writes them through the API; the applicant
 * reads through the implicit member role.
 */

const CMS = "/api/v1/web-portal-cms";
const APPLICANT = { name: "E2E Applicant", password: "Passw0rd!e2e" };

let admin: DashboardUser;
let applicantEmail: string;

test.describe.configure({ mode: "serial" });

async function ok<T = unknown>(response: Awaited<ReturnType<APIRequestContext["post"]>>): Promise<T> {
  expect(response.ok(), `${response.url()} → ${response.status()} ${await response.text()}`).toBeTruthy();
  return (await response.json()) as T;
}

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "sports-college" });
  const headers = { Authorization: `Bearer ${admin.token}` };
  applicantEmail = `applicant@${admin.organisation.slug}.example.com`;
  await ok(
    await request.post("/api/v1/identity/users", {
      headers,
      data: { ...APPLICANT, email: applicantEmail, roles: ["applicant"] },
    }),
  );

  const published = await ok<{ id: string }>(
    await request.post(`${CMS}/announcements`, {
      headers,
      data: { title: "Admissions open for 2026-27", body: "Apply by 30 November.\nLate applications are not accepted." },
    }),
  );
  await ok(await request.post(`${CMS}/announcements/${published.id}/publish`, { headers, data: { published: true } }));
  await ok(await request.post(`${CMS}/announcements`, { headers, data: { title: "Draft: fee revision", body: "Not final." } }));
});

async function signIn(page: Page) {
  await page.goto("/app"); // the dashboard app lives at /app; / is the public site
  await page.getByLabel("Email", { exact: true }).fill(applicantEmail);
  await page.getByLabel("Password", { exact: true }).fill(APPLICANT.password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** The panel a widget renders in, found by its heading. */
const widget = (page: Page, title: string) =>
  page.locator(".eos-widget").filter({ has: page.getByRole("heading", { name: title, exact: true }) });

test("an applicant sees the organisation's published announcement and not its draft", async ({ page }) => {
  await signIn(page);
  await expect(page.getByText(`${admin.organisation.name} · Applicant dashboard`)).toBeVisible();
  const panel = widget(page, "Announcements");
  const rows = panel.getByRole("list", { name: "Announcements" }).getByRole("listitem");
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText("Admissions open for 2026-27");
  await expect(rows.first()).toContainText("Apply by 30 November. Late applications are not accepted.");
  await expect(panel.getByText("Draft: fee revision")).toHaveCount(0);
});
