import { defineConfig, devices } from "@playwright/test";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { API_PORT, SUPER_ADMIN, WEB_PORT } from "./stack";

const repoRoot = fileURLToPath(new URL("../..", import.meta.url));

// The repo's virtualenv (tools/scripts/py-setup.sh); E2E_PYTHON overrides it, e.g. in CI.
const python =
  process.env.E2E_PYTHON ??
  join(repoRoot, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");

// A fresh database per run: every journey starts from an empty platform.
const database = join(mkdtempSync(join(tmpdir(), "eos-e2e-")), "e2e.db").replaceAll("\\", "/");

// E2E_BASE_URL points the suite at a deployed site (staging) instead of starting its own stack. Only the
// read-only smoke checks run then: every other journey registers organisations and would write to a real
// database.
const deployed = process.env.E2E_BASE_URL?.replace(/\/$/, "");

const localStack = [
  {
    name: "api",
    command: `"${python}" -m uvicorn eos_backend.main:app --port ${API_PORT}`,
    cwd: repoRoot,
    url: `http://127.0.0.1:${API_PORT}/api/v1/health`,
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      ...process.env,
      EOS_DATABASE_URL: `sqlite:///${database}`,
      EOS_DEV_MODE: "true", // returns the verification token, so no mailbox is needed
      EOS_SUPER_ADMIN_EMAIL: SUPER_ADMIN.email,
      EOS_SUPER_ADMIN_PASSWORD: SUPER_ADMIN.password,
      TENANCY_AUTO_APPROVE: "false", // the journey includes the super admin's approval
      BILLING_PAYMENT_ADAPTER: "none",
      EOS_CORS_ORIGINS: `http://localhost:${WEB_PORT}`,
      EOS_RATE_LIMIT_ENABLED: "false", // every spec signs in from 127.0.0.1; the sign-in bucket would refuse them
    } as Record<string, string>,
  },
  {
    name: "web",
    command: `pnpm --filter @eos/frontend exec vite --port ${WEB_PORT} --strictPort`,
    cwd: repoRoot,
    url: `http://localhost:${WEB_PORT}`,
    reuseExistingServer: false,
    timeout: 60_000,
    env: { ...process.env, EOS_API_TARGET: `http://127.0.0.1:${API_PORT}` } as Record<string, string>,
  },
];

export default defineConfig({
  testDir: ".",
  testMatch: deployed ? "smoke/**/*.spec.ts" : "**/*.spec.ts",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  // Traces, screenshots and the HTML report go under .cache/, which .gitignore already covers.
  outputDir: ".cache/test-results",
  reporter: [["list"], ["html", { open: "never", outputFolder: ".cache/playwright-report" }]],
  use: {
    baseURL: deployed ?? `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: deployed ? undefined : localStack,
});
