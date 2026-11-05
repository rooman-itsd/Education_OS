import { defineConfig } from "vitest/config";

// The viewer's zone is set far from India so the tests prove dates and times are shown in Asia/Kolkata regardless.
process.env.TZ = "America/New_York";

export default defineConfig({
  test: { globals: true, environment: "jsdom", include: ["tests/**/*.test.{ts,tsx}"], css: false },
});
