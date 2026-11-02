import { parse } from "yaml";
import { WidgetRegistry, type DashboardWidget } from "@eos/ui-kit";
import enabledRaw from "../config/modules.enabled.yaml?raw";

/** One registry for the whole app. Filled once at startup. */
export const registry = new WidgetRegistry();

interface Enabled {
  modules?: string[];
  platform?: string[];
  integrations?: string[];
}

/** Every module widgets entry point in the repo, keyed by path. Loaded lazily. */
const widgetModules = import.meta.glob<{ widgets?: DashboardWidget[] }>(
  "../../../modules/*/*/frontend/src/widgets/index.ts",
);

/** Platform services' widgets (billing, tenancy, identity, audit, ...), listed under `platform:`. */
const platformModules = import.meta.glob<{ widgets?: DashboardWidget[] }>(
  "../../../platform/*/frontend/src/widgets/index.ts",
);

/** Integrations' widgets (payment-sbiepay, digilocker, ...), listed under `integrations:`. */
const integrationModules = import.meta.glob<{ widgets?: DashboardWidget[] }>(
  "../../../integrations/*/frontend/src/widgets/index.ts",
);

let registering: Promise<string[]> | undefined;

/**
 * Register the widgets of every module listed in config/modules.enabled.yaml.
 * `modules:` entries are `<domain>/<module>` paths relative to modules/, e.g. `academics/lms`;
 * `platform:` entries are service names under platform/, e.g. `billing`, returned as `platform/billing`;
 * `integrations:` entries are adapter names under integrations/, e.g. `payment-sbiepay`, returned as
 * `integrations/payment-sbiepay`.
 * Runs once: later calls (React StrictMode runs effects twice in development) get the same result
 * instead of registering every widget again. A failed run is retried by the next call.
 */
export function registerEnabledModules(): Promise<string[]> {
  registering ??= registerOnce().catch((e: unknown) => {
    registering = undefined;
    throw e;
  });
  return registering;
}

async function registerOnce(): Promise<string[]> {
  const enabled = (parse(enabledRaw) as Enabled | null) ?? {};
  const loaded: string[] = [];
  const entries: Array<[string, string, (() => Promise<{ widgets?: DashboardWidget[] }>) | undefined]> = [
    ...(enabled.modules ?? []).map((name): [string, string, (() => Promise<{ widgets?: DashboardWidget[] }>) | undefined] => [
      name,
      name,
      widgetModules[`../../../modules/${name}/frontend/src/widgets/index.ts`],
    ]),
    ...(enabled.platform ?? []).map((name): [string, string, (() => Promise<{ widgets?: DashboardWidget[] }>) | undefined] => [
      name,
      `platform/${name}`,
      platformModules[`../../../platform/${name}/frontend/src/widgets/index.ts`],
    ]),
    ...(enabled.integrations ?? []).map((name): [string, string, (() => Promise<{ widgets?: DashboardWidget[] }>) | undefined] => [
      name,
      `integrations/${name}`,
      integrationModules[`../../../integrations/${name}/frontend/src/widgets/index.ts`],
    ]),
  ];
  for (const [name, label, load] of entries) {
    if (!load) {
      console.warn(`modules.enabled.yaml lists "${name}" but it has no frontend/src/widgets/index.ts`);
      continue;
    }
    const mod = await load();
    registry.register(mod.widgets ?? []);
    loaded.push(label);
  }
  return loaded;
}
