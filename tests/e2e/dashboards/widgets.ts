import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { SUPER_ADMIN } from "../stack";
import { login, type DashboardUser } from "./organisation";

/**
 * Shared by the dashboard journeys that walk a whole role layout (management, research-*): what each widget of
 * the layout shows for a new organisation, found the way the shell renders it (a panel with the registered title).
 * Permission-based hiding is not covered: apps/frontend/src/App.tsx passes permissions="all" to the dashboard for
 * now, so a widget whose API refuses the role renders with the module's "no access" wording instead of hiding.
 */

/** A widget of a role layout and what its panel shows for a new organisation. */
export interface LayoutWidget {
  /** `<module>.<widget>`, as the layout lists it. */
  id: string;
  /** `<domain>/<module>` under modules/ (or `platform/<service>`, `integrations/<adapter>`), as modules.enabled.yaml lists it. */
  module: string;
  /** The sprint batch (GitHub issue) that builds or built the module, for the skip message while it is missing. */
  batch: string;
  /** The widget's registered title, once the module exports it. */
  title?: string;
  /** The GET the widget's body makes, under /api/v1, to learn before opening the page what it will show. */
  probe?: string;
  /** The empty-state title for a new organisation (the probe answers 200). */
  empty?: string;
  /** The wording when the backend is not mounted (the probe answers 404). */
  unavailable?: string;
  /** The wording when the API refuses the role (the probe answers 403). */
  forbidden?: string;
}

export const repo = (path: string) => readFileSync(new URL(`../../../${path}`, import.meta.url), "utf8");

/** The list a module is named in by kind: `platform/<service>` → platform, `integrations/<adapter>` → integrations. */
const listOf = (module: string) => ["platform", "integrations"].find((kind) => module.startsWith(`${kind}/`));

/** Whether apps/frontend registers a module's widgets (a listed, uncommented entry of modules.enabled.yaml). */
export function enabled(module: string): boolean {
  const kind = listOf(module);
  const entry = kind ? module.slice(`${kind}/`.length) : module;
  return repo("apps/frontend/config/modules.enabled.yaml")
    .split("\n")
    .some((line) => line.replace(/#.*/, "").trim() === `- ${entry}`);
}

/**
 * Whether apps/backend mounts a module's API (a listed, uncommented entry of modules.enabled.yaml: `modules` takes
 * `<domain>/<module>`, `platform` and `integrations` take the name, which may be listed inline as `platform: [a, b]`).
 */
export function backendEnabled(module: string): boolean {
  const text = repo("apps/backend/config/modules.enabled.yaml").split("\n").map((line) => line.replace(/#.*/, "").trim());
  const kind = listOf(module);
  if (kind) {
    const service = module.slice(`${kind}/`.length);
    const inline = text.find((line) => line.startsWith(`${kind}:`));
    const names = (inline?.match(/\[(.*)\]/)?.[1] ?? "").split(",").map((n) => n.trim());
    return names.includes(service) || text.includes(`- ${service}`);
  }
  return text.includes(`- ${module}`);
}

/** Whether the module's widgets entry point exports the widget id. */
export function exported(w: LayoutWidget): boolean {
  const dir = listOf(w.module) ? w.module : `modules/${w.module}`;
  try {
    return repo(`${dir}/frontend/src/widgets/index.ts`).includes(`"${w.id}"`);
  } catch {
    return false;
  }
}

/** A widget is on the dashboard once its module is enabled and the module exports it. */
export const shipped = (w: LayoutWidget) => enabled(w.module) && exported(w);

/** Why a widget is not on the dashboard yet, for the skip message. */
export function waitingFor(w: LayoutWidget): string {
  if (!enabled(w.module)) return `${w.module} is not in apps/frontend/config/modules.enabled.yaml yet (sprint batch ${w.batch})`;
  return `${w.module} is enabled but does not export ${w.id} yet (sprint batch ${w.batch})`;
}

export async function signIn(page: Page, user: DashboardUser) {
  await page.goto("/app"); // the dashboard app lives at /app; / is the public site
  // exact: the organisation field's hint also says "email"
  await page.getByLabel("Email", { exact: true }).fill(user.email);
  await page.getByLabel("Password", { exact: true }).fill(user.password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** The panel a widget renders in, found by its heading. */
export const widget = (page: Page, title: string) =>
  page.locator(".eos-widget").filter({ has: page.getByRole("heading", { name: title, exact: true }) });

/**
 * Move the organisation to the Standard plan as the super admin: finance-operations, campus-life and governance
 * are not in the Trial plan (platform/billing/config/plans.yaml), and the shell hides (or locks) widgets of
 * modules outside the entitlement while the entitlement gate refuses their requests.
 */
export async function standardPlan(request: APIRequestContext, organisationId: string) {
  const token = await login(request, SUPER_ADMIN.email, SUPER_ADMIN.password);
  const plan = await request.put(`/api/v1/billing/admin/subscriptions/${organisationId}`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { plan: "standard", reason: "e2e: the role's modules are not in the trial plan" },
  });
  expect(plan.ok(), await plan.text()).toBeTruthy();
}

/**
 * The status the widget's own GET gets for this user; what the panel shows follows from it. A module the backend
 * enables must answer 200: a 404 (not mounted) or 403 (role catalogue regression) there fails the journey instead of
 * passing as "not available yet". Only a module absent from apps/backend/config/modules.enabled.yaml may answer otherwise.
 */
export async function probe(request: APIRequestContext, user: DashboardUser, w: LayoutWidget): Promise<number> {
  const r = await request.get(`/api/v1${w.probe}`, { headers: { Authorization: `Bearer ${user.token}` } });
  if (backendEnabled(w.module)) {
    expect(r.status(), `${w.id}: ${w.module} is enabled in apps/backend/config/modules.enabled.yaml, so ${w.probe} must answer 200 (got ${r.status()} ${await r.text()})`).toBe(200);
  }
  return r.status();
}

/** The panel's body for a new organisation, given what the probe answered. */
export async function expectBody(page: Page, w: LayoutWidget, status: number) {
  const panel = widget(page, w.title!);
  if (backendEnabled(w.module)) {
    // enabled in the backend: data or the empty state, never the "not available yet" or "no access" wording
    expect(status, `${w.id}: ${w.module} is enabled in the backend, its probe must answer 200`).toBe(200);
    await expect(panel.getByText(w.empty!, { exact: true })).toBeVisible();
    return;
  }
  if (status === 200) await expect(panel.getByText(w.empty!, { exact: true })).toBeVisible();
  else if (status === 403) await expect(panel.getByText(w.forbidden ?? "You do not have access to this.", { exact: true })).toBeVisible();
  else await expect(panel.getByText(w.unavailable!, { exact: true })).toBeVisible();
}

async function ok<T>(response: Awaited<ReturnType<APIRequestContext["post"]>>): Promise<T> {
  expect(response.ok(), `${response.url()} → ${response.status()} ${await response.text()}`).toBeTruthy();
  return (await response.json()) as T;
}

/** POST under /api/v1 as `user` and return the created record. */
export async function created<T>(request: APIRequestContext, user: DashboardUser, path: string, data: unknown): Promise<T> {
  return ok<T>(await request.post(`/api/v1${path}`, { headers: { Authorization: `Bearer ${user.token}` }, data }));
}

/** A contract date (YYYY-MM-DD) some days from today. */
export const dayFromNow = (days: number) => new Date(Date.now() + days * 86_400_000).toISOString().slice(0, 10);
