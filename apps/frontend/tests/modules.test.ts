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
});
