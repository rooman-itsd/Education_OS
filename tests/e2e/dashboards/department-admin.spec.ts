import { expect, test } from "@playwright/test";
import { addUser, organisationAdmin, type DashboardUser } from "./organisation";
import { created, expectBody, probe, shipped, signIn, waitingFor, widget, type LayoutWidget } from "./widgets";

/**
 * Department Admin / HoD dashboard (issue #318; layout platform/identity/config/dashboards/department-admin.yaml).
 * The role exists in every academy profile; this journey uses an engineering college.
 *
 * What runs depends on what has shipped; each skip says what it waits for:
 * - always: a department-admin user signs in and lands on their dashboard;
 * - for every widget whose module is enabled and exports it: the panel renders by its registered title and shows
 *   its empty state, or says its data is not available while the backend is missing;
 * - widgets of modules not enabled or not built yet are skipped, naming the module and the sprint batch.
 *
 * Two of the five widgets are somebody else's build, #325: timetable-attendance.department-attendance and
 * examinations.results-summary (neither exists yet). academic-management.faculty-load shipped in #466 and is
 * checked like any shipped widget; workflow.approvals-pending and reporting.department-reports exist but their
 * platform services stay disabled until the remediation PRs of #317 merge. Until then this spec asserts the layout and
 * the sign-in, and each skip names what is missing — which is the point: it fails the day one of them ships
 * broken, rather than silently passing.
 *
 * Loading states are covered by the modules' unit tests, not here. Permission-based hiding is not covered:
 * apps/frontend/src/App.tsx passes permissions="all" to the dashboard for now, so a widget whose API refuses
 * the role renders with the module's "no access" wording instead of hiding.
 */

const TITLE = "Department Admin / HoD";

const WIDGETS: LayoutWidget[] = [
  {
    id: "workflow.approvals-pending",
    module: "platform/workflow",
    batch: "#317",
    title: "Approvals pending",
    probe: "/workflow/requests/pending?limit=8",
    empty: "No pending approvals",
    unavailable: "Workflow data is not available yet.",
  },
  {
    // Texts of FacultyLoad.tsx (academic-management, merged in #466). A new organisation has no active term:
    // GET /faculty-load answers 404 active_term_not_found, which the widget's client turns into "No active term".
    id: "academic-management.faculty-load",
    module: "academics/academic-management",
    batch: "#466",
    title: "Faculty load",
    probe: "/academic-management/faculty-load",
    empty: "No active term",
    emptyCode: "active_term_not_found",
    unavailable: "No active term",
    forbidden: "You do not have access to faculty load.",
  },
  { id: "timetable-attendance.department-attendance", module: "academics/timetable-attendance", batch: "#325" },
  { id: "examinations.results-summary", module: "academics/examinations", batch: "#325" },
  {
    id: "reporting.department-reports",
    module: "platform/reporting",
    batch: "#317",
    title: "Department Reports",
    probe: "/reporting/widgets/department-reports",
    empty: "No department reports",
    unavailable: "Reporting service is not available yet.",
  },
];
const SHIPPED = WIDGETS.filter(shipped);

let admin: DashboardUser;
let user: DashboardUser;
/** Per shipped widget id: what its GET answered the department-admin user. */
const status: Record<string, number> = {};
const byId = (id: string) => WIDGETS.find((w) => w.id === id)!;
const ready = (id: string) => (status[id] ?? 0) === 200;

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  admin = await organisationAdmin(request, { academyType: "engineering-college" });
  user = await addUser(request, admin, "department-admin");
  for (const w of SHIPPED) status[w.id] = await probe(request, user, w);
});

test(`a department admin signs in and lands on the ${TITLE} dashboard`, async ({ page }) => {
  await signIn(page, user);
  await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
  await expect(page.getByText(`${user.organisation.name} · ${TITLE} dashboard`)).toBeVisible();
  await expect(page.getByText("Preview mode")).toHaveCount(0);
});

test.describe("department admin widgets", () => {
  test("every shipped widget renders by its registered title", async ({ page }) => {
    test.skip(
      SHIPPED.length === 0,
      "none of the department-admin layout's modules is enabled and exporting its widget yet",
    );
    await signIn(page, user);
    const dashboard = page.getByRole("region", { name: `${TITLE} dashboard` });
    for (const w of SHIPPED) await expect(dashboard.getByRole("heading", { name: w.title!, exact: true })).toBeVisible();
  });

  test("each shipped widget shows its empty state, or says its data is not available yet", async ({ page }) => {
    test.skip(
      SHIPPED.length === 0,
      "none of the department-admin layout's modules is enabled and exporting its widget yet",
    );
    await signIn(page, user);
    for (const w of SHIPPED) await expectBody(page, w, status[w.id] ?? 0);
  });

  for (const w of WIDGETS.filter((x) => !shipped(x))) {
    test(`${w.id} renders once ${w.module} ships`, async ({ page }) => {
      test.skip(!shipped(w), waitingFor(w));
      // The shell renders an unregistered id as a "Not built yet" placeholder titled with the id itself.
      await signIn(page, user);
      await expect(page.getByRole("region", { name: `${TITLE} dashboard` })).toBeVisible();
      await expect(widget(page, w.id)).toHaveCount(0);
    });
  }
});

test.describe("with workflow and reporting data", () => {
  test("workflow.approvals-pending lists a request waiting for this head of department", async ({ page, request }) => {
    const w = byId("workflow.approvals-pending");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the workflow API answered ${status[w.id]} to the department-admin role`);

    // Org admin configures a simple approval chain where step 1 is assigned to department-admin
    const chainCode = "hod-syllabus-approval";
    const createChain = await request.post("/api/v1/workflow/chains", {
      headers: { Authorization: `Bearer ${admin.token}` },
      data: {
        code: chainCode,
        title: "Syllabus Review Chain",
        description: "Departmental syllabus approval process",
        steps: [
          {
            step_order: 1,
            name: "HoD Approval",
            approver_role: "department-admin",
            is_final: true,
          },
        ],
      },
    });
    expect([201, 409]).toContain(createChain.status());

    // Submit a request into the chain waiting for this department admin
    const reqTitle = "CS101 Syllabus Revision";
    await created(request, admin, "/workflow/requests", {
      chain_code: chainCode,
      entity_type: "syllabus",
      entity_id: "cs-101",
      title: reqTitle,
      description: "Semester 1 syllabus update awaiting HoD sign-off",
    });

    await signIn(page, user);
    const panel = widget(page, w.title!);
    await expect(panel.getByText("No pending approvals")).toHaveCount(0);
    await expect(panel.getByText(reqTitle)).toBeVisible();
    await expect(panel.getByText(/Syllabus ·/)).toBeVisible();
  });

  test("reporting.department-reports lists the academic reports the head of department may run", async ({ page, request }) => {
    const w = byId("reporting.department-reports");
    test.skip(!shipped(w), waitingFor(w));
    test.skip(!ready(w.id), `the reporting API answered ${status[w.id]} to the department-admin role`);

    // Query standard report definitions as admin
    const defsRes = await request.get("/api/v1/reporting/definitions", {
      headers: { Authorization: `Bearer ${admin.token}` },
    });
    expect(defsRes.ok(), await defsRes.text()).toBeTruthy();
    const defs = (await defsRes.json()) as Array<{ id: string; code: string; name: string; category: string }>;

    // Find the standard academic department attendance report definition
    const academicDef = defs.find((d) => d.code === "department-attendance") ?? defs.find((d) => d.category === "academic");
    expect(academicDef, "standard academic report definition must be available").toBeDefined();

    // Execute the academic report
    const runRes = await request.post(`/api/v1/reporting/definitions/${academicDef!.id}/run`, {
      headers: { Authorization: `Bearer ${admin.token}` },
      data: {},
    });
    expect(runRes.ok(), await runRes.text()).toBeTruthy();

    await signIn(page, user);
    const panel = widget(page, w.title!);
    await expect(panel.getByText("No department reports")).toHaveCount(0);
    await expect(panel.getByText(academicDef!.name)).toBeVisible();
  });
});

test.fixme("academic-management.faculty-load shows the teaching load of the department's faculty", async () => {
  // modules/academics/academic-management (#466). Needs an active term, offerings and faculty assignments; the
  // widget's own tests cover the list, this journey covers the empty and "no active term" states.
});

test.fixme("timetable-attendance.department-attendance shows this week's attendance for the department", async () => {
  // modules/academics/timetable-attendance (sprint batch #325); the module is a scaffold today.
});

test.fixme("examinations.results-summary shows the department's pass rate for the last session", async () => {
  // modules/academics/examinations (sprint batch #325); the module has widgets but no backend.
});
