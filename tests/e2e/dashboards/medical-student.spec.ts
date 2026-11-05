import { expect, test } from "@playwright/test";
import { organisationWithUser, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

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
 * - no data journeys yet: every widget of this layout that holds data waits for its module (field-training, projects) or for the student to have records of it. The data journeys are added with the modules.
 *
 * facilities and practice are not in the Trial plan (platform/billing/config/plans.yaml), so the super admin moves
 * the organisation to Standard first. Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Medical Student";

const WIDGETS: LayoutWidget[] = [
  // Inherited from the Student layout (extends: student). lms.course-materials is both inherited and listed by the layout.
  { id: "timetable-attendance.today", module: "academics/timetable-attendance", batch: "#325" },
  { id: "timetable-attendance.attendance-summary", module: "academics/timetable-attendance", batch: "#325" },
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
  { id: "field-training.my-placement", module: "practice/field-training", batch: "#339" },
  { id: "field-training.hours-logged", module: "practice/field-training", batch: "#339" },
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
  { id: "projects.my-projects", module: "practice/projects", batch: "#339" },
];
const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the medical student. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  user = await organisationWithUser(request, { academyType: "medical-college", role: "medical-student" });
  await standardPlan(request, user.organisation.id);
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
