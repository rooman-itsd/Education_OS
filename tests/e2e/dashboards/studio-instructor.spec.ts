import { expect, test } from "@playwright/test";
import { addUser, organisationWithUser, type DashboardUser } from "./organisation";
import { created, expectBody, probe, shipped, signIn, standardPlan, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Studio Instructor dashboard (layout platform/identity/config/dashboards/studio-instructor.yaml, which extends the
 * Faculty layout; the role exists in the arts-academy profile, ADR-0004).
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a studio-instructor user signs in and lands on their dashboard;
 * - for every widget of the layout, the inherited Faculty ones included, whose module is in
 *   apps/frontend/config/modules.enabled.yaml: the panel renders by its registered title and shows its empty
 *   state, or says its data is not available while the backend is missing (the studio-instructor holds the faculty
 *   role's permissions through `extends`);
 * - widgets of modules not enabled yet are skipped, naming the module and the sprint batch that builds it;
 * - with facility-booking data: today's reservations for art studios appear in facility-booking.bookings-today;
 * - other downstream data journeys are fixme until practice modules merge.
 *
 * facilities, finance-operations and campus-life are not in the Trial plan, so the super admin moves the organisation
 * to Standard first. The empty-state tests run before any data is created (serial mode). Loading states are covered
 * by the modules' unit tests, not here.
 */

const TITLE = "Studio Instructor";

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
    unavailable: "No courses this term",
    forbidden: "Could not load your courses",
  },
  // The studio instructor's own widgets.
  {
    id: "portfolio.reviews-pending",
    module: "practice/portfolio",
    batch: "#322",
    title: "Reviews Pending",
    probe: "/portfolio/items?scope=managed&status=submitted,under_review",
    empty: "No reviews pending",
    unavailable: "Portfolio review data is not available yet.",
  },
  { id: "projects.to-review", module: "practice/projects", batch: "#339" },
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
    id: "facility-booking.bookings-today",
    module: "facilities/facility-booking",
    batch: "#287",
    title: "Bookings today",
    probe: "/facility-booking/summary",
    empty: "No bookings today",
    unavailable: "Facility booking data is not available yet.",
  },
  { id: "productions.in-preparation", module: "practice/productions", batch: "#318" },
];

const SHIPPED = WIDGETS.filter(shipped);
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;

let user: DashboardUser;
/** Per shipped widget id: what its GET answered the studio instructor user. */
const status: Record<string, number> = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  user = await organisationWithUser(request, {
    academyType: "arts-academy",
    role: "studio-instructor",
    extraRoles: ["facility-staff", "org-admin"],
  });
  await standardPlan(request, user.organisation.id);

  // Set up an active academic term so academic-management.course-roster (/me/offerings) finds an active term.
  const term = await created<{ id: string }>(request, user, "/academic-management/terms", {
    code: "2026-FALL",
    name: "Fall 2026",
    starts_on: "2026-09-01",
    ends_on: "2026-12-31",
  });
  await created(request, user, `/academic-management/terms/${term.id}/activate`, {});

  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a studio instructor signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("studio instructor widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the studio-instructor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, says its data is not available yet, or says the role has no access", async ({ page }) => {
    test.skip(SHIPPED.length === 0, "none of the studio-instructor layout's modules is in apps/frontend/config/modules.enabled.yaml yet");
    await signIn(page, user);
    for (const w of SHIPPED) await expectBody(page, w, status[w.id] ?? 0);
  });

  for (const w of WIDGETS.filter((w) => !shipped(w))) {
    test(`${w.id} renders once ${w.module} ships`, async ({ page }) => {
      test.skip(!shipped(w), waitingFor(w));
      await signIn(page, user);
      await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
      await expect(widget(page, w.id)).toHaveCount(0);
    });
  }
});

test.describe("with facility-booking data", () => {
  test("facility-booking.bookings-today lists today's studio reservation", async ({ page, request }) => {
    const w = byId("facility-booking.bookings-today");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(status[w.id] !== 200, `the facility-booking API answered ${status[w.id]} to the studio-instructor role`);

    const zone = process.env.FACILITY_BOOKING_TIMEZONE || "UTC";
    const day = (d: Date) => d.toLocaleDateString("en-CA", { timeZone: zone });
    const slot = 30 * 60_000;
    const start = new Date(Math.ceil((Date.now() + 5 * 60_000) / slot) * slot);
    const end = new Date(start.getTime() + slot);
    test.skip(day(end) !== day(new Date()), `too close to midnight in ${zone}`);

    const type = await created<{ id: string }>(request, user, "/facility-booking/resource-types", {
      name: "Painting Studio",
    });
    const resource = await created<{ id: string }>(request, user, "/facility-booking/resources", {
      name: "Studio 3 (Oil & Acrylic)",
      type_id: type.id,
      capacity: 25,
    });
    await created(request, user, "/facility-booking/bookings", {
      resource_id: resource.id,
      start_at: start.toISOString(),
      end_at: end.toISOString(),
      title: "Masterclass Demo",
    });

    await signIn(page, user);
    const panel = widget(page, "Bookings today");
    await expect(panel.getByText("Studio 3 (Oil & Acrylic) · Masterclass Demo")).toBeVisible();
    await expect(panel.getByLabel("Booking counts")).toContainText("1 today");
    await expect(panel.getByText("No bookings today")).toHaveCount(0);
  });
});

test.describe("with portfolio data", () => {
  test("portfolio.reviews-pending lists the artworks submitted for the instructor's review, and only those", async ({ page, request }) => {
    const w = byId("portfolio.reviews-pending");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(status[w.id] !== 200, `the portfolio API answered ${status[w.id]} to the studio-instructor role`);

    // The instructor holds org-admin here, so it can add the manager who configures item types and the artist who
    // submits. A reviewer sees items of the types that name them as a reviewer (contract: GET /items?scope=managed).
    const manager = await addUser(request, user, "portfolio-manager");
    const artist = await addUser(request, user, "artist");
    const critique = await created<{ id: string }>(request, manager, "/portfolio/item-types", {
      name: "Studio Critique",
      reviewer_person_ids: [user.id],
    });
    const otherType = await created<{ id: string }>(request, manager, "/portfolio/item-types", { name: "Thesis Show Piece" });

    const submitted = await created<{ id: string }>(request, artist, "/portfolio/items", {
      type_id: critique.id,
      title: "Still Life with Pomegranates",
    });
    await created(request, artist, `/portfolio/items/${submitted.id}/submit`, {});
    // Still a draft: nothing to review yet.
    await created(request, artist, "/portfolio/items", { type_id: critique.id, title: "Unfinished Landscape" });
    // Submitted, but of a type the instructor does not review.
    const notMine = await created<{ id: string }>(request, artist, "/portfolio/items", {
      type_id: otherType.id,
      title: "Gallery Wall Proposal",
    });
    await created(request, artist, `/portfolio/items/${notMine.id}/submit`, {});

    await signIn(page, user);
    const panel = widget(page, w.title!);
    await expect(panel.getByText("Still Life with Pomegranates")).toBeVisible();
    await expect(panel.getByText("Awaiting Review", { exact: true })).toBeVisible();
    await expect(panel.getByText(w.empty!)).toHaveCount(0);
    await expect(panel.getByText("Unfinished Landscape")).toHaveCount(0);
    await expect(panel.getByText("Gallery Wall Proposal")).toHaveCount(0);
  });
});

test.describe("with selection-process data", () => {
  test("selection-process.to-judge lists the candidates of the instructor's panels awaiting a decision, and only those", async ({ page, request }) => {
    const w = byId("selection-process.to-judge");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(status[w.id] !== 200, `the selection-process API answered ${status[w.id]} to the studio-instructor role`);

    // A coordinator runs the processes; the instructor judges only on the panels that name them (studio-instructor
    // holds selection-process-panelist through module_roles). Candidates are people, here an applicant and a student.
    const coordinator = await addUser(request, user, "selection-process-coordinator");
    const onPanel = await addUser(request, user, "applicant");
    const elsewhere = await addUser(request, user, "student");
    const type = await created<{ id: string }>(request, coordinator, "/selection-process/process-types", { name: "Jury" });

    const openProcess = async (title: string, panelists: string[]) => {
      const p = await created<{ id: string }>(request, coordinator, "/selection-process/processes", {
        type_id: type.id,
        title,
        stages: [{ name: "Portfolio review", sequence: 1 }],
      });
      await created(request, coordinator, `/selection-process/processes/${p.id}/panels`, {
        name: `${title} panel`,
        member_person_ids: panelists,
      });
      await created(request, coordinator, `/selection-process/processes/${p.id}/open`, {});
      return p;
    };
    const judged = await openProcess("Annual Jury 2026", [user.id]);
    const other = await openProcess("Residency Selection 2026", [coordinator.id]);
    await created(request, coordinator, `/selection-process/processes/${judged.id}/candidates`, { person_id: onPanel.id });
    await created(request, coordinator, `/selection-process/processes/${other.id}/candidates`, { person_id: elsewhere.id });

    await signIn(page, user);
    const panel = widget(page, w.title!);
    await expect(panel.getByText(`Candidate #${onPanel.id.slice(0, 8)}`)).toBeVisible();
    await expect(panel.getByText("Pending Decision", { exact: true })).toBeVisible();
    await expect(panel.getByText(w.empty!)).toHaveCount(0);
    await expect(panel.getByText(`Candidate #${elsewhere.id.slice(0, 8)}`)).toHaveCount(0);
  });
});

// Backend-dependent: these need their module's API to create data through once the modules are merged.

test.fixme("projects.to-review lists studio projects submitted for evaluation", async () => {
  // practice/projects (sprint batch #339).
});

test.fixme("productions.in-preparation lists stage productions or gallery exhibitions in preparation", async () => {
  // practice/productions (sprint batch #318).
});
