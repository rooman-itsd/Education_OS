import { expect, test, type Page } from "@playwright/test";
import { organisationWithUser, type DashboardUser } from "./organisation";
import { created, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Placement Officer dashboard (layout platform/identity/config/dashboards/placement-officer.yaml; the role exists in
 * the management-institute profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a placement officer signs in and lands on their dashboard;
 * - for every widget whose module is in apps/frontend/config/modules.enabled.yaml: the panel renders by its
 *   registered title and shows its empty state, or says its data is not available while the backend is missing;
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it
 *   (field-training #339, placement-career #337, productions #318). None of them is built yet, so each widget's
 *   title, probe and wording are filled in once its module exports it;
 * - data journey, once both placement-career widgets have shipped and the API answers the placement officer: a
 *   company, a drive scheduled within 30 days and an opening in it that the officer records and publishes show in
 *   placement-career.openings-summary and placement-career.drives. The other widgets' journeys are fixme until their
 *   module ships.
 *
 * placement-career (campus-life) is not in the Trial plan (platform/billing/config/plans.yaml), so the super admin
 * moves the organisation to Standard first. The empty-state tests run before any data is created (serial mode).
 * Loading states are covered by the modules' unit tests, not here.
 *
 * placement-career takes "today" as the date in Asia/Kolkata and shows contract dates as Indian calendar dates
 * (its README), so the dates sent here are Indian dates and the data journey skips in the few minutes before Indian
 * midnight, when the server's day could turn mid-test.
 */

const TITLE = "Placement Officer";

const WIDGETS: LayoutWidget[] = [
  {
    id: "field-training.placements-open",
    module: "practice/field-training",
    batch: "#339",
    title: "Open placements",
    probe: "/field-training/openings?status=open&has_seats=true&limit=1",
    empty: "No open placements with seats",
    unavailable: "Field training data is not available yet.",
  },
  // The staff view of openings (#424 splits it from the learner widget placement-career.openings).
  {
    id: "placement-career.openings-summary",
    module: "campus-life/placement-career",
    batch: "#337",
    title: "Placement openings",
    probe: "/placement-career/reports/openings-summary?limit=1",
    empty: "No openings yet",
    unavailable: "Placement data is not available yet.",
    forbidden: "You do not have access to this.",
  },
  {
    id: "placement-career.drives",
    module: "campus-life/placement-career",
    batch: "#337",
    title: "Upcoming drives",
    probe: "/placement-career/reports/drives-upcoming?limit=1",
    empty: "No drives scheduled",
    unavailable: "Placement data is not available yet.",
    forbidden: "You do not have access to this.",
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
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the placement officer. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

const IST = 5.5 * 3_600_000; // Asia/Kolkata is UTC+05:30 all year (no daylight saving)
/** The Indian date (YYYY-MM-DD) some days from today, as placement-career's business dates are. */
const indianDay = (days = 0) => new Date(Date.now() + IST + days * 86_400_000).toISOString().slice(0, 10);
/** Minutes left until midnight in India. */
const minutesToIndianMidnight = () => 1440 - Math.floor(((Date.now() + IST) % 86_400_000) / 60_000);
const NEAR_MIDNIGHT = "within 15 minutes of midnight in Asia/Kolkata, the module's business day could turn mid-test";

/** A contract date as placement-career's format.ts shows it ("13 Nov 2026", in Asia/Kolkata), formatted by the browser. */
const shown = (page: Page, date: string) =>
  page.evaluate(
    (d) => new Date(`${d}T00:00:00+05:30`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" }),
    date,
  );

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  user = await organisationWithUser(request, { academyType: "management-institute", role: "placement-officer" });
  await standardPlan(request, user.organisation.id);
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a placement officer signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("placement-officer widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the placement-officer layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the placement-officer layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

test.describe("with placement-career data", () => {
  test("a drive and its opening the officer publishes show in upcoming drives and placement openings", async ({ page, request }) => {
    for (const id of ["placement-career.openings-summary", "placement-career.drives"]) {
      test.skip(!shipped(byId(id)), waitingFor(byId(id)));
      test.skip(!ready(id), `the placement-career API answered ${status[id]} to the placement-officer role`);
    }
    test.skip(minutesToIndianMidnight() < 15, NEAR_MIDNIGHT);
    // The layout grants placement-career-officer (company, drive and opening manage). A drive is created as a draft
    // and scheduled; an opening in it is published once the drive is scheduled and stops taking applications on or
    // before the drive date. Drive in 10 days (inside the widget's next 30 days), opening closing in 7.
    const company = await created<{ id: string }>(request, user, "/placement-career/companies", {
      name: "Northwind Analytics",
      industry: "Consulting",
    });
    const driveOn = indianDay(10);
    const registrationClosesOn = indianDay(7);
    const drive = await created<{ id: string }>(request, user, "/placement-career/drives", {
      company_id: company.id,
      title: "Northwind campus drive",
      scheduled_on: driveOn,
      venue: "Seminar Hall 2",
      registration_closes_on: registrationClosesOn,
    });
    await created(request, user, `/placement-career/drives/${drive.id}/schedule`, {});
    const closesOn = indianDay(7);
    const opening = await created<{ id: string }>(request, user, "/placement-career/openings", {
      company_id: company.id,
      drive_id: drive.id,
      title: "Business Analyst",
      location: "Bengaluru",
      ctc_per_annum: "900000",
      positions: 3,
      applications_close_on: closesOn,
    });
    await created(request, user, `/placement-career/openings/${opening.id}/publish`, {});
    await signIn(page, user);

    const summary = widget(page, "Placement openings");
    await expect(summary.getByText("No openings yet")).toHaveCount(0);
    const figures = summary.locator("dl > div");
    await expect(figures.filter({ hasText: "Open openings" })).toHaveText("Open openings1");
    await expect(figures.filter({ hasText: "Applications" })).toHaveText("Applications0");
    await expect(figures.filter({ hasText: "Students placed" })).toHaveText("Students placed0");
    const closing = summary.getByRole("list", { name: "Openings closing soonest" }).getByRole("listitem").filter({ hasText: "Business Analyst" });
    await expect(closing).toContainText("Northwind Analytics");
    await expect(closing).toContainText(`Closes ${await shown(page, closesOn)}`);
    await expect(closing).toContainText("0 applications");

    const drives = widget(page, "Upcoming drives");
    await expect(drives.getByText("No drives scheduled")).toHaveCount(0);
    await expect(drives.locator("dl > div").filter({ hasText: "Next 30 days" })).toHaveText("Next 30 days1");
    const row = drives.getByRole("list", { name: "Upcoming drives" }).getByRole("listitem").filter({ hasText: "Northwind campus drive" });
    await expect(row).toContainText("Northwind Analytics, Seminar Hall 2");
    await expect(row).toContainText(await shown(page, driveOn));
    await expect(row).toContainText(`Registration closes ${await shown(page, registrationClosesOn)}`);
    await expect(row).toContainText("1 opening");
    await expect(row).toContainText("0 applications");
  });
});

// Backend-dependent: these need their module's API to create the data through, so nothing here is faked.
test.fixme("field-training.placements-open lists the internships still looking for trainees", async () => {
  // practice/field-training (sprint batch #339); vocabulary: "Internship". The layout grants field-training-coordinator.
});

test.fixme("productions.calendar shows the case competitions and industry events in the coming weeks", async () => {
  // practice/productions (sprint batch #318); vocabulary: "Case competition / industry event".
});
