import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";
import { ASSIGNMENT, COURSE, STUDENTS, VENUE, get, seedTeaching, type TeachingData } from "./faculty-data";

/**
 * Faculty / Instructor dashboard (sprint batch #326; layout platform/identity/config/dashboards/faculty.yaml). The role
 * exists in every academy profile; this journey uses an engineering college. A new user gets the profile role
 * `faculty`; the layout's `module_roles` give them `lms-instructor`, `timetable-attendance-faculty`,
 * `examinations-faculty` and `facility-booking-user`, so they read their own teaching data with no other role.
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a faculty user signs in and lands on the Faculty / Instructor dashboard;
 * - for every widget of the layout whose module is enabled and exports it: the panel renders by its registered
 *   title and shows its empty state, or says its data is not available while the backend is missing. A widget whose
 *   module the backend enables must answer 200 (probe in widgets.ts), so a 403 from a role catalogue regression or a
 *   404 from an unmounted route fails here instead of passing as "not available yet";
 * - the two timetable-attendance widgets, today-classes and attendance-to-mark, are built in the open PR #605 and are
 *   NOT exported on main yet. Their tests are skipped (reported as skipped, never as passed) until that PR merges;
 *   then the same tests run unchanged against the texts below, which are those of the code in #605 and must be
 *   re-checked against what merges.
 *
 * Not covered here: data journeys. Showing a real offering roster, an exam duty or a grading queue needs course,
 * enrolment, paper and session records created through several module APIs with their own preconditions (a term,
 * registrations, candidates); none of that is written or run yet, and the empty states below are all this file asserts
 * for those three widgets. Permission-based hiding is not covered either: apps/frontend/src/App.tsx passes
 * permissions="all" to the dashboard for now. Playwright needs the running stack and was not run for this change.
 */

const TITLE = "Faculty / Instructor";

const WIDGETS: LayoutWidget[] = [
  {
    // Texts of the code in the open PR #605 (TeachingTodayWidget.tsx, index.ts); not on main yet.
    id: "timetable-attendance.today-classes",
    module: "academics/timetable-attendance",
    batch: "#325",
    title: "Teaching today",
    probe: "/timetable-attendance/me/teaching-schedule",
    empty: "No classes to teach today",
    unavailable: "Timetable and attendance are not available yet.",
    forbidden: "You do not have access to this.",
  },
  {
    // Texts of the code in the open PR #605 (AttendanceToMarkWidget.tsx, index.ts); not on main yet.
    id: "timetable-attendance.attendance-to-mark",
    module: "academics/timetable-attendance",
    batch: "#325",
    title: "Attendance to mark",
    probe: "/timetable-attendance/me/attendance-to-mark",
    empty: "No attendance waiting to be marked",
    unavailable: "Timetable and attendance are not available yet.",
    forbidden: "You do not have access to this.",
  },
  {
    // Texts of AssignmentsToGradeWidget.tsx and describeFailure in lms/frontend/src/api/client.ts.
    id: "lms.assignments-to-grade",
    module: "academics/lms",
    batch: "#326",
    title: "Assignments to grade",
    probe: "/lms/me/grading-queue",
    empty: "Nothing waiting to be graded",
    unavailable: "Course data is not available yet.",
    forbidden: "You do not have access to this.",
  },
  {
    // Texts of ExamDuties.tsx and errorMessage in examinations/frontend/src/widgets/useWidgetData.tsx.
    id: "examinations.exam-duties",
    module: "academics/examinations",
    batch: "#325",
    title: "My exam duties",
    probe: "/examinations/me/duties",
    empty: "No upcoming exam duties.",
    unavailable: "Examinations data is not available yet.",
    forbidden: "You do not have access to this.",
  },
  {
    // Texts of CourseRoster.tsx (academic-management). A new organisation has no active term: the probe answers 404 active_term_not_found, which the widget shows as its empty state.
    id: "academic-management.course-roster",
    module: "academics/academic-management",
    batch: "#326",
    title: "Course roster",
    probe: "/academic-management/me/offerings",
    empty: "No courses this term",
    emptyCode: "active_term_not_found",
    unavailable: "Could not load your courses",
    forbidden: "Could not load your courses",
  },
  {
    // Inherited by the Faculty layout (#421): the instructor's own upcoming bookings (MyBookingsWidget.tsx).
    id: "facility-booking.my-bookings",
    module: "facilities/facility-booking",
    batch: "#421",
    title: "My bookings",
    probe: "/facility-booking/bookings?scope=mine&from=now&status=pending,confirmed,checked_in&page_size=6",
    empty: "No upcoming bookings",
    unavailable: "Booking data is not available yet.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);

let admin: DashboardUser;
let user: DashboardUser;
/** Per shipped widget id: what its GET answered the faculty user. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "engineering-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "faculty");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a faculty member signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("faculty widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the faculty layout's modules is enabled and exporting its widget yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the faculty layout's modules is enabled and exporting its widget yet");
    await signIn(page, user);
    for (const w of SHIPPED) await expectBody(page, w, status[w.id] ?? 0);
  });

  test("the widgets appear in the order of the layout", async ({ page }) => {
    test.skip(SHIPPED.length < 2, "fewer than two of the faculty layout's widgets are shipped");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    await expect(dashboard.getByRole("heading", { name: SHIPPED[0]!.title!, exact: true })).toBeVisible();
    const headings = (await dashboard.locator(".eos-widget h2, .eos-widget h3").allTextContents()).map((t) => t.trim());
    const seen = SHIPPED.map((w) => headings.indexOf(w.title!));
    expect(seen.every((i) => i >= 0), `headings found: ${headings.join(" | ")}`).toBeTruthy();
    expect(seen).toEqual([...seen].sort((a, b) => a - b));
  });

  // The two widgets of #605: skipped, not passed, until the PR merges and the module exports them.
  for (const id of ["timetable-attendance.today-classes", "timetable-attendance.attendance-to-mark"]) {
    const w = WIDGETS.find((x) => x.id === id)!;
    test(`${w.id} renders for a faculty member and answers 200 once ${w.module} ships it`, async ({ page }) => {
      test.skip(!shipped(w), waitingFor(w));
      expect(status[w.id], `${w.probe} must answer 200 to the faculty role`).toBe(200);
      await signIn(page, user);
      await expect(widget(page, w.title!)).toBeVisible();
      await expect(widget(page, w.title!).getByText(w.empty!, { exact: true })).toBeVisible();
    });
  }
});

test.describe("with teaching data", () => {
  let data: TeachingData;

  test.beforeAll(async ({ request }) => {
    test.setTimeout(240_000);
    // A term, a course and an offering the faculty member teaches, two registered students, a course space with a
    // published assignment both submitted, and an exam session and paper with two duties (faculty-data.ts).
    data = await seedTeaching(request, admin, user);
  });

  test("course roster lists the course they teach and, opened, its enrolled students", async ({ page }) => {
    await signIn(page, user);
    const panel = widget(page, "Course roster");
    await expect(panel.getByText(`${COURSE.code} · ${COURSE.title}`)).toBeVisible();
    await expect(panel).toContainText("Primary");
    await expect(panel).toContainText("A (2)"); // section A, two enrolled
    await expect(panel.getByText("2 enrolled", { exact: true })).toBeVisible();
    await panel.getByText(`${COURSE.code} · ${COURSE.title}`).click();
    const roster = panel.getByRole("list", { name: `Roster of ${COURSE.code} · ${COURSE.title}` });
    for (const name of STUDENTS) await expect(roster).toContainText(name);
    await expect(roster).toContainText("Section A");
    await panel.getByRole("button", { name: "All courses" }).click();
    await expect(panel.getByText("2 enrolled", { exact: true })).toBeVisible();
  });

  test("assignments to grade shows the assignment both students submitted", async ({ page }) => {
    await signIn(page, user);
    const panel = widget(page, "Assignments to grade");
    const queue = panel.getByRole("list", { name: "Work to grade" });
    await expect(queue).toContainText(ASSIGNMENT);
    await expect(queue).toContainText(`${COURSE.title} · waiting since`); // the course the space belongs to
    await expect(queue.getByText("2 submissions", { exact: true })).toBeVisible();
    await expect(panel.getByText("Nothing waiting to be graded")).toHaveCount(0);
  });

  test("exam duties shows the invigilation and the evaluation duty assigned to them", async ({ page }) => {
    await signIn(page, user);
    const panel = widget(page, "My exam duties");
    await expect(panel.getByText("Invigilation", { exact: true })).toBeVisible();
    await expect(panel).toContainText(VENUE);
    await expect(panel.getByText("Evaluation", { exact: true })).toBeVisible();
    await expect(panel.getByText("Assigned", { exact: true })).toHaveCount(2);
    await expect(panel.getByText("No upcoming exam duties.")).toHaveCount(0);
  });

  test("another faculty member who teaches nothing sees none of it", async ({ page }) => {
    await signIn(page, data.other);
    await expect(widget(page, "Course roster").getByText("No courses this term", { exact: true })).toBeVisible();
    await expect(widget(page, "Assignments to grade").getByText("Nothing waiting to be graded", { exact: true })).toBeVisible();
    await expect(widget(page, "My exam duties").getByText("No upcoming exam duties.", { exact: true })).toBeVisible();
    await expect(page.getByText(ASSIGNMENT)).toHaveCount(0);
    await expect(page.getByText(VENUE)).toHaveCount(0);
  });

  // The same records, read through the API the widgets call.
  test("the widget endpoints answer the faculty member with their own records and another one with nothing", async ({ request }) => {
    const mine = {
      offerings: await get<{ items: { course_offering_id: string; enrolled_count: number }[] }>(request, user, "/api/v1/academic-management/me/offerings"),
      queue: await get<{ total: number; items: { title: string; waiting_count: number }[] }>(request, user, "/api/v1/lms/me/grading-queue"),
      duties: await get<{ items: { duty_type: string }[] }>(request, user, "/api/v1/examinations/me/duties"),
    };
    expect(mine.offerings.items.map((o) => [o.course_offering_id, o.enrolled_count])).toEqual([[data.offering.id, 2]]);
    expect(mine.queue.items.map((i) => [i.title, i.waiting_count])).toEqual([[ASSIGNMENT, 2]]);
    expect(mine.duties.items.map((d) => d.duty_type).sort()).toEqual(["evaluation", "invigilation"]);

    const theirs = {
      offerings: await get<{ items: unknown[] }>(request, data.other, "/api/v1/academic-management/me/offerings"),
      queue: await get<{ total: number; items: unknown[] }>(request, data.other, "/api/v1/lms/me/grading-queue"),
      duties: await get<{ items: unknown[] }>(request, data.other, "/api/v1/examinations/me/duties"),
    };
    expect(theirs.offerings.items).toEqual([]);
    expect(theirs.queue).toEqual({ items: [], total: 0 });
    expect(theirs.duties.items).toEqual([]);
  });

  test("another faculty member is refused the course's roster, space, submissions, gradebook and the duties of others", async ({ request }) => {
    const refused = async (who: { token: string }, path: string, code: string) => {
      const response = await request.get(path, { headers: { Authorization: `Bearer ${who.token}` } });
      expect(response.status(), path).toBe(403);
      expect(((await response.json()) as { detail: { code: string } }).detail.code, path).toBe(code);
    };
    const { other } = data;
    await refused(other, `/api/v1/academic-management/offerings/${data.offering.id}/roster`, "forbidden");
    await refused(other, `/api/v1/lms/course-spaces/${data.space.id}`, "not_in_scope");
    await refused(other, `/api/v1/lms/assignments/${data.assignment.id}/submissions`, "not_in_scope");
    await refused(other, `/api/v1/lms/course-spaces/${data.space.id}/gradebook`, "not_in_scope");
    await refused(other, "/api/v1/examinations/duties", "forbidden"); // the list of everyone's duties
    // The teaching faculty member reads the same roster and sees both students.
    const roster = await get<{ total: number; items: { student_name: string }[] }>(request, user, `/api/v1/academic-management/offerings/${data.offering.id}/roster`);
    expect(roster.items.map((i) => i.student_name).sort()).toEqual([...STUDENTS].sort());
  });

  test("a student cannot read what faculty read, and nobody without a token reads any of it", async ({ request }) => {
    const auth = { Authorization: `Bearer ${data.students[0]!.token}` };
    for (const path of [
      "/api/v1/lms/me/grading-queue",
      "/api/v1/examinations/me/duties",
      `/api/v1/academic-management/offerings/${data.offering.id}/roster`,
      `/api/v1/lms/assignments/${data.assignment.id}/submissions`,
    ]) {
      expect((await request.get(path, { headers: auth })).status(), path).toBe(403);
    }
    for (const path of ["/api/v1/lms/me/grading-queue", "/api/v1/examinations/me/duties", "/api/v1/academic-management/me/offerings"]) {
      expect((await request.get(path)).status(), path).toBe(401);
    }
  });

  test("the department head's faculty-load report counts the teaching assignment", async ({ request }) => {
    // The Faculty layout has no faculty-load widget (it is on the Department Admin dashboard); the report is read here.
    const report = await get<{ items: { faculty_id: string; faculty_name: string; offerings_count: number; contact_hours: number; over_load: boolean }[] }>(
      request,
      data.hod,
      "/api/v1/academic-management/faculty-load",
    );
    const row = report.items.find((i) => i.faculty_id === user.id);
    expect(row, JSON.stringify(report.items)).toBeTruthy();
    expect([row!.offerings_count, row!.contact_hours, row!.over_load]).toEqual([1, 4, false]);
    expect(report.items.some((i) => i.faculty_id === data.other.id)).toBe(false); // teaches nothing: no load
  });
});
