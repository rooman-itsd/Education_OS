import { expect, test } from "@playwright/test";
import { organisationWithUser, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Medical Staff (Doctor / Physio) dashboard (layout platform/identity/config/dashboards/medical-staff.yaml; the role
 * exists in the sports-college profile).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a medical-staff user signs in and lands on their dashboard;
 * - for every widget whose module is in apps/frontend/config/modules.enabled.yaml: the panel renders by its
 *   registered title and shows its empty state, or says its data is not available while the backend is missing;
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it;
 *   facility-booking is enabled but exports facility-booking.bookings-today, not the facility-booking.bookings the
 *   layout lists, so that widget skips until sprint batch #331;
 * - the data journeys are fixme: each needs a sports module enabled, and sports-nutrition-health learns athletes
 *   only from the athlete-performance.athlete.registered event.
 *
 * The sports suite is the profile's one specialized suite, so Trial includes it; facilities is not in Trial, so the
 * super admin moves the organisation to Standard first. The empty-state tests run before any data is created
 * (serial mode). Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Medical Staff (Doctor / Physio)";

const WIDGETS: LayoutWidget[] = [
  {
    id: "sports-nutrition-health.injured-athletes",
    module: "sports/sports-nutrition-health",
    batch: "#330",
    title: "Injured athletes",
    probe: "/sports-nutrition-health/injuries?status=active&limit=200",
    empty: "No injured athletes",
    unavailable: "Nutrition and health data is not available yet.",
  },
  {
    id: "sports-nutrition-health.appointments-today",
    module: "sports/sports-nutrition-health",
    batch: "#330",
    title: "Appointments today",
    probe: "/sports-nutrition-health/appointments?limit=1",
    empty: "No appointments today",
    unavailable: "Nutrition and health data is not available yet.",
  },
  {
    id: "athlete-performance.fitness-clearances",
    module: "sports/athlete-performance",
    batch: "#330",
    title: "Fitness clearances",
    probe: "/athlete-performance/reports/clearances",
    empty: "No athletes yet",
    unavailable: "Athlete performance data is not available yet.",
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
];
const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the medical-staff user. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  user = await organisationWithUser(request, { academyType: "sports-college", role: "medical-staff" });
  await standardPlan(request, user.organisation.id);
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a medical staff member signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("medical-staff widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the medical-staff layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the medical-staff layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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

// Backend-dependent: these need their module's API to create the data through, so nothing here is faked. Each needs
// its module in both modules.enabled.yaml files; write them as the finance-staff data journeys are written then.
// Every one starts from an athlete registered in athlete-performance: set up with organisationAdmin + addUser, as the
// org admin POST /athlete-performance/disciplines and, as a coach, POST /athlete-performance/athletes
// { full_name: "Asha Rao", primary_discipline_id, status: "active" }. sports-nutrition-health accepts that athlete id
// only once the athlete-performance.athlete.registered event has reached it through platform/event-bus.
test.describe("with sports data", () => {
  test.fixme("sports-nutrition-health.injured-athletes lists an athlete with an active injury", async () => {
    // sports/sports-nutrition-health (sprint batch #330, PR #389). As the medical-staff user (injury:write through
    // sports-nutrition-health-medical) POST /sports-nutrition-health/injuries { athlete_id, body_part: "Left hamstring",
    // injury_type: "Grade 1 strain", severity: "moderate", occurred_on: dayFromNow(-2), context: "training",
    // status: "active", expected_return_on: dayFromNow(12) }. A resolved injury for a second athlete must not count.
    // Expect: "No injured athletes" is gone; one row, "Asha Rao", "Left hamstring", moderate, back in 12 days.
  });

  test.fixme("sports-nutrition-health.appointments-today lists an appointment later today", async () => {
    // As the medical-staff user (appointment:write) POST /sports-nutrition-health/appointments { athlete_id,
    // practitioner_id: <medical-staff user id>, appointment_type: "physiotherapy", scheduled_at: <today, an hour from
    // now, UTC>, duration_minutes: 45, status: "scheduled" }, and one tomorrow that must not show.
    // Expect: "No appointments today" is gone; one row with the time, "Asha Rao" and "Physiotherapy".
  });

  test.fixme("athlete-performance.fitness-clearances flags a clearance that lapses in 5 days", async () => {
    // sports/athlete-performance (sprint batch #330, PR #385). As the medical-staff user (clearance:write through the
    // medical-staff profile role) PUT /athlete-performance/athletes/{id}/clearance { status: "cleared",
    // valid_until: dayFromNow(5) }; a second athlete cleared until dayFromNow(90) and a third "not_cleared".
    // Expect: "No athletes yet" is gone; the counts show cleared, restricted and not cleared, and "Asha Rao" is listed
    // as lapsing in 5 days.
  });
});
