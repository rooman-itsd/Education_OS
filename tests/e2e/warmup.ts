import { chromium, type FullConfig } from "@playwright/test";
import { SUPER_ADMIN } from "./stack";

/**
 * Global setup: sign in once as the super admin and wait until the dashboard has loaded its modules, before any
 * journey starts. The web server is Vite in dev mode, which compiles every module's widgets on the first dashboard
 * visit; with several journeys signing in at once on a cold server that first visit took longer than an assertion
 * waits, and the journeys failed on "Loading modules…" instead of on anything they test. Runs after the web servers
 * are up; skipped against a deployed site (E2E_BASE_URL), which serves a built app.
 */
export default async function warmUp(config: FullConfig) {
  if (process.env.E2E_BASE_URL) return;
  const baseURL = config.projects[0]?.use.baseURL;
  if (!baseURL) return;
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ baseURL });
    await page.goto("/app", { timeout: 120_000 });
    await page.getByLabel("Email", { exact: true }).fill(SUPER_ADMIN.email);
    await page.getByLabel("Password", { exact: true }).fill(SUPER_ADMIN.password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.getByRole("region", { name: "Super Admin dashboard" }).waitFor({ timeout: 180_000 });
  } finally {
    await browser.close();
  }
}
