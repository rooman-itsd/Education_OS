import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, dayFromNow, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

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
 *   facility-booking.bookings (upcoming bookings on the resources the coach approves) is checked by its empty state,
 *   then by a booking facility staff make on a track the coach approves;
 *   athlete-performance.session-plan and wearables.alerts are not built in v1 (see NOT_BUILT);
 * - the sports data journeys are fixme: each needs a sports module enabled, and the coach's scoping in
 *   tournament-events and training-video-analysis needs the athlete-performance.athlete.registered event.
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
  {
    id: "lms.assignments-to-grade",
    module: "academics/lms",
    batch: "#326",
    title: "Assignments to grade",
    probe: "/lms/me/grading-queue",
    empty: "Nothing waiting to be graded",
    unavailable: "Course data is not available yet.",
  },

  { id: "examinations.exam-duties", module: "academics/examinations", batch: "#325" },
  {
    id: "academic-management.course-roster",
    module: "academics/academic-management",
    batch: "#100",
    title: "Course roster",
    probe: "/academic-management/me/offerings",
    empty: "No courses this term",
    // No active term: academic-management answers 404 active_term_not_found, which the widget shows as nothing this term.
    emptyCode: "active_term_not_found",
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
    id: "facility-booking.bookings",
    module: "facilities/facility-booking",
    batch: "#331",
    title: "Upcoming bookings",
    probe: "/facility-booking/bookings?scope=managed&from=now&status=pending,confirmed,checked_in&page_size=6",
    empty: "No upcoming bookings",
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
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let admin: DashboardUser;
let user: DashboardUser;
/** Facility staff: they run the resource register, so they set up the track the coach approves. */
let facilityStaff: DashboardUser;
/** Per shipped widget id: what its GET answered the coach. */
const status: Record<string, number> = {};
const ready = (id: string) => shipped(byId(id)) && status[id] === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "sports-college" });
  await standardPlan(request, admin.organisation.id);
  user = await addUser(request, admin, "coach");
  facilityStaff = await addUser(request, admin, "facility-staff");
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

});

test.describe("with facility data", () => {
  test("facility-booking.bookings lists a booking later today on a track the coach approves", async ({ page, request }) => {
    const w = byId("facility-booking.bookings");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the facility-booking API answered ${status[w.id]} to the coach role`);
    // As in facility-staff.spec.ts: the default slot grid is 30 minutes and "today" is the organisation's date in
    // FACILITY_BOOKING_TIMEZONE (UTC by default; the API inherits this process's environment), so book the next free
    // half hour, unless that runs past midnight in that zone. The coach sees bookings on the resources whose
    // approvers list them (scope=managed).
    const zone = process.env.FACILITY_BOOKING_TIMEZONE || "UTC";
    const day = (d: Date) => d.toLocaleDateString("en-CA", { timeZone: zone }); // YYYY-MM-DD
    const slot = 30 * 60_000;
    const start = new Date(Math.ceil((Date.now() + 5 * 60_000) / slot) * slot);
    const end = new Date(start.getTime() + slot);
    test.skip(day(end) !== day(new Date()), `too close to midnight in ${zone}`);
    const type = await created<{ id: string }>(request, facilityStaff, "/facility-booking/resource-types", { name: "Track" });
    const resource = await created<{ id: string }>(request, facilityStaff, "/facility-booking/resources", {
      name: "Athletics track",
      type_id: type.id,
      capacity: 30,
      approver_user_ids: [user.id],
    });
    await created(request, facilityStaff, "/facility-booking/bookings", {
      resource_id: resource.id,
      start_at: start.toISOString(),
      end_at: end.toISOString(),
      title: "Sprint session",
    });
    await signIn(page, user);
    const panel = widget(page, "Upcoming bookings");
    await expect(panel.getByText("No upcoming bookings")).toHaveCount(0);
    await expect(panel.getByText("Athletics track · Sprint session")).toBeVisible();
  });
});
