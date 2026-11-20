import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { OPENING, REQUIRED_HOURS, seedPlacement, SITE } from "./field-training-data";
import { created, dayFromNow, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Medical Student dashboard (layout platform/identity/config/dashboards/medical-student.yaml, which extends the Student layout; the role exists in the medical-college
 * profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a medical student signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Student ones included, whose module is in apps/frontend/config/modules.enabled.yaml and exports the
 *   widget: the panel renders by its registered title and shows its empty state, or says its data is not available
 *   while the backend is missing;
 * - widgets that are not on the dashboard yet are skipped, naming the module and the sprint batch that builds it
 *   (field-training and projects #339, skill-progress #329, facility-booking #331, and the inherited timetable-attendance, examinations and lms ones, and transport and library until they are enabled). Entries whose module is already merged carry that widget's texts, so the journey starts checking them the
 *   day the module is enabled;
 * - data journeys: a placement the hospital coordinator assigns and starts, with a log entry the student writes and the
 *   clinical supervisor verifies, shows in `field-training.my-placement` and `field-training.hours-logged`; a project the
 *   student proposes shows in `projects.my-projects`. Each skips until its module is enabled. The other widgets
 *   (skill-progress, facility-booking, lms and the inherited Student ones) hold data of their own modules and get their data
 *   journeys with those modules.
 *
 * facilities and practice are not in the Trial plan (platform/billing/config/plans.yaml), so the super admin moves
 * the organisation to Standard first. Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Medical Student";

const WIDGETS: LayoutWidget[] = [
  // Inherited from the Student layout (extends: student). lms.course-materials is both inherited and listed by the layout.
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
    // Texts of NoticesWidget.tsx in PR #473 (sprint batch #338), which is on main; the module is not enabled yet.
    id: "transport.notices",
    module: "campus-life/transport",
    batch: "#338",
    title: "Transport notices",
    probe: "/transport/me/notices?limit=1",
    empty: "No transport notices right now",
    unavailable: "Transport data is not available yet.",
  },
  {
    // Texts of LoansWidget.tsx in PR #476 (sprint batch #338), which is on main; the module is not enabled yet.
    id: "library.loans",
    module: "campus-life/library",
    batch: "#338",
    title: "Library loans",
    probe: "/library/me/loans",
    empty: "No books on loan",
    unavailable: "Library data is not available yet.",
  },
  // The medical student's own widgets.
  {
    id: "field-training.my-placement",
    module: "practice/field-training",
    batch: "#339",
    title: "My placement",
    probe: "/field-training/me/placements",
    empty: "No placement yet",
    unavailable: "Field training data is not available yet.",
  },
  {
    id: "field-training.hours-logged",
    module: "practice/field-training",
    batch: "#339",
    title: "Hours logged",
    probe: "/field-training/me/hours",
    empty: "No hours to show yet",
    unavailable: "Field training data is not available yet.",
  },
  {
    id: "skill-progress.my-progress",
    module: "practice/skill-progress",
    batch: "#329",
    title: "My progress",
    probe: "/skill-progress/me/progress",
    empty: "No assessments yet",
    unavailable: "Skill progress data is not available yet.",
    forbidden: "You do not have access to this.",
  },
  {
    // Texts of MyBookingsWidget.tsx and UpcomingBookings.tsx.
    id: "facility-booking.my-bookings",
    module: "facilities/facility-booking",
    batch: "#331",
    title: "My bookings",
    probe: "/facility-booking/bookings?scope=mine&from=now&status=pending,confirmed,checked_in&page_size=6",
    empty: "No upcoming bookings",
    unavailable: "Booking data is not available yet.",
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
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let admin: DashboardUser;
let user: DashboardUser;
/** The hospital coordinator and clinical supervisor who set up the student's placement. */
let coordinator: DashboardUser;
let supervisor: DashboardUser;
/** Per shipped widget id: what its GET answered the medical student. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "medical-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "medical-student");
  coordinator = await addUser(request, admin, "hospital-coordinator");
  supervisor = await addUser(request, admin, "clinical-supervisor");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a medical student signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("medical-student widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the medical-student layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the medical-student layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

test.describe("with field-training and projects data", () => {
  test("field-training.my-placement and hours-logged show the placement the coordinator assigns and the hours the supervisor verifies", async ({ page, request }) => {
    for (const id of ["field-training.my-placement", "field-training.hours-logged"]) {
      test.skip(!shipped(byId(id)), waitingFor(byId(id)));
      test.skip(!ready(id), `the field-training API answered ${status[id]} to the medical-student role`);
    }
    // The coordinator (field-training-coordinator) records the site and the opening and assigns and starts the placement;
    // the student logs today's hours and the supervisor named on the opening verifies them. Only verified hours count.
    await seedPlacement(request, { coordinator, supervisor, trainee: user }, { start: true, log: true, verify: true });
    await signIn(page, user);

    const placement = widget(page, "My placement");
    await expect(placement.getByText("No placement yet")).toHaveCount(0);
    const row = placement.getByRole("list", { name: "Your placements" }).getByRole("listitem").filter({ hasText: OPENING });
    await expect(row).toContainText(SITE);
    await expect(row).toContainText(`${4} of ${REQUIRED_HOURS} h verified`);
    await expect(row).toContainText("Active");

    const hours = widget(page, "Hours logged");
    await expect(hours.getByText("No hours to show yet")).toHaveCount(0);
    await expect(hours).toContainText(`4 of ${REQUIRED_HOURS} hours verified`);
    await expect(hours.getByText("Awaiting verification: 0 h")).toBeVisible();
  });

  test("projects.my-projects lists a project the student proposes", async ({ page, request }) => {
    const w = byId("projects.my-projects");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the projects API answered ${status[w.id]} to the medical-student role`);
    // projects:self:propose (projects-member): the project starts as proposed with the student as its lead.
    await created(request, user, "/projects/projects", {
      title: "Hand hygiene audit",
      kind: "Research",
      starts_on: dayFromNow(0),
      ends_on: dayFromNow(90),
    });
    await signIn(page, user);
    const panel = widget(page, "My projects");
    await expect(panel.getByText("You are not on a project yet")).toHaveCount(0);
    const row = panel.getByRole("list", { name: "My projects" }).getByRole("listitem").filter({ hasText: "Hand hygiene audit" });
    await expect(row).toContainText("Lead · No milestones yet");
    await expect(row).toContainText("Proposed");
  });
});
