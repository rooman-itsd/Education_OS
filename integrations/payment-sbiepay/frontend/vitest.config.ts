import { defineConfig } from "vitest/config";

// The widget shows the last reconciliation time in the viewer's time zone; tests pin it so the expected text is exact.
process.env.TZ = "Asia/Kolkata";

export default defineConfig({
  test: { globals: true, environment: "jsdom", include: ["tests/**/*.test.{ts,tsx}"], css: false },
});
