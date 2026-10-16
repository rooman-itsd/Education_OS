import { expect, test } from "@playwright/test";

/**
 * Smoke check: the site talks to a real API. Read-only, so it is safe against staging:
 *
 *   E2E_BASE_URL=https://<staging-host> pnpm --filter e2e e2e
 *
 * Without E2E_BASE_URL it runs against the suite's own local stack. Against a deployed site it fails
 * until the proxy sends /api/ to the API (the web vhost answers every path with index.html).
 */

const deployed = Boolean(process.env.E2E_BASE_URL);

test("the API answers health through the site's /api/ path", async ({ request }) => {
  const response = await request.get("/api/v1/health");
  const type = response.headers()["content-type"] ?? "";
  expect(
    type,
    "/api/v1/health returned a web page, not the API: the /api/ proxy does not reach the API host",
  ).toContain("application/json");
  const health = await response.json();
  expect(health.status).toBe("ok");
  // The local stack runs on SQLite; a deployed API must be on Postgres.
  if (deployed) expect(health.database, "a deployed API must use Postgres").toBe("postgres");
});

test("the site leaves preview mode and offers sign-in", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});
