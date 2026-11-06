import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Legal Mentor dashboard (layout platform/identity/config/dashboards/legal-mentor.yaml, which extends the Faculty
 * layout; the role exists in the law-college profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a legal mentor signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Faculty ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml: the panel renders by its registered title and shows its empty state
 *   (the mentor holds selection-process:decision:write through selection-process-panelist in the layout's
 *   module_roles);
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it
 *   (projects and field-training #339, productions #318, and the inherited timetable-attendance, lms and
 *   examinations ones).
 *
 * No data journey yet: `selection-process.to-judge` lists candidates on panels the mentor sits on, which needs a
 * process with a panel and a registered candidate; the moot court coordinator's journey covers creating an open call.
 * The organisation is moved to Standard first, as in the other academy journeys.
 */

const TITLE = "Legal Mentor";

const WIDGETS: LayoutWidget[] = [
  // Inherited from the Faculty layout (extends: faculty).
  {
    id: "timetable-attendance.today-classes",
    module: "academics/timetable-attendance",
    batch: "#325",
    title: "Teaching today",
    probe: "/timetable-attendance/me/teaching-schedule",
    empty: "No classes to teach today",
    unavailable: "Timetable and attendance are not available yet.",
  },
  {
    id: "timetable-attendance.attendance-to-mark",
    module: "academics/timetable-attendance",
    batch: "#325",
    title: "Attendance to mark",
    probe: "/timetable-attendance/me/attendance-to-mark",
    empty: "No attendance waiting to be marked",
    unavailable: "Timetable and attendance are not available yet.",
  },
  {
    id: "lms.assignments-to-grade",
    module: "academics/lms",
    batch: "#326",
    title: "Assignments to grade",
    probe: "/lms/me/grading-queue",
    empty: "Nothing waiting to be graded",
    unavailable: "Course data is not available yet.",
  },
  {
    id: "examinations.exam-duties",
    module: "academics/examinations",
    batch: "#325",
    title: "My exam duties",
    probe: "/examinations/me/duties",
    empty: "No upcoming exam duties.",
    unavailable: "Examinations data is not available yet.",
  },
  {
    id: "academic-management.course-roster",
    module: "academics/academic-management",
    batch: "#100",
    title: "Course roster",
    probe: "/academic-management/me/offerings",
    empty: "No courses this term",
    // A new organisation has no active term: GET /me/offerings answers 404 active_term_not_found, which the widget's
    // client turns into an empty page ("No courses this term").
    emptyCode: "active_term_not_found",
    unavailable: "No courses this term",
    forbidden: "Could not load your courses",
  },
  {
    // Inherited from the Faculty layout (#421): the instructor's own upcoming bookings (MyBookingsWidget.tsx).
    id: "facility-booking.my-bookings",
    module: "facilities/facility-booking",
    batch: "#421",
    title: "My bookings",
    probe: "/facility-booking/bookings?scope=mine&from=now&status=pending,confirmed,checked_in&page_size=6",
    empty: "No upcoming bookings",
    unavailable: "Booking data is not available yet.",
  },
  // The legal mentor's own widgets.
  {
    id: "projects.to-review",
    module: "practice/projects",
    batch: "#339",
    title: "To review",
    probe: "/projects/me/reviews?limit=1",
    empty: "Nothing waiting for your review",
    unavailable: "Projects data is not available yet.",
  },
  {
    id: "selection-process.to-judge",
    module: "practice/selection-process",
    batch: "#322",
    title: "To Judge",
    probe: "/selection-process/processes?status=open&page_size=5",
    empty: "No candidates awaiting review",
    unavailable: "Judging tasks are not available yet.",
  },
  {
    id: "field-training.trainees-to-assess",
    module: "practice/field-training",
    batch: "#339",
    title: "Trainees to assess",
    probe: "/field-training/me/trainees?limit=1",
    empty: "Nothing to assess right now",
    unavailable: "Field training data is not available yet.",
  },
  {
    id: "productions.in-preparation",
    module: "practice/productions",
    batch: "#318",
    title: "In preparation",
    probe: "/productions/in-preparation",
    empty: "Nothing in preparation",
    unavailable: "Production data is not available yet.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the legal mentor. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const admin = await organisationAdmin(request, { academyType: "law-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "legal-mentor");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a legal mentor signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("legal-mentor widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the legal-mentor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the legal-mentor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
