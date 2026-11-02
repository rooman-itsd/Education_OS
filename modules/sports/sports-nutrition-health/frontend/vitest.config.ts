import { defineConfig } from "vitest/config";

// The appointments-today tests check a local day that spans two UTC days (India, UTC+05:30). The zone must be set
// here, before any test worker starts: `test.env` is applied too late to change the zone Date already uses, so the
// tests would pass only on a machine already set to India time.
process.env.TZ = "Asia/Kolkata";

export default defineConfig({
  test: { globals: true, environment: "jsdom", include: ["tests/**/*.test.{ts,tsx}"], css: false },
});
