import { describe, expect, it } from "vitest";
import { registerEnabledModules, registry } from "../src/modules";

// React StrictMode runs effects twice in development, so App.tsx calls registerEnabledModules() twice on
// start-up. Every enabled module's widgets must still be registered exactly once, without an error.
describe("registerEnabledModules", () => {
  it("registers each enabled module once, however often it is called", async () => {
    const [first, second] = await Promise.all([registerEnabledModules(), registerEnabledModules()]);
    const third = await registerEnabledModules();

    expect(first.length).toBeGreaterThan(0); // modules.enabled.yaml lists at least one module
    expect(second).toEqual(first);
    expect(third).toEqual(first);
    for (const id of ["hostel.notices"]) expect(registry.get(id)).toBeDefined();
  });

  it("reads the platform: list the same way as modules:, naming them platform/<service>", async () => {
    const loaded = await registerEnabledModules();
    const yaml = (await import("../config/modules.enabled.yaml?raw")).default as string;
    const platform = yaml
      .split("\n")
      .filter((line) => !/^\s*#/.test(line))
      .join("\n")
      .match(/^platform:\s*\[([^\]]*)\]/m)?.[1]
      ?.split(",")
      .map((s) => s.trim())
      .filter(Boolean) ?? [];
    for (const name of platform) expect(loaded).toContain(`platform/${name}`);
    for (const name of loaded.filter((n) => n.startsWith("platform/"))) expect(platform).toContain(name.slice("platform/".length));
  });
});
