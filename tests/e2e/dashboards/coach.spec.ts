import { expect, test } from "@playwright/test";
import { organisationWithUser, type DashboardUser } from "./organisation";
import { dayFromNow, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Coach dashboard (layout platform/identity/config/dashboards/coach.yaml, which extends the Faculty layout; the role
 * exists in the sports-college profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a coach signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Faculty ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml: the panel renders by its registered title and shows its empty
 *   state, or says its data is not available while the backend is missing (the coach holds the faculty role's
 *   permissions through `extends`);
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it;
 *   facility-booking is enabled but exports facility-booking.bookings-today, not the facility-booking.bookings the
 *   layout lists, so that widget skips until sprint batch #331; athlete-performance.session-plan and wearables.alerts
 *   are not built in v1 (see NOT_BUILT);
 * - the data journeys are fixme: each needs a sports module enabled, and the coach's scoping in tournament-events
 *   and training-video-analysis needs the athlete-performance.athlete.registered event.
 *
 * The sports suite is the profile's one specialized suite, so Trial includes it; facilities is not in Trial, so the
 * super admin moves the organisation to Standard first. The empty-state tests run before any data is created
 * (serial mode). Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Coach";

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
    // The widget's client treats 404 (no active term) as nothing this term, not as a failure.
    emptyWhen: [404],
    unavailable: "No courses this term",
    forbidden: "Could not load your courses",
  },
  // The coach's own widgets.
  {
    id: "athlete-performance.squad-overview",
    module: "sports/athlete-performance",
    batch: "#330",
    title: "Squad overview",
    probe: "/athlete-performance/reports/squad-summary",
    empty: "No athletes yet",
    unavailable: "Athlete performance data is not available yet.",
  },
  { id: "athlete-performance.session-plan", module: "sports/athlete-performance", batch: "#330" },
  {
    id: "training-video-analysis.reviews-pending",
    module: "sports/training-video-analysis",
    batch: "#330",
    title: "Videos to review",
    probe: "/training-video-analysis/videos?annotated=false&limit=6",
    empty: "No videos waiting for review",
    unavailable: "Training video data is not available yet.",
  },
  {
    // Texts of facility-booking.bookings-today, the widget the module exports today (BookingsTodayWidget.tsx).
    id: "facility-booking.bookings",
    module: "facilities/facility-booking",
    batch: "#331",
    title: "Bookings today",
    probe: "/facility-booking/summary",
    empty: "No bookings today",
    unavailable: "Booking data is not available yet.",
  },
  // An integration, not a module: listed by its folder so the skip names where it lives.
  { id: "wearables.alerts", module: "integrations/wearables", batch: "after launch" },
  {
    id: "tournament-events.calendar",
    module: "sports/tournament-events",
    batch: "#330",
    title: "Tournament calendar",
    probe: `/tournament-events/calendar?from=${dayFromNow(0)}&to=${dayFromNow(27)}`,
    empty: "Nothing on the calendar",
    unavailable: "Tournament data is not available yet.",
  },
];

/**
 * Widgets the layout lists that no v1 batch builds, and why: they skip with this reason instead of waitingFor's.
 * (A local helper: widgets.ts has no notion of a widget that is not planned.)
 */
const NOT_BUILT: Record<string, string> = {
  "athlete-performance.session-plan":
    "not built: training plans and sessions belong to training-video-analysis, and sprint batch #330 proposes moving this widget there",
  "wearables.alerts": "not built in v1: integrations/wearables is a placeholder for after launch (docs/team/sprint-v1.0.md)",
};
const why = (w: LayoutWidget) => NOT_BUILT[w.id] ?? waitingFor(w);

const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the coach. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  user = await organisationWithUser(request, { academyType: "sports-college", role: "coach" });
  await standardPlan(request, user.organisation.id);
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a coach signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("coach widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the coach layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the coach layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    for (const w of SHIPPED) await expectBody(page, w, status[w.id] ?? 0);
  });

  for (const w of WIDGETS.filter((w) => !shipped(w))) {
    test(`${w.id} renders once ${w.module} ships`, async ({ page }) => {
      test.skip(!shipped(w), why(w));
      // The shell renders an unregistered id as a "Not built yet" placeholder titled with the id itself.
      await signIn(page, user);
      await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
      await expect(widget(page, w.id)).toHaveCount(0);
    });
  }
});

// Backend-dependent: these need their module's API to create the data through, so nothing here is faked. Each needs
// its module in both modules.enabled.yaml files; write them as the finance-staff data journeys are written then.
test.describe("with sports data", () => {
  test.fixme("athlete-performance.squad-overview counts the coach's athletes and their latest results", async () => {
    // sports/athlete-performance (sprint batch #330, PR #385). As the org admin (athlete-performance-admin through the
    // profile role) POST /athlete-performance/disciplines { name: "Athletics", category: "individual", active: true }
    // and /metrics { name: "100 m sprint", unit: "s", direction: "lower_is_better", discipline_id }. As the coach
    // (athlete:write, result:record) POST /athlete-performance/athletes twice { full_name, primary_discipline_id,
    // coach_id: <coach id>, squad: "Sprints", status: "active" } and a POST /athlete-performance/results for each
    // { athlete_id, metric_id, value, recorded_at, context: "training" }.
    // Expect: "No athletes yet" is gone; the summary shows 2 athletes in squad "Sprints" with results recorded.
  });

  test.fixme("training-video-analysis.reviews-pending lists a video not annotated yet", async () => {
    // sports/training-video-analysis (sprint batch #330, PR #390). As the coach (video:upload)
    // POST /training-video-analysis/videos { title: "Block starts, lane 4", video_url: "https://videos.example.com/e2e.mp4",
    // duration_seconds: 95, uploader_id: <coach id>, recorded_at: <today> } and add no annotation. Videos tagged to an
    // athlete are scoped by the athlete ids training-video-analysis learns from athlete-performance.athlete.registered
    // through platform/event-bus, so a journey that tags athletes needs that event delivered.
    // Expect: "No videos waiting for review" is gone; the row shows "Block starts, lane 4" with its duration, and the
    // video drops off the list after POST /videos/{id}/annotations.
  });

  test.fixme("tournament-events.calendar shows a published tournament in the next four weeks", async () => {
    // sports/tournament-events (sprint batch #330, PR #388). A user holding tournament-events-admin (check that
    // org-admin does) POST /tournament-events/tournaments { name: "State Athletics Championship", discipline:
    // "Athletics", level: "state", format: "heats_and_finals", start_date: dayFromNow(7), end_date: dayFromNow(8),
    // venue: "City stadium", hosting: "away" } and POST /tournaments/{id}/publish. A draft must not appear.
    // Expect: "Nothing on the calendar" is gone; the calendar (today to dayFromNow(27)) shows the championship on its
    // dates with its venue.
  });

  test.fixme("facility-booking.bookings lists a booking made for later today", async () => {
    // facilities/facility-booking is enabled, but the layout's facility-booking.bookings is not exported (the module
    // exports facility-booking.bookings-today; sprint batch #331 builds or renames it). Then, as in
    // facility-staff.spec.ts: a resource type and a resource the coach manages, a booking later today
    // (POST /facility-booking/resource-types, /resources, /bookings), and expect its time window and resource name.
  });
});
