import { chromium, type FullConfig } from "@playwright/test";
import { spawn } from "node:child_process";
import { SUPER_ADMIN } from "./stack";

/**
 * Starts the event-bus relay (`python -m eos_event_bus`) on the API's database, as production runs it, and returns the
 * function that stops it. Without it nothing delivers events between modules: a course space never learns its
 * instructor, enrolment-registration never learns an offering, a roster never fills. playwright.config.ts hands over the
 * interpreter, directory and environment.
 */
function startRelay() {
  const handover = process.env.E2E_RELAY;
  if (!handover) return undefined;
  const { python, cwd, env } = JSON.parse(handover) as { python: string; cwd: string; env: Record<string, string> };
  const relay = spawn(python, ["-m", "eos_event_bus"], { cwd, env, stdio: ["ignore", "ignore", "pipe"] });
  let log = "";
  relay.stderr.on("data", (chunk: Buffer) => {
    log = (log + chunk.toString()).slice(-4000);
  });
  relay.on("exit", (code) => {
    if (code) console.error(`the event-bus relay stopped with code ${code}:\n${log}`);
  });
  return () => {
    relay.kill();
  };
}

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
  const stopRelay = startRelay();
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ baseURL });
    await page.goto("/app", { timeout: 120_000 });
    await page.getByLabel("Email", { exact: true }).fill(SUPER_ADMIN.email);
    await page.getByLabel("Password", { exact: true }).fill(SUPER_ADMIN.password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.getByRole("region", { name: "Super Admin dashboard" }).waitFor({ timeout: 180_000 });
  } catch (error) {
    stopRelay?.(); // a failed warm-up must not leave the relay running
    throw error;
  } finally {
    await browser.close();
  }
  return stopRelay;
}
