import { expect, test, type APIRequestContext } from "@playwright/test";
import { SUPER_ADMIN } from "../stack";

/**
 * The onboarding journey (ADR-0005): an organisation registers and verifies its email, cannot sign in
 * until a super admin approves its academic package, then signs in and lands on its dashboard.
 *
 * Approval goes through the API until the super admin approval queue exists in apps/frontend.
 */

async function approveAsSuperAdmin(request: APIRequestContext, slug: string) {
  const login = await request.post("/api/v1/identity/auth/login", { data: SUPER_ADMIN });
  expect(login.ok(), await login.text()).toBeTruthy();
  const headers = { Authorization: `Bearer ${(await login.json()).token}` };

  const pending = await request.get("/api/v1/tenancy/admin/organisations?status=pending_approval", { headers });
  expect(pending.ok(), await pending.text()).toBeTruthy();
  const org = ((await pending.json()) as { id: string; slug: string }[]).find((o) => o.slug === slug);
  expect(org, `${slug} is waiting for approval`).toBeTruthy();

  const approved = await request.post(`/api/v1/tenancy/admin/organisations/${org!.id}/approve`, {
    headers,
    data: { reason: "e2e" },
  });
  expect(approved.ok(), await approved.text()).toBeTruthy();
  expect((await approved.json()).status).toBe("active");
}

test("register, approve, sign in, dashboard", async ({ page, request }) => {
  const run = Date.now().toString(36);
  const org = {
    name: `E2E Engineering ${run}`,
    slug: `e2e-${run}`,
    email: `admin@e2e-${run}.example.com`,
    password: "Passw0rd!e2e",
  };

  await test.step("register the organisation", async () => {
    await page.goto("/#signup");
    await expect(page.getByRole("heading", { name: "Register your organisation" })).toBeVisible();
    await page.getByLabel("Organisation name").fill(org.name);
    await page.getByLabel("Short name").fill(org.slug);
    await page.getByLabel("Academy type").selectOption("engineering-college");
    await page.getByLabel("Your name").fill("E2E Admin");
    await page.getByLabel("Work email").fill(org.email);
    await page.getByLabel("Password").fill(org.password);
    await page.getByRole("button", { name: "Create organisation" }).click();
  });

  await test.step("verify the email", async () => {
    await expect(page.getByRole("heading", { name: "Verify your email" })).toBeVisible();
    // Dev mode returns the token, which the page pre-fills in place of the emailed one.
    await expect(page.getByLabel("Verification token")).not.toHaveValue("");
    await page.getByRole("button", { name: "Activate organisation" }).click();
    await expect(page.getByRole("heading", { name: "Email verified" })).toBeVisible();
  });

  await test.step("sign-in is refused until approval", async () => {
    await page.getByRole("link", { name: "Back to sign in" }).click();
    // exact: the organisation field's hint also says "email"
    await page.getByLabel("Email", { exact: true }).fill(org.email);
    await page.getByLabel("Password", { exact: true }).fill(org.password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("alert")).toContainText("waiting for platform approval");
  });

  await test.step("a super admin approves it", async () => {
    await approveAsSuperAdmin(request, org.slug);
  });

  await test.step("sign in", async () => {
    await page.getByRole("button", { name: "Sign in" }).click();
  });

  await test.step("land on the organisation admin dashboard", async () => {
    await expect(page.getByRole("heading", { level: 1, name: "Organisation Admin" })).toBeVisible();
    await expect(page.getByLabel("Organisation and plan")).toContainText(org.name);
    await expect(page.getByText("Preview mode")).toHaveCount(0);
  });
});
