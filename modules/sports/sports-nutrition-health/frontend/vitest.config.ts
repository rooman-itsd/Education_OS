import { defineConfig } from "vitest/config";

export default defineConfig({
  // TZ: the appointments-today tests check a local day that spans two UTC days (India, UTC+05:30).
  test: { globals: true, environment: "jsdom", include: ["tests/**/*.test.{ts,tsx}"], css: false, env: { TZ: "Asia/Kolkata" } },
});
