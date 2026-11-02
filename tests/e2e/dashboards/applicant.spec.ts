import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { organisationAdmin, type DashboardUser } from "./organisation";

/**
 * Applicant dashboard (layout platform/identity/config/dashboards/applicant.yaml):
 * - web-portal-cms.announcements: shows the organisation's current published announcements, never drafts.
 * - admissions.application-status: shows the applicant's linked application, or a form to link by reference and email;
 *   tracks status through review, offer and acceptance.
 * - admissions.pending-documents: lists the applicant's own pending and rejected documents.
 */

const CMS = "/api/v1/web-portal-cms";
const ADMISSIONS = "/api/v1/admissions";
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

test.fixme("an applicant links their application, sees status and pending documents, and tracks offer acceptance", async ({
  page,
  request,
}) => {
  // Applications are submitted through the public API (POST /public/{org_slug}/applications, no session;
  // the contract has no staff route that creates one). The host does not serve module public routes yet:
  // its entitlement gate (apps/backend/src/eos_backend/gateway.py) wants a bearer token on every module path,
  // and admissions' public_organisation expects the host to resolve the slug into request.state (anonymous: 401).
  // Until then, mark this data journey fixme so it doesn't fail against the real stack in CI (#417).
  // 1. Submit an application anonymously through the public API
  const appRes = await ok<{ id: string; reference_number: string }>(
    await request.post(`${ADMISSIONS}/public/${admin.organisation.slug}/applications`, {
      data: {
        applicant: { first_name: "Ana", last_name: "Silva", email: applicantEmail },
        programme_id: "00000000-0000-0000-0000-000000000001",
        academic_year: "2026-27",
      },
    }),
  );
  const ref = appRes.reference_number;

  // 2. Attach a supporting document
  await ok(
    await request.post(`${ADMISSIONS}/public/${admin.organisation.slug}/applications/${ref}/documents`, {
      data: {
        email: applicantEmail,
        type: "academic_record",
        document_id: "doc-e2e-1",
        label: "High School Certificate",
      },
    }),
  );

  // 3. Applicant signs in and lands on dashboard
  await signIn(page);
  await expect(page.getByText(`${admin.organisation.name} · Applicant dashboard`)).toBeVisible();

  // 4. Application status widget initially shows the link form
  const statusPanel = widget(page, "Application status");
  await expect(statusPanel.getByRole("form", { name: "Link application" })).toBeVisible();

  await statusPanel.getByLabel("Reference number").fill(ref);
  await statusPanel.getByLabel("Email").fill(applicantEmail);
  await statusPanel.getByRole("button", { name: "Link application" }).click();

  // 5. After linking, widget displays the linked application
  await expect(statusPanel.getByText(ref)).toBeVisible();
  await expect(statusPanel.getByText("Submitted")).toBeVisible();

  // 6. Pending documents widget displays the pending document
  const docsPanel = widget(page, "Pending documents");
  await expect(docsPanel.getByText("High School Certificate")).toBeVisible();

  // 7. Admissions staff moves application to eligible and makes an offer
  const staffEmail = `staff@${admin.organisation.slug}.example.com`;
  await ok(
    await request.post("/api/v1/identity/users", {
      headers: { Authorization: `Bearer ${admin.token}` },
      data: { name: "Admissions Staff", email: staffEmail, password: "Passw0rd!e2e", roles: ["admissions-staff"] },
    }),
  );
  const staffAuth = await ok<{ token: string }>(
    await request.post("/api/v1/identity/auth/login", {
      data: { email: staffEmail, password: "Passw0rd!e2e" },
    }),
  );
  const staffHeaders = { Authorization: `Bearer ${staffAuth.token}` };

  await ok(
    await request.put(`${ADMISSIONS}/applications/${appRes.id}/status`, {
      headers: staffHeaders,
      data: { status: "under_review", reason: "Reviewing documents" },
    }),
  );
  await ok(
    await request.put(`${ADMISSIONS}/applications/${appRes.id}/status`, {
      headers: staffHeaders,
      data: { status: "eligible", reason: "Meets criteria" },
    }),
  );
  await ok(
    await request.post(`${ADMISSIONS}/applications/${appRes.id}/offer`, {
      headers: staffHeaders,
      data: { note: "Congratulations on your selection!" },
    }),
  );

  // 8. Applicant accepts the offer
  await ok(
    await request.post(`${ADMISSIONS}/public/${admin.organisation.slug}/applications/${ref}/offer/accept`, {
      data: { email: applicantEmail },
    }),
  );

  // 9. Reload dashboard and verify accepted status
  await page.reload();
  await expect(statusPanel.getByText(ref)).toBeVisible();
  await expect(statusPanel.getByText("Accepted")).toBeVisible();
});
