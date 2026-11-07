import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Law Student dashboard (layout platform/identity/config/dashboards/law-student.yaml, which extends the Student
 * layout; the role exists in the law-college profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a law student signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Student ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml: the panel renders by its registered title and shows its empty state
 *   (the law student holds selection-process:candidate:read through the student role's grants);
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it
 *   (productions #318, field-training and projects #339, placement-career #337, and the inherited
 *   timetable-attendance, examinations, lms, transport and library ones).
 *
 * campus-life and finance-operations are not in the Trial plan (platform/billing/config/plans.yaml), so the super
 * admin moves the organisation to Standard first. Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Law Student";

const WIDGETS: LayoutWidget[] = [
  // Inherited from the Student layout (extends: student).
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
  // The law student's own widgets.
  {
    id: "selection-process.upcoming",
    module: "practice/selection-process",
    batch: "#322",
    title: "Upcoming Selection Events",
    probe: "/selection-process/slots/upcoming?limit=6",
    empty: "No upcoming selection rounds",
    unavailable: "Schedule data is not available yet.",
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
    id: "projects.my-projects",
    module: "practice/projects",
    batch: "#339",
    title: "My projects",
    probe: "/projects/me/projects",
    empty: "You are not on a project yet",
    unavailable: "Projects data is not available yet.",
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
    id: "placement-career.openings",
    module: "campus-life/placement-career",
    batch: "#337",
    title: "Job openings",
    probe: "/placement-career/me/openings?limit=1",
    empty: "No openings right now",
    unavailable: "Placement data is not available yet.",
    forbidden: "You do not have access to this.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the law student. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "law-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "law-student");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a law student signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("law-student widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the law-student layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the law-student layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
