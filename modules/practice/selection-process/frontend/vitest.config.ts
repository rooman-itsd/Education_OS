import { defineConfig } from "vitest/config";

// Dates in the widgets are shown in the viewer's zone; run the tests in a fixed zone so the expectations are stable.
process.env.TZ = "Asia/Kolkata";

export default defineConfig({
  test: { globals: true, environment: "jsdom", include: ["tests/**/*.test.{ts,tsx}"], css: false },
});
