import { expect, test } from "@playwright/test";
import { organisationWithUser, type DashboardUser } from "./organisation";
import { expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Dancer dashboard (layout platform/identity/config/dashboards/dancer.yaml, which extends the Student layout; the role
 * exists in the dance-academy profile). Issue #333.
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a dancer signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Student ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml and exports it: the panel renders by its registered title and shows its
 *   empty state, or says its data is not available while the backend is missing (the dancer holds the student role's
 *   permissions through `extends`);
 * - widgets of modules not enabled yet, or not exported yet, are skipped, naming the module and the sprint batch that
 *   builds it: skill-progress (#329), productions (#318), selection-process (#322, PR #414), facility-booking.my-bookings
 *   (#331, PR #395) and timetable-attendance (#325);
 * - no data journey yet: inventory-equipment.my-loans needs a loan handed out to the dancer, and the other widgets
 *   wait for their modules.
 *
 * facilities, finance-operations and campus-life are not in the Trial plan (platform/billing/config/plans.yaml), so the
 * super admin moves the organisation to Standard first. The empty-state tests run before any data is created (serial
 * mode). Loading states are covered by the modules' unit tests, not here.
 */

const TITLE = "Dancer";

const WIDGETS: LayoutWidget[] = [
  // Inherited from the Student layout (extends: student). timetable-attendance.today is listed by both layouts.
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
  { id: "transport.notices", module: "campus-life/transport", batch: "#338" },
  { id: "library.loans", module: "campus-life/library", batch: "#338" },
  // The dancer's own widgets.
  { id: "skill-progress.my-progress", module: "practice/skill-progress", batch: "#329" },
  { id: "productions.my-roles", module: "practice/productions", batch: "#318" },
  {
    // Texts of UpcomingWidget.tsx in PR #414 (feat/selection-process/module-build), not merged yet.
    id: "selection-process.upcoming",
    module: "practice/selection-process",
    batch: "#322",
    title: "Upcoming Selection Events",
    probe: "/selection-process/slots/upcoming?limit=6",
    empty: "No upcoming selection rounds",
    unavailable: "Schedule data is not available yet.",
  },
  {
    // Texts of MyBookingsWidget.tsx and UpcomingBookings.tsx in PR #395 (feat/facility-booking/bookings-widgets).
    id: "facility-booking.my-bookings",
    module: "facilities/facility-booking",
    batch: "#331",
    title: "My bookings",
    probe: "/facility-booking/bookings?scope=mine&from=now&status=pending,confirmed,checked_in&page_size=6",
    empty: "No upcoming bookings",
    unavailable: "Booking data is not available yet.",
  },
  {
    id: "inventory-equipment.my-loans",
    module: "facilities/inventory-equipment",
    batch: "#331",
    title: "My loans",
    probe: "/inventory-equipment/loans?scope=mine&open=true&page_size=50",
    empty: "Nothing on loan",
    unavailable: "Inventory data is not available yet.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the dancer. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  user = await organisationWithUser(request, { academyType: "dance-academy", role: "dancer" });
  await standardPlan(request, user.organisation.id);
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a dancer signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("dancer widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the dancer layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the dancer layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
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
