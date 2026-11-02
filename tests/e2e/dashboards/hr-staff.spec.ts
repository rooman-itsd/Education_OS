import { expect, test, type Page } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * HR Staff dashboard (layout platform/identity/config/dashboards/hr-staff.yaml).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: an hr-staff user signs in and lands on their dashboard;
 * - for every widget whose module is in apps/frontend/config/modules.enabled.yaml: the panel renders by its
 *   registered title and shows its empty state, or says its data is not available while the backend is missing;
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it
 *   (hr-payroll and e-office, both #336);
 * - data journeys, each once its widget has shipped and its API answers the hr-staff role:
 *   a faculty member HR adds as an employee applies for leave, which shows in hr-payroll.leave-requests, and their
 *   joining in hr-payroll.joinings-and-exits; the month's payroll run HR starts shows in
 *   hr-payroll.payroll-run-status; a file a colleague forwards to HR shows in e-office.files-pending.
 *
 * finance-operations (hr-payroll, e-office) is not in the Trial plan, so the super admin moves the organisation to
 * Standard first. The empty-state tests run before any data is created (serial mode). Loading states are covered by
 * the modules' unit tests, not here.
 *
 * Both modules take "today" as the date in Asia/Kolkata (their READMEs), so the dates sent here are Indian dates and
 * the data journeys skip in the few minutes before Indian midnight, when the server's day could turn mid-test.
 */

const TITLE = "HR Staff";

const WIDGETS: LayoutWidget[] = [
  {
    id: "hr-payroll.leave-requests",
    module: "finance-operations/hr-payroll",
    batch: "#336",
    title: "Leave requests pending",
    probe: "/hr-payroll/leave-requests?status=pending",
    empty: "No leave requests pending",
    unavailable: "HR data is not available yet.",
  },
  {
    id: "hr-payroll.payroll-run-status",
    module: "finance-operations/hr-payroll",
    batch: "#336",
    title: "Payroll this month",
    probe: "/hr-payroll/payroll-runs/current",
    empty: "No payroll run this month",
    unavailable: "HR data is not available yet.",
    emptyCode: "not_found", // no run yet: the contract answers 404 not_found, which the widget shows as empty
  },
  {
    id: "e-office.files-pending",
    module: "finance-operations/e-office",
    batch: "#336",
    title: "Files pending with me",
    probe: "/e-office/me/inbox?limit=5",
    empty: "No files pending",
    unavailable: "File data is not available yet.",
  },
  {
    id: "hr-payroll.joinings-and-exits",
    module: "finance-operations/hr-payroll",
    batch: "#336",
    title: "Joinings and exits",
    probe: "/hr-payroll/reports/joinings-and-exits",
    empty: "No joinings or exits this month",
    unavailable: "HR data is not available yet.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let admin: DashboardUser;
let user: DashboardUser;
/** A faculty member: the employee HR adds, and the colleague who forwards a file to HR. */
let faculty: DashboardUser;
/** Per shipped widget id: what its GET answered the hr-staff user. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

/** The employee the leave journey adds, for the payroll journey after it. */
let employee: { id: string; name: string; joined_on: string } | undefined;

const IST = 5.5 * 3_600_000; // Asia/Kolkata is UTC+05:30 all year (no daylight saving)
/** The Indian date (YYYY-MM-DD) some days from today, as the modules' business dates are. */
const indianDay = (days = 0) => new Date(Date.now() + IST + days * 86_400_000).toISOString().slice(0, 10);
/** Minutes left until midnight in India. */
const minutesToIndianMidnight = () => 1440 - Math.floor(((Date.now() + IST) % 86_400_000) / 60_000);
const NEAR_MIDNIGHT = "within 15 minutes of midnight in Asia/Kolkata, the modules' business day could turn mid-test";

/** A contract date as the widgets show it ("7 Nov 2026"), formatted by the browser exactly as their format.ts does. */
const shown = (page: Page, date: string) =>
  page.evaluate((d) => new Date(`${d}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }), date);

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "management-institute" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "hr-staff");
  faculty = await addUser(request, admin, "faculty");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`an hr staff user signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("hr-staff widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the hr-staff layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the hr-staff layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

test.describe("with hr-payroll data", () => {
  test("a leave request shows in leave requests pending, and the employee's joining in joinings and exits", async ({ page, request }) => {
    for (const id of ["hr-payroll.leave-requests", "hr-payroll.joinings-and-exits"]) {
      test.skip(!shipped(byId(id)), waitingFor(byId(id)));
      test.skip(!ready(id), `the hr-payroll API answered ${status[id]} to the hr-staff role`);
    }
    test.skip(minutesToIndianMidnight() < 15, NEAR_MIDNIGHT);
    // hr-staff holds hr-payroll:leave-type:manage and employee:manage: it adds a leave type and the faculty member as
    // an employee joining today, linked to their account. Leave is applied for by the employee themselves
    // (POST /leave-requests needs hr-payroll:self:use, which faculty holds, and acts on the caller's own record).
    // A paid type of 24 days a year gives a share of at least 2 days whatever month one joins in; one day a week ahead
    // is never before today, joining, or across more than one leave year.
    const type = await created<{ id: string }>(request, user, "/hr-payroll/leave-types", { code: "CL", name: "Casual leave", days_per_year: 24 });
    const joinedOn = indianDay(0);
    employee = await created<{ id: string; name: string; joined_on: string }>(request, user, "/hr-payroll/employees", {
      employee_code: "EMP-001",
      user_id: faculty.id,
      name: "Asha Rao",
      joined_on: joinedOn,
      employment_type: "permanent",
      staff_category: "teaching",
      designation: "Assistant Professor",
      department_name: "Finance",
    });
    const leaveOn = indianDay(7);
    await created(request, faculty, "/hr-payroll/leave-requests", { leave_type_id: type.id, from: leaveOn, to: leaveOn, reason: "Family function" });
    await signIn(page, user);

    const leave = widget(page, "Leave requests pending");
    await expect(leave.getByText("No leave requests pending")).toHaveCount(0);
    await expect(leave.locator("dl > div").filter({ hasText: "Pending" })).toHaveText("Pending1");
    const requests = leave.getByRole("list", { name: "Pending leave requests" });
    const row = requests.getByRole("listitem").filter({ hasText: "Asha Rao" });
    await expect(row).toContainText("Casual leave");
    await expect(row).toContainText(await shown(page, leaveOn));
    await expect(row).toContainText("1 day");
    await expect(row.getByText("Unpaid", { exact: true })).toHaveCount(0);

    const people = widget(page, "Joinings and exits");
    await expect(people.getByText("No joinings or exits this month")).toHaveCount(0);
    const summary = people.locator("dl > div");
    await expect(summary.filter({ hasText: "Joined" })).toHaveText("Joined1");
    await expect(summary.filter({ hasText: "Exited" })).toHaveText("Exited0");
    await expect(summary.filter({ hasText: "Headcount" })).toHaveText("Headcount1");
    const joinings = people.getByRole("list", { name: "Recent joinings" });
    const joined = joinings.getByRole("listitem").filter({ hasText: "Asha Rao" });
    await expect(joined).toContainText("Assistant Professor · Finance");
    await expect(joined).toContainText(`Joined ${await shown(page, joinedOn)}`);
  });

  test("hr-payroll.payroll-run-status shows the month's run HR starts, in review", async ({ page, request }) => {
    const w = byId("hr-payroll.payroll-run-status");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the hr-payroll API answered ${status[w.id]} to the hr-staff role`);
    test.skip(!employee, "needs the employee the leave journey adds");
    test.skip(minutesToIndianMidnight() < 15, NEAR_MIDNIGHT);
    // hr-staff holds hr-payroll:payroll:prepare: it sets the employee's salary (not its own, which is refused) from
    // joining and starts the run for the current Indian month, computed in the request (202, status review). The
    // employee has no bank account, so the run lists one exception. Approving needs payroll:approve, which hr-staff
    // does not hold (finance or management approve), so the run stays in review.
    await request
      .put(`/api/v1/hr-payroll/employees/${employee!.id}/salary`, {
        headers: { Authorization: `Bearer ${user.token}` },
        data: {
          effective_from: employee!.joined_on,
          lines: [
            { code: "BASIC", name: "Basic", kind: "earning", amount: "30000.00" },
            { code: "PF", name: "Provident fund", kind: "deduction", amount: "3600.00" },
          ],
        },
      })
      .then(async (r) => expect(r.ok(), `${r.url()} → ${r.status()} ${await r.text()}`).toBeTruthy());
    const period = indianDay(0).slice(0, 7);
    const run = await created<{ period: string; status: string; employees: number; net_total: string; exceptions: unknown[] }>(
      request,
      user,
      "/hr-payroll/payroll-runs",
      { period },
    );
    expect(run).toMatchObject({ period, status: "review", employees: 1 });
    expect(run.exceptions).toHaveLength(1);
    await signIn(page, user);

    const panel = widget(page, "Payroll this month");
    await expect(panel.getByText("No payroll run this month")).toHaveCount(0);
    const monthName = await page.evaluate((p) => new Date(`${p}-01T00:00:00`).toLocaleDateString("en-IN", { month: "long", year: "numeric" }), period);
    await expect(panel.getByRole("heading", { name: monthName, exact: true })).toBeVisible();
    await expect(panel.getByText("In review", { exact: true })).toBeVisible();
    const summary = panel.locator("dl > div");
    await expect(summary.filter({ hasText: "Employees" })).toHaveText("Employees1");
    const net = await page.evaluate((n) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(Number(n)), run.net_total);
    await expect(summary.filter({ hasText: "Net pay" })).toHaveText(`Net pay${net}`);
    await expect(panel.getByText("Next: HR to submit it for approval", { exact: true })).toBeVisible();
    await expect(panel.getByText("1 exception", { exact: true })).toBeVisible();
    await expect(panel.getByText(/^No run for /)).toHaveCount(0);
  });
});

test.describe("with e-office data", () => {
  test("e-office.files-pending lists a file a colleague forwards to HR", async ({ page, request }) => {
    const w = byId("e-office.files-pending");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the e-office API answered ${status[w.id]} to the hr-staff role`);
    test.skip(minutesToIndianMidnight() < 15, NEAR_MIDNIGHT);
    // File categories need e-office:settings:manage, which only org-admin holds. A file is opened held by its creator
    // and forwarding to oneself is refused (422 same_holder), so the faculty member (e-office:file:create) opens it and
    // forwards it to HR with the action asked for and a due date a week ahead (not in the past, by the Indian date).
    const category = await created<{ id: string }>(request, admin, "/e-office/categories", { code: "EST", name: "Establishment" });
    const file = await created<{ id: string; number: string }>(request, faculty, "/e-office/files", {
      subject: "Sanction of study leave",
      category_id: category.id,
      first_note: "Proposal for one week of study leave.",
    });
    expect(file.number).toMatch(/^EST\/\d{4}\/\d+$/);
    const dueOn = indianDay(7);
    await created(request, faculty, `/e-office/files/${file.id}/forward`, { to_user_id: user.id, action_required: "for approval", due_on: dueOn });
    await signIn(page, user);

    const panel = widget(page, "Files pending with me");
    await expect(panel.getByText("No files pending")).toHaveCount(0);
    const summary = panel.locator("dl > div");
    await expect(summary.filter({ hasText: "Pending" })).toHaveText("Pending1");
    await expect(summary.filter({ hasText: "Urgent" })).toHaveText("Urgent0");
    await expect(summary.filter({ hasText: "Overdue" })).toHaveText("Overdue0");
    const files = panel.getByRole("list", { name: "Files waiting longest" });
    const row = files.getByRole("listitem").filter({ hasText: file.number });
    await expect(row).toContainText("Sanction of study leave");
    await expect(row).toContainText("For approval");
    await expect(row).toContainText(`Due ${await shown(page, dueOn)}`);
    await expect(row.getByText("Overdue", { exact: true })).toHaveCount(0);
  });
});
