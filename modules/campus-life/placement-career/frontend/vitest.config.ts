import { defineConfig } from "vitest/config";

// The widgets show contract dates (drive dates, closing dates) as Indian dates; the tests run in a zone far from
// India so a date read in the viewer's zone instead of Asia/Kolkata would show the wrong day.
process.env.TZ = "America/Los_Angeles";

export default defineConfig({
  test: { globals: true, environment: "jsdom", include: ["tests/**/*.test.{ts,tsx}"], css: false },
});
