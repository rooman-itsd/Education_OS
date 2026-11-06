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
 *   every hostel shows in hostel.notices; an opening the placement officer publishes shows in
 *   placement-career.openings; an alumni mentor the placement officer (alumni-coordinator) assigns to the student,
 *   with a session scheduled for tomorrow, shows in alumni.mentoring. The other widgets' journeys are fixme until
 *   their module ships.
 *
 * finance-operations and campus-life are not in the Trial plan (platform/billing/config/plans.yaml), so the super
 * admin moves the organisation to Standard first. The empty-state tests run before any data is created (serial
 * mode). Loading states are covered by the modules' unit tests, not here.
 *
 * placement-career and alumni take "today" as the date in Asia/Kolkata (their READMEs), so the dates sent for them are
 * Indian dates and their journeys skip in the few minutes before Indian midnight, when the server's day could turn
 * mid-test.
 */

const TITLE = "Management Student";

const WIDGETS: LayoutWidget[] = [
  // Inherited from the Student layout (extends: student).
  { id: "timetable-attendance.today", module: "academics/timetable-attendance", batch: "#325" },
  { id: "timetable-attendance.attendance-summary", module: "academics/timetable-attendance", batch: "#325" },
  { id: "examinations.upcoming-assessments", module: "academics/examinations", batch: "#325" },
  // The management-student layout lists lms.course-materials again; the shell shows it once (resolveWidgetIds).
  {
    id: "lms.course-materials",
    module: "academics/lms",
    batch: "#326",
    title: "Course materials",
    probe: "/lms/me/course-materials?limit=1",
    empty: "No new course materials",
    unavailable: "Course data is not available yet.",
  },

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
  {
    id: "productions.upcoming",
    module: "practice/productions",
    batch: "#318",
    title: "Upcoming productions",
    probe: "/productions/upcoming",
    empty: "Nothing coming up",
    unavailable: "Production data is not available yet.",
  },
  {
    id: "projects.my-projects",
    module: "practice/projects",
    batch: "#339",
    title: "My projects",
    probe: "/projects/me/projects",
    empty: "You are not on a project yet",
    unavailable: "Projects data is not available yet.",
  },
  {
    id: "field-training.my-placement",
    module: "practice/field-training",
    batch: "#339",
    title: "My placement",
    probe: "/field-training/me/placements",
    empty: "No placement yet",
    unavailable: "Field training data is not available yet.",
  },
  // The learner view of openings (#424 keeps this id for learners and adds openings-summary for staff).
  { id: "placement-career.openings", module: "campus-life/placement-career", batch: "#337" },
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
/** The placement officer: they publish the opening and, as alumni-coordinator, assign the mentor the student sees. */
let officer: DashboardUser;
/** Per shipped widget id: what its GET answered the management student. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

/** A contract date as fees-accounts' format.ts shows it ("5 Nov 2026"), formatted by the browser the same way. */
const shown = (page: Page, date: string) =>
  page.evaluate((d) => new Date(`${d}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }), date);

const IST = 5.5 * 3_600_000; // Asia/Kolkata is UTC+05:30 all year (no daylight saving)
/** The Indian date (YYYY-MM-DD) some days from today, as placement-career's and alumni's business dates are. */
const indianDay = (days = 0) => new Date(Date.now() + IST + days * 86_400_000).toISOString().slice(0, 10);
/** Minutes left until midnight in India. */
const minutesToIndianMidnight = () => 1440 - Math.floor(((Date.now() + IST) % 86_400_000) / 60_000);
const NEAR_MIDNIGHT = "within 15 minutes of midnight in Asia/Kolkata, the module's business day could turn mid-test";

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "management-institute" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "management-student");
  financeStaff = await addUser(request, admin, "finance-staff");
  warden = await addUser(request, admin, "hostel-warden");
  officer = await addUser(request, admin, "placement-officer");
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

test.describe("with placement-career data", () => {
  test("placement-career.openings lists an opening the placement officer publishes", async ({ page, request }) => {
    const w = byId("placement-career.openings");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the placement-career API answered ${status[w.id]} to the management-student role`);
    test.skip(minutesToIndianMidnight() < 15, NEAR_MIDNIGHT);
    // placement-officer holds placement-career-officer through its layout's module_roles: it records a company and
    // publishes an opening outside a drive, taking applications for 7 more days. GET /me/openings lists every open
    // opening still taking applications to the student (the `student` role the layout extends).
    const company = await created<{ id: string }>(request, officer, "/placement-career/companies", { name: "Contoso Capital", industry: "Banking" });
    const closesOn = indianDay(7);
    const opening = await created<{ id: string }>(request, officer, "/placement-career/openings", {
      company_id: company.id,
      title: "Management Trainee",
      location: "Mumbai",
      ctc_per_annum: "1200000",
      applications_close_on: closesOn,
    });
    await created(request, officer, `/placement-career/openings/${opening.id}/publish`, {});
    await signIn(page, user);

    const panel = widget(page, "Job openings");
    await expect(panel.getByText("No openings right now")).toHaveCount(0);
    const row = panel.getByRole("list", { name: "Job openings" }).getByRole("listitem").filter({ hasText: "Management Trainee" });
    await expect(row).toContainText("Contoso Capital, Mumbai");
    await expect(row).toContainText("CTC ₹12,00,000 a year");
    // placement-career's format.ts reads a contract date as midnight in India and shows it in Asia/Kolkata.
    const closes = await page.evaluate(
      (d) => new Date(`${d}T00:00:00+05:30`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" }),
      closesOn,
    );
    await expect(row).toContainText(`Apply by ${closes}`);
    await expect(row).not.toContainText("Campus drive on");
  });
});

test.describe("with alumni data", () => {
  test("alumni.mentoring shows the mentor the placement officer assigns and the session they schedule", async ({ page, request }) => {
    const w = byId("alumni.mentoring");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the alumni API answered ${status[w.id]} to the management-student role`);
    test.skip(minutesToIndianMidnight() < 15, NEAR_MIDNIGHT);
    // placement-officer holds alumni-coordinator through its layout's module_roles: it adds an alumnus flagged as a
    // mentor, assigns them to the student (student_id is the student's user id; GET /me/mentoring reads the caller's
    // own assignment; started_on defaults to today in India) and schedules a session for tomorrow at 10:30 in India.
    const mentor = await created<{ id: string }>(request, officer, "/alumni/directory", {
      full_name: "Priya Raman",
      graduation_year: 2016,
      programme: "MBA",
      current_company: "Fabrikam Consulting",
      current_designation: "Engagement Manager",
      industry: "Consulting",
      city: "Bengaluru",
      email: "priya.raman@example.com",
      is_mentor: true,
    });
    const assignment = await created<{ id: string; started_on: string }>(request, officer, "/alumni/mentoring/assignments", {
      mentor_id: mentor.id,
      student_id: user.id,
      student_name: "E2E management-student",
      focus: "Consulting careers",
    });
    const scheduledAt = new Date(`${indianDay(1)}T10:30:00+05:30`).toISOString();
    await created(request, officer, `/alumni/mentoring/assignments/${assignment.id}/sessions`, {
      scheduled_at: scheduledAt,
      duration_minutes: 45,
      mode: "online",
      topic: "Case interview practice",
    });
    await signIn(page, user);

    const panel = widget(page, "My mentor");
    await expect(panel.getByText("No mentor assigned yet")).toHaveCount(0);
    const mentorCard = panel.getByRole("region", { name: "Your mentor" });
    await expect(mentorCard.getByRole("heading", { name: "Priya Raman" })).toBeVisible();
    await expect(mentorCard).toContainText("Engagement Manager, Fabrikam Consulting");
    await expect(mentorCard).toContainText("Class of 2016 · MBA · Consulting · Bengaluru");
    const facts = mentorCard.locator("dl.eos-alumni__facts > div");
    await expect(facts.filter({ hasText: "Focus" })).toHaveText("FocusConsulting careers");
    // alumni's format.ts shows started_on (already an Indian date) as that day in the browser's own calendar.
    const since = await page.evaluate(
      (d) => new Date(`${d}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }),
      assignment.started_on,
    );
    await expect(facts.filter({ hasText: "Mentoring since" })).toHaveText(`Mentoring since${since}`);
    await expect(mentorCard.getByRole("link", { name: "priya.raman@example.com" })).toBeVisible();

    // The session's time in India, assembled from parts as alumni's indianDateTime does ("Sat, 7 Nov 2026, 10:30 am").
    const when = await page.evaluate((iso) => {
      const parts = new Intl.DateTimeFormat("en-IN", {
        timeZone: "Asia/Kolkata",
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
      }).formatToParts(new Date(iso));
      const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
      return `${get("weekday")}, ${get("day")} ${get("month")} ${get("year")}, ${get("hour")}:${get("minute")} ${get("dayPeriod").toLowerCase()}`;
    }, scheduledAt);
    const session = panel.getByRole("list", { name: "Upcoming mentoring sessions" }).getByRole("listitem").filter({ hasText: "Case interview practice" });
    await expect(session).toContainText(when);
    await expect(session).toContainText("Online");
    await expect(session).toContainText("45 min");
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

test.fixme("lms.course-materials lists the materials of the student's courses", async () => {
  // academics/lms (sprint batch #326).
});
