import { expect, test, type Page } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, dayFromNow, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Management Student dashboard (layout platform/identity/config/dashboards/management-student.yaml, which extends
 * the Student layout; the role exists in the management-institute profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a management student signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Student ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml: the panel renders by its registered title and shows its empty
 *   state, or says its data is not available while the backend is missing (the management student holds the
 *   student role's permissions through `extends`);
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it
 *   (timetable-attendance and examinations' upcoming-assessments #325, lms #326, transport and library #338,
 *   productions #318, projects and field-training #339, placement-career and alumni #337). examinations is enabled
 *   but does not export examinations.upcoming-assessments yet, so that widget skips too;
 * - data journeys, each once its widget has shipped and its API answers the management-student role:
 *   an invoice finance staff raise to the student shows in fees-accounts.fee-dues; a notice a warden publishes to
 *   every hostel shows in hostel.notices. The other widgets' journeys are fixme until their module ships.
 *
 * finance-operations and campus-life are not in the Trial plan (platform/billing/config/plans.yaml), so the super
 * admin moves the organisation to Standard first. The empty-state tests run before any data is created (serial
 * mode). Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Management Student";

const WIDGETS: LayoutWidget[] = [
  // Inherited from the Student layout (extends: student).
  { id: "timetable-attendance.today", module: "academics/timetable-attendance", batch: "#325" },
  { id: "timetable-attendance.attendance-summary", module: "academics/timetable-attendance", batch: "#325" },
  { id: "examinations.upcoming-assessments", module: "academics/examinations", batch: "#325" },
  // The management-student layout lists lms.course-materials again; the shell shows it once (resolveWidgetIds).
  { id: "lms.course-materials", module: "academics/lms", batch: "#326" },
  {
    id: "fees-accounts.fee-dues",
    module: "finance-operations/fees-accounts",
    batch: "#107",
    title: "Fee dues",
    probe: "/fees-accounts/me/dues",
    empty: "No fees due",
    unavailable: "Fee data is not available yet.",
  },
  {
    id: "hostel.notices",
    module: "campus-life/hostel",
    batch: "#338",
    title: "Hostel notices",
    probe: "/hostel/me/notices?limit=1",
    empty: "No hostel notices right now",
    unavailable: "Could not load hostel notices",
    forbidden: "Could not load hostel notices",
  },
  {
    // Texts of NoticesWidget.tsx in PR #473 (sprint batch #338).
    id: "transport.notices",
    module: "campus-life/transport",
    batch: "#338",
    title: "Transport notices",
    probe: "/transport/me/notices?limit=1",
    empty: "No transport notices right now",
    unavailable: "Transport data is not available yet.",
  },
  {
    // Texts of LoansWidget.tsx in PR #476 (sprint batch #338).
    id: "library.loans",
    module: "campus-life/library",
    batch: "#338",
    title: "Library loans",
    probe: "/library/me/loans",
    empty: "No books on loan",
    unavailable: "Library data is not available yet.",
  },
  // The management student's own widgets.
  { id: "productions.upcoming", module: "practice/productions", batch: "#318" },
  { id: "projects.my-projects", module: "practice/projects", batch: "#339" },
  { id: "field-training.my-placement", module: "practice/field-training", batch: "#339" },
  // The learner view of openings (#424 keeps this id for learners and adds openings-summary for staff).
  {
    id: "placement-career.openings",
    module: "campus-life/placement-career",
    batch: "#337",
    title: "Job openings",
    probe: "/placement-career/me/openings?limit=1",
    empty: "No openings right now",
    unavailable: "Placement data is not available yet.",
    forbidden: "You do not have access to this.",
  },
  { id: "alumni.mentoring", module: "campus-life/alumni", batch: "#337" },
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let admin: DashboardUser;
let user: DashboardUser;
/** Finance staff: they raise the fee demand the student sees. */
let financeStaff: DashboardUser;
/** A hostel warden: they publish the notice the student sees. */
let warden: DashboardUser;
/** Per shipped widget id: what its GET answered the management student. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

/** A contract date as fees-accounts' format.ts shows it ("5 Nov 2026"), formatted by the browser the same way. */
const shown = (page: Page, date: string) =>
  page.evaluate((d) => new Date(`${d}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }), date);

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "management-institute" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "management-student");
  financeStaff = await addUser(request, admin, "finance-staff");
  warden = await addUser(request, admin, "hostel-warden");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a management student signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("management-student widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the management-student layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the management-student layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

test.describe("with fees-accounts data", () => {
  test("fees-accounts.fee-dues shows the invoice finance staff raise to the management student", async ({ page, request }) => {
    const w = byId("fees-accounts.fee-dues");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the fees-accounts API answered ${status[w.id]} to the management-student role`);
    // finance-staff holds fees-accounts:fee-structure:manage and invoice:create, as in finance-staff.spec.ts. An ad hoc
    // invoice to the student (person_id is the user's id; GET /me/dues reads the caller's own invoices) takes the fee
    // head's name as its title. Due in 30 days by the server's UTC date, which dayFromNow also is, so nothing is overdue.
    const head = await created<{ id: string }>(request, financeStaff, "/fees-accounts/fee-heads", {
      code: "TUITION",
      name: "Tuition fee",
      category: "tuition",
    });
    const dueOn = dayFromNow(30);
    const invoice = await created<{ id: string; number: string }>(request, financeStaff, "/fees-accounts/invoices", {
      person_id: user.id,
      lines: [{ fee_head_id: head.id, amount: "45000.00" }],
      due_date: dueOn,
    });
    await signIn(page, user);

    const panel = widget(page, "Fee dues");
    await expect(panel.getByText("No fees due")).toHaveCount(0);
    const summary = panel.locator("dl > div");
    await expect(summary.filter({ hasText: "Total due" })).toHaveText("Total due₹45,000.00");
    await expect(summary.filter({ hasText: "Overdue" })).toHaveText("OverdueNothing overdue");
    const due = await shown(page, dueOn);
    await expect(summary.filter({ hasText: "Next due" })).toHaveText(`Next due${due}`);
    const row = panel.getByRole("list", { name: "Fees due" }).getByRole("listitem").filter({ hasText: "Tuition fee" });
    await expect(row).toContainText(`${invoice.number} · Due ${due}`);
    await expect(row).toContainText("₹45,000.00");
    await expect(row.getByText("Overdue", { exact: true })).toHaveCount(0);
  });
});

test.describe("with hostel data", () => {
  test("hostel.notices shows a notice a warden publishes to every hostel", async ({ page, request }) => {
    const w = byId("hostel.notices");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the hostel API answered ${status[w.id]} to the management-student role`);
    // hostel-warden holds hostel:notice:publish. A notice without hostel_id goes to every hostel, and a resident
    // without an allocation sees exactly those (notice_visible_to in hostel's domain/rules.py), so the student needs
    // no room for this.
    await created(request, warden, "/hostel/notices", {
      title: "Mess timings during placement week",
      body: "Breakfast opens at 6:30 so you can reach the interview hall by 8.",
    });
    await signIn(page, user);

    const panel = widget(page, "Hostel notices");
    await expect(panel.getByText("No hostel notices right now")).toHaveCount(0);
    const row = panel.getByRole("list", { name: "Hostel notices" }).getByRole("listitem").filter({ hasText: "Mess timings during placement week" });
    await expect(row).toContainText("Breakfast opens at 6:30 so you can reach the interview hall by 8.");
    await expect(row.getByText("All hostels", { exact: true })).toBeVisible();
  });
});

// Backend-dependent: these need their module's API to create the data through, so nothing here is faked.
test.fixme("productions.upcoming lists the case competitions and industry events the student takes part in", async () => {
  // practice/productions (sprint batch #318); the management-institute vocabulary calls a production a
  // "Case competition / industry event". Not in apps/frontend or apps/backend modules.enabled.yaml yet.
});

test.fixme("projects.my-projects shows the student's live project", async () => {
  // practice/projects (sprint batch #339); vocabulary: "Live project". The layout grants projects-member.
});

test.fixme("field-training.my-placement shows the student's internship", async () => {
  // practice/field-training (sprint batch #339); vocabulary: "Internship". The layout grants field-training-trainee.
});

test.fixme("placement-career.openings lists the openings the student may apply to", async () => {
  // campus-life/placement-career (sprint batch #337); contract on contract/placement-career/v1 (PR #424).
});

test.fixme("alumni.mentoring shows the student's alumni mentor", async () => {
  // campus-life/alumni (sprint batch #337); contract on contract/alumni/v1 (PR #422), which grants alumni-mentee.
});

test.fixme("lms.course-materials lists the materials of the student's courses", async () => {
  // academics/lms (sprint batch #326).
});
