import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { organisationWithUser, type DashboardUser } from "./organisation";

/**
 * Examination Staff dashboard (issue #5; layout platform/identity/config/dashboards/examination-staff.yaml).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: an examination-staff user signs in and lands on their dashboard;
 * - once examinations is in apps/frontend/config/modules.enabled.yaml (widgets: PR #216): the three
 *   examination widgets render;
 * - while the examinations backend is not mounted: each widget says its data is not available yet;
 * - once the examinations backend exists (Shivani) and enrolment-registration ships its widget (Praveen):
 *   the data journeys marked fixme below.
 *
 * Loading states are covered by the module's unit tests, not here. Permission-based hiding is not
 * tested: apps/frontend/src/App.tsx passes permissions="all" to the dashboard for now.
 */

const WIDGETS = [
  { id: "examinations.schedule", title: "Exam schedule" },
  { id: "examinations.hall-tickets-issued", title: "Hall tickets issued" },
  { id: "examinations.results-pending", title: "Results pending" },
] as const;

/** Whether the shell registers examinations' widgets (a listed, uncommented entry). */
const examinationsEnabled = readFileSync(new URL("../../../apps/frontend/config/modules.enabled.yaml", import.meta.url), "utf8")
  .split("\n")
  .some((line) => /^\s*-\s*academics\/examinations\s*$/.test(line.replace(/#.*/, "")));

let user: DashboardUser;
let backendLive = false;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  user = await organisationWithUser(request, { academyType: "sports-college", role: "examination-staff" });
  // The examinations API answers once its backend is mounted; until then the route does not exist.
  const probe = await request.get("/api/v1/examinations/sessions?limit=1", {
    headers: { Authorization: `Bearer ${user.token}` },
  });
  backendLive = probe.status() !== 404;
});

async function signIn(page: Page) {
  await page.goto("/app"); // the dashboard app lives at /app; / is the public site
  // exact: the organisation field's hint also says "email"
  await page.getByLabel("Email", { exact: true }).fill(user.email);
  await page.getByLabel("Password", { exact: true }).fill(user.password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** The panel a widget renders in, found by its heading. */
const widget = (page: Page, title: string) =>
  page.locator(".eos-widget").filter({ has: page.getByRole("heading", { name: title, exact: true }) });

test("an examination staff member signs in and lands on the Examination Staff dashboard", async ({ page }) => {
  await signIn(page);
  await expect(page.getByRole("region", { name: "Examination Staff dashboard" })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · Examination Staff dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("examination widgets", () => {
  test.skip(!examinationsEnabled, "examinations is not in apps/frontend/config/modules.enabled.yaml yet (widgets: PR #216)");

  test("the three examination widgets render", async ({ page }) => {
    await signIn(page);
    const dashboard = page.getByRole("region", { name: "Examination Staff dashboard" });
    for (const w of WIDGETS) await expect(dashboard.getByRole("heading", { name: w.title, exact: true })).toBeVisible();
  });

  test("each widget says its data is not available while the examinations backend is missing", async ({ page }) => {
    test.skip(backendLive, "the examinations backend is live; the data journeys below apply instead");
    await signIn(page);
    for (const w of WIDGETS) {
      // The UI kit's ErrorState: the message, and a retry because the service may come back.
      const alert = widget(page, w.title).getByRole("alert");
      await expect(alert).toContainText("Examinations data is not available yet.");
      await expect(alert.getByRole("button", { name: "Try again" })).toBeVisible();
    }
  });
});

// Backend-dependent: these need the examinations API (Shivani) to create the data through, so nothing
// here is faked. Each lists what to create and what the widget must then show.
test.describe("with examinations data", () => {
  test.fixme("examinations.schedule lists the upcoming sessions", async () => {
    // Create an exam cycle, a paper for a course offering and a scheduled session tomorrow
    // (POST /exam-cycles, /papers, /sessions) with venue, candidates and fewer invigilators than required.
    // Expect: the session's date and time, "<course code> · <course title>", the venue, the candidate count,
    // and the invigilator count marked short (e.g. "3/4 · short").
  });

  test.fixme("examinations.schedule says there are no upcoming sessions", async () => {
    // With no scheduled sessions from today on, expect "No upcoming exam sessions."
  });

  test.fixme("examinations.hall-tickets-issued shows the counts for the active cycle", async () => {
    // Run eligibility and issue hall tickets for a scheduled cycle, then withhold one with a reason
    // (POST /exam-cycles/{id}/eligibility-runs, /exam-cycles/{id}/hall-tickets, /hall-tickets/{id}/withhold).
    // Expect: eligible, issued, not issued, withheld and revoked counts, and the withheld reason with its count.
  });

  test.fixme("examinations.results-pending shows papers by stage", async () => {
    // Move a cycle to evaluation with papers in marks entry and moderation.
    // Expect: the six stages in order, counts on marks entry and moderation, "none" on the rest.
  });
});

test.fixme("enrolment-registration.registered-candidates shows registered candidates", async () => {
  // Owned by enrolment-registration (Praveen); the widget does not exist yet. Write this journey with it.
});
