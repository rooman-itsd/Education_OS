import { defineConfig } from "vitest/config";

// The payroll widget compares the run's month with today's Indian month; tests pin the zone so the expected text is exact.
process.env.TZ = "Asia/Kolkata";

export default defineConfig({
  test: { globals: true, environment: "jsdom", include: ["tests/**/*.test.{ts,tsx}"], css: false },
});
