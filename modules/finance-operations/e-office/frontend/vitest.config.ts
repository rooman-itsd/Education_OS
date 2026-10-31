import { defineConfig } from "vitest/config";

// The widget shows due dates and the date each file was received; tests pin the time zone so the expected text is exact.
process.env.TZ = "Asia/Kolkata";

export default defineConfig({
  test: { globals: true, environment: "jsdom", include: ["tests/**/*.test.{ts,tsx}"], css: false },
});
