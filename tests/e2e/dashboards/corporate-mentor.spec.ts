import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, dayFromNow, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Corporate Mentor dashboard (layout platform/identity/config/dashboards/corporate-mentor.yaml, which extends the
 * Faculty layout; the role exists in the management-institute profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a corporate mentor signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Faculty ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml: the panel renders by its registered title and shows its empty
 *   state, or says its data is not available while the backend is missing (the mentor holds the faculty role's
 *   permissions through `extends`, and selection-process-panelist's through the layout's `module_roles`);
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it
 *   (timetable-attendance #325, lms #326, projects and field-training #339, productions #318);
 *   examinations is enabled and exports examinations.exam-duties, so that widget is checked like the others;
 * - data journeys, each once its widget has shipped and its API answers the corporate-mentor role: a course the
 *   organisation admin assigns the mentor to teach in the active term shows in academic-management.course-roster.
 *   selection-process.to-judge's journey is fixme (see below), and so are those of the modules not built yet.
 *
 * The super admin moves the organisation to Standard first, as the other journeys do, so every module of the
 * profile is entitled. The empty-state tests run before any data is created (serial mode). Loading states are
 * covered by the modules' unit tests, not here.
 */

const TITLE = "Corporate Mentor";

const WIDGETS: LayoutWidget[] = [
  // Inherited from the Faculty layout (extends: faculty).
  { id: "timetable-attendance.today-classes", module: "academics/timetable-attendance", batch: "#325" },
  { id: "timetable-attendance.attendance-to-mark", module: "academics/timetable-attendance", batch: "#325" },
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
    // A new organisation has no active term: GET /me/offerings answers 404 active_term_not_found, which the widget
    // shows as nothing this term.
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
  // The corporate mentor's own widgets.
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
    id: "field-training.trainees-to-assess",
    module: "practice/field-training",
    batch: "#339",
    title: "Trainees to assess",
    probe: "/field-training/me/trainees?limit=1",
    empty: "Nothing to assess right now",
    unavailable: "Field training data is not available yet.",
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
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let admin: DashboardUser;
let user: DashboardUser;
/** Per shipped widget id: what its GET answered the corporate mentor. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "management-institute" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "corporate-mentor");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a corporate mentor signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("corporate-mentor widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the corporate-mentor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the corporate-mentor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

test.describe("with academic-management data", () => {
  test("academic-management.course-roster lists the course the mentor is assigned to teach this term", async ({ page, request }) => {
    const w = byId("academic-management.course-roster");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the academic-management API answered ${status[w.id]} to the corporate-mentor role`);
    // The organisation admin holds every academic-management key: it adds a term around today and activates it, a
    // course (department_id is a reference academic-management does not validate), an offering of one section in that
    // term, and assigns the mentor as its primary instructor. GET /me/offerings lists the active term's offerings the
    // caller is assigned to, whatever the offering's status; nobody is enrolled, so the roster is empty.
    const term = await created<{ id: string }>(request, admin, "/academic-management/terms", {
      code: "2026-T2",
      name: "Term 2 2026",
      starts_on: dayFromNow(-30),
      ends_on: dayFromNow(90),
    });
    await created(request, admin, `/academic-management/terms/${term.id}/activate`, {});
    const course = await created<{ id: string }>(request, admin, "/academic-management/courses", {
      code: "MBA-501",
      title: "Corporate strategy",
      credits: 3,
      course_type: "theory",
      department_id: randomUUID(),
    });
    const offering = await created<{ id: string }>(request, admin, "/academic-management/offerings", {
      course_id: course.id,
      academic_period_id: term.id,
      sections: [{ code: "A", capacity: 60 }],
    });
    await created(request, admin, `/academic-management/offerings/${offering.id}/faculty-assignments`, {
      faculty_id: user.id,
      role: "primary",
      contact_hours: 3,
    });
    await signIn(page, user);

    const panel = widget(page, "Course roster");
    await expect(panel.getByText("No courses this term")).toHaveCount(0);
    const row = panel.getByRole("list", { name: "Your courses this term" }).getByRole("listitem").filter({ hasText: "MBA-501 · Corporate strategy" });
    await expect(row).toContainText("Primary · A (0)");
    await expect(row).toContainText("0 enrolled");
    // Choosing the course lists its learners (GET /offerings/{id}/roster, which faculty may read for what they teach).
    await row.getByText("MBA-501 · Corporate strategy").click();
    await expect(panel.getByText("No learners enrolled in MBA-501 · Corporate strategy yet", { exact: true })).toBeVisible();
    await panel.getByRole("button", { name: "All courses" }).click();
    await expect(panel.getByRole("list", { name: "Your courses this term" })).toBeVisible();
  });
});

// Backend-dependent: these need their module's API to create the data through, so nothing here is faked.
test.fixme("selection-process.to-judge lists a candidate in a competition selection the mentor judges", async () => {
  // practice/selection-process is enabled and has every API this needs (a coordinator opens a process with one stage,
  // a panel with the mentor as member, a registered candidate), but ToJudgeWidget asks
  // GET /processes/{id}/candidates?scope=managed&status=registered,in_progress, and the API takes `status` as a
  // repeated query parameter (list[str]), so it filters on the one value "registered,in_progress" and the panel
  // stays empty. Write this once selection-process sends status=registered&status=in_progress (or splits commas).
});

test.fixme("projects.to-review lists the live projects waiting for the mentor's review", async () => {
  // practice/projects (sprint batch #339); vocabulary: "Live project". The layout grants projects-guide.
});

test.fixme("field-training.trainees-to-assess lists the interns the mentor assesses", async () => {
  // practice/field-training (sprint batch #339); vocabulary: "Internship". The layout grants field-training-supervisor.
});

test.fixme("productions.in-preparation lists the case competitions and industry events being prepared", async () => {
  // practice/productions (sprint batch #318); vocabulary: "Case competition / industry event".
});
