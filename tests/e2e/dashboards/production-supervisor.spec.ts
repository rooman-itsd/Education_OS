import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Production Supervisor dashboard (layout platform/identity/config/dashboards/production-supervisor.yaml, which extends the Faculty layout; the role exists in the
 * film-media-institute profile). Issue #320.
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a production supervisor signs in and lands on their dashboard;
 * - for every widget of the layout whose module is in apps/frontend/config/modules.enabled.yaml and exports it: the
 *   panel renders by its registered title and shows its empty state, or says its data is not available while the
 *   backend is missing;
 * - widgets of modules not enabled yet, or not exported yet, are skipped, naming the module and the sprint batch that
 *   builds it: projects (#339), productions (#318, PR #454), timetable-attendance and examinations (#325) and lms (#326);
 * - there is no data journey: every widget of this layout that has shipped needs a selection panel or a project guide
 *   to have something to show, and those modules' own journeys cover that. The empty states are what this checks.
 *
 * facilities is not in the Trial plan (platform/billing/config/plans.yaml), so the super admin moves the organisation
 * to Standard first. The empty-state tests run before any data is created (serial mode). Loading states are covered
 * by the modules' unit tests, not here.
 */

const TITLE = "Production Supervisor";

const WIDGETS: LayoutWidget[] = [
  // Inherited from the Faculty layout (extends: faculty).
  { id: "timetable-attendance.today-classes", module: "academics/timetable-attendance", batch: "#325" },
  { id: "timetable-attendance.attendance-to-mark", module: "academics/timetable-attendance", batch: "#325" },
  { id: "lms.assignments-to-grade", module: "academics/lms", batch: "#326" },
  { id: "examinations.exam-duties", module: "academics/examinations", batch: "#325" },
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
  // The production supervisor's own widgets.
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
    id: "projects.active",
    module: "practice/projects",
    batch: "#339",
    title: "Active projects",
    probe: "/projects/projects?status=active&limit=1",
    empty: "No active projects",
    unavailable: "Projects data is not available yet.",
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
  {
    // Texts of ToJudgeWidget.tsx (practice/selection-process, merged in #414). The widget's first
    // GET lists the open processes; it then asks each for the candidates the panelist judges.
    id: "selection-process.to-judge",
    module: "practice/selection-process",
    batch: "#322",
    title: "To Judge",
    probe: "/selection-process/processes?status=open&page_size=5",
    empty: "No candidates awaiting review",
    unavailable: "Judging tasks are not available yet.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let admin: DashboardUser;
let user: DashboardUser;
/** Per shipped widget id: what its GET answered the production supervisor. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "film-media-institute" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "production-supervisor");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a production supervisor signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("production-supervisor widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the production-supervisor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the production-supervisor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
