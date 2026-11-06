import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, dayFromNow, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Student dashboard (sprint batch #338, was #8; layout platform/identity/config/dashboards/student.yaml). A new user
 * gets the profile role `student` by default; the layout's `module_roles` give them `transport-rider` and
 * `library-member`, so they read their own transport notices and library loans with no other role.
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a student signs in and lands on the Student dashboard;
 * - for every widget of the layout whose module is in apps/frontend/config/modules.enabled.yaml: the panel renders by
 *   its registered title and shows its empty state, or says its data is not available while the backend is missing;
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it
 *   (timetable-attendance and examinations #325, lms #326);
 * - data journeys: campus-life staff create real records through the module APIs (nothing is faked) and the
 *   student's cards show them: a hostel notice for the student's hostel and one for every hostel, a transport notice
 *   for every route, and a library book on loan with its due date.
 *
 * finance-operations and campus-life are not in the Trial plan (platform/billing/config/plans.yaml), so the super
 * admin moves the organisation to Standard first. The empty-state tests run before any data is created (serial
 * mode). Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Student";

const WIDGETS: LayoutWidget[] = [
  {
    id: "timetable-attendance.today",
    module: "academics/timetable-attendance",
    batch: "#325",
    title: "Today's classes",
    probe: "/timetable-attendance/me/schedule",
    empty: "No classes today",
    unavailable: "Timetable and attendance are not available yet.",
  },
  {
    id: "timetable-attendance.attendance-summary",
    module: "academics/timetable-attendance",
    batch: "#325",
    title: "My attendance",
    probe: "/timetable-attendance/me/attendance-summary",
    empty: "No attendance recorded yet",
    // No active term: timetable-attendance answers 404 active_term_not_found, which the widget shows as nothing recorded yet.
    emptyCode: "active_term_not_found",
    unavailable: "Timetable and attendance are not available yet.",
  },
  { id: "examinations.upcoming-assessments", module: "academics/examinations", batch: "#325" },
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
    id: "transport.notices",
    module: "campus-life/transport",
    batch: "#338",
    title: "Transport notices",
    probe: "/transport/me/notices?limit=1",
    empty: "No transport notices right now",
    unavailable: "Transport data is not available yet.",
  },
  {
    id: "library.loans",
    module: "campus-life/library",
    batch: "#338",
    title: "Library loans",
    probe: "/library/me/loans",
    empty: "No books on loan",
    unavailable: "Library data is not available yet.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);

const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let admin: DashboardUser;
let user: DashboardUser;
/** Per shipped widget id: what its GET answered the student. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "medical-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "student");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a student signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("student widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the student layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the student layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

test.describe("with campus-life data", () => {
  test("hostel.notices shows the notice for the student's hostel and the one for every hostel", async ({ page, request }) => {
    const w = byId("hostel.notices");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the hostel API answered ${status[w.id]} to the student role`);
    // The hostel office (hostel-admin, which also holds notice:publish) allocates the student a bed, checks them in
    // and posts the notices.
    const office = await addUser(request, admin, "hostel-admin");
    const hostel = await created<{ id: string }>(request, office, "/hostel/hostels", { name: "Nightingale Block", occupancy_type: "women" });
    const room = await created<{ id: string }>(request, office, `/hostel/hostels/${hostel.id}/rooms`, { number: "101", room_type: "double", capacity: 2 });
    const allocation = await created<{ id: string }>(request, office, "/hostel/allocations", {
      person_id: user.id,
      room_id: room.id,
      bed: "1",
      academic_year: "2026-27",
      from: dayFromNow(0),
      to: dayFromNow(180),
    });
    await created(request, office, `/hostel/allocations/${allocation.id}/check-in`, {});
    await created(request, office, "/hostel/notices", { hostel_id: hostel.id, title: "Water cut 2-4 pm", body: "Tank cleaning" });
    await created(request, office, "/hostel/notices", { hostel_id: null, title: "Diwali holidays", body: "Hostels stay open" });
    await signIn(page, user);
    const panel = widget(page, "Hostel notices");
    await expect(panel.getByText("No hostel notices right now")).toHaveCount(0);
    await expect(panel).toContainText("Water cut 2-4 pm");
    await expect(panel).toContainText("Diwali holidays");
    await expect(panel.getByText("All hostels", { exact: true })).toBeVisible(); // the badge, not the subtitle
  });

  test("transport.notices shows a notice for every route", async ({ page, request }) => {
    const w = byId("transport.notices");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the transport API answered ${status[w.id]} to the student role`);
    // The transport office (transport-admin, notice:publish) posts a notice with no route: every rider sees it,
    // with or without a pass.
    const office = await addUser(request, admin, "transport-admin");
    await created(request, office, "/transport/notices", {
      route_id: null,
      kind: "delay",
      title: "Route 7 runs 20 minutes late",
      body: "Traffic on the ring road",
    });
    await signIn(page, user);
    const panel = widget(page, "Transport notices");
    await expect(panel.getByText("No transport notices right now")).toHaveCount(0);
    await expect(panel.getByRole("list", { name: "Transport notices" })).toBeVisible();
    await expect(panel).toContainText("Route 7 runs 20 minutes late");
    await expect(panel).toContainText("All routes · Traffic on the ring road");
    await expect(panel.getByText("Delay", { exact: true })).toBeVisible();
  });

  test("library.loans shows the book on loan with its due date and renewals left", async ({ page, request }) => {
    const w = byId("library.loans");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the library API answered ${status[w.id]} to the student role`);
    // The head librarian (library-admin: policy:manage plus everything the librarian has) sets the student loan
    // policy, catalogues a copy, registers the student as a member and issues the book at the desk.
    const librarian = await addUser(request, admin, "library-admin");
    const barcode = `BC-${admin.organisation.slug}`;
    const policy = { member_category: "student", max_loans: 3, loan_days: 14, max_renewals: 1, fine_per_day: "2.00", max_unpaid_fines: "50.00", hold_days: 3 };
    const put = await request.put("/api/v1/library/loan-policies", { headers: { Authorization: `Bearer ${librarian.token}` }, data: [policy] });
    expect(put.ok(), await put.text()).toBeTruthy();
    const title = await created<{ id: string }>(request, librarian, "/library/titles", { title: "Gray's Anatomy", kind: "book" });
    await created(request, librarian, `/library/titles/${title.id}/copies`, { accession_no: `ACC-${admin.organisation.slug}`, barcode });
    await created(request, librarian, "/library/members", { person_id: user.id, category: "student" });
    await created(request, librarian, "/library/loans", { barcode, person_id: user.id });
    await signIn(page, user);
    const panel = widget(page, "Library loans");
    await expect(panel.getByText("No books on loan")).toHaveCount(0);
    await expect(panel.getByRole("list", { name: "Library loans" })).toBeVisible();
    await expect(panel).toContainText("Gray's Anatomy");
    await expect(panel).toContainText("Due ");
    await expect(panel).toContainText("1 renewal left");
  });
});
