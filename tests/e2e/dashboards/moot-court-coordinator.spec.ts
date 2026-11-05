import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Moot Court Coordinator dashboard (layout platform/identity/config/dashboards/moot-court-coordinator.yaml; the role
 * exists in the law-college profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a moot court coordinator signs in and lands on their dashboard;
 * - for every widget of the layout whose module is in apps/frontend/config/modules.enabled.yaml: the panel renders
 *   by its registered title and shows its empty state;
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it
 *   (productions #318, field-training #339);
 * - data journey: a moot court round the coordinator sets up and opens through the API (a process type, then a
 *   process with one stage) shows in `selection-process.open-calls`. The coordinator holds
 *   selection-process-coordinator through the layout's module_roles.
 *
 * The organisation is moved to Standard first, as in the other academy journeys. The empty-state tests run before
 * any data is created (serial mode). Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Moot Court Coordinator";

const WIDGETS: LayoutWidget[] = [
  {
    id: "selection-process.open-calls",
    module: "practice/selection-process",
    batch: "#322",
    title: "Open Calls",
    probe: "/selection-process/processes?status=open&page_size=6",
    empty: "No open calls right now",
    unavailable: "Open calls are not available yet.",
  },
  {
    id: "productions.calendar",
    module: "practice/productions",
    batch: "#318",
    title: "Production calendar",
    probe: "/productions/calendar",
    empty: "Nothing scheduled",
    unavailable: "Production data is not available yet.",
  },
  {
    id: "productions.upcoming",
    module: "practice/productions",
    batch: "#318",
    title: "Upcoming productions",
    probe: "/productions/upcoming",
    empty: "Nothing coming up",
    unavailable: "Production data is not available yet.",
  },
  { id: "field-training.placements-open", module: "practice/field-training", batch: "#339" },
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the moot court coordinator. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "law-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "moot-court-coordinator");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a moot court coordinator signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("moot-court-coordinator widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the moot-court-coordinator layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the moot-court-coordinator layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    for (const w of SHIPPED) await expectBody(page, w, status[w.id] ?? 0);
  });

  for (const w of WIDGETS.filter((w) => !shipped(w))) {
    test(`${w.id} renders once ${w.module} ships`, async ({ page }) => {
      test.skip(!shipped(w), waitingFor(w));
      // The shell renders an unregistered id as a "Not built yet" placeholder titled with the id itself.
      await signIn(page, user);
      await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
      await expect(widget(page, w.id)).toHaveCount(0);
    });
  }
});

test.describe("with selection-process data", () => {
  test("selection-process.open-calls lists a moot court round the coordinator opens", async ({ page, request }) => {
    const w = byId("selection-process.open-calls");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the selection-process API answered ${status[w.id]} to the moot-court-coordinator role`);
    // The coordinator names the kind of selection in the organisation's own words, creates a round with one stage
    // and opens it for registration.
    const type = await created<{ id: string }>(request, user, "/selection-process/process-types", { name: "Moot court panel" });
    const round = await created<{ id: string }>(request, user, "/selection-process/processes", {
      type_id: type.id,
      title: "Inter-college moot court 2026",
      stages: [{ name: "Memorial submission", sequence: 1 }],
    });
    await created(request, user, `/selection-process/processes/${round.id}/open`, {});
    await signIn(page, user);

    const panel = widget(page, "Open Calls");
    await expect(panel.getByText("No open calls right now")).toHaveCount(0);
    const row = panel.getByRole("list", { name: "Open selection calls" }).getByRole("listitem").filter({ hasText: "Inter-college moot court 2026" });
    await expect(row).toContainText("1 stage");
    await expect(row).toContainText("Open");
  });
});
