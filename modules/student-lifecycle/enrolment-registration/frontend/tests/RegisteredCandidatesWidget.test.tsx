import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RegisteredCandidatesReport } from "../src/api/client";
import { widgets } from "../src/widgets";
import { RegisteredCandidatesWidget } from "../src/widgets/RegisteredCandidatesWidget";

const report = (over: Partial<RegisteredCandidatesReport> = {}): RegisteredCandidatesReport => ({
  academic_period_id: "t-1",
  term_name: "Term 1 2026",
  total: 1240,
  by_type: { regular: 1216, supplementary: 18, backlog: 6 },
  offerings: [
    { course_offering_id: "off-1", course_code: "CS101", course_title: "Programming I", registered: 42 },
    { course_offering_id: "3f2a9c7e-0000-4000-8000-000000000000", course_code: null, course_title: null, registered: 30 },
  ],
  ...over,
});

function api(body: unknown, status = 200) {
  return vi.fn().mockImplementation(async () => ({ ok: status < 400, status, statusText: "", json: async () => body }));
}

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("enrolment-registration.registered-candidates", () => {
  it("is exported with the id, permission, kind and size the Examination Staff layout and the contract expect", () => {
    expect(widgets).toHaveLength(1);
    expect(widgets[0]).toMatchObject({
      id: "enrolment-registration.registered-candidates",
      permission: "enrolment-registration:registration:read",
      kind: "list",
      size: "1x1",
      component: RegisteredCandidatesWidget,
    });
  });

  it("shows the total, the term, supplementary and backlog counts, and the busiest offerings", async () => {
    const fetchMock = api(report());
    vi.stubGlobal("fetch", fetchMock);
    render(<RegisteredCandidatesWidget role="examination-staff" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    const summary = await screen.findByLabelText("Registered candidates summary");
    expect(summary.textContent).toBe("1,240 registered · Term 1 2026 · 18 supplementary · 6 backlog");
    const rows = screen.getAllByRole("listitem");
    expect(rows[0]?.textContent).toContain("CS101 · Programming I");
    expect(rows[0]?.textContent).toContain("42 registered");
    expect(rows[1]?.textContent).toContain("Course offering 3f2a9c7e");
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe("/api/v1/enrolment-registration/reports/registered-candidates?limit=5");
    expect((fetchMock.mock.calls[0]?.[1] as { headers: Record<string, string> }).headers.Authorization).toBe("Bearer test-token");
  });

  it("says all terms while no term is known, and leaves out zero supplementary and backlog", async () => {
    vi.stubGlobal(
      "fetch",
      api(report({ academic_period_id: null, term_name: null, total: 3, by_type: { regular: 3, supplementary: 0, backlog: 0 } })),
    );
    render(<RegisteredCandidatesWidget role="examination-staff" />);
    expect((await screen.findByLabelText("Registered candidates summary")).textContent).toBe("3 registered · all terms");
  });

  it("has an empty state", async () => {
    vi.stubGlobal("fetch", api(report({ total: 0, offerings: [], by_type: { regular: 0, supplementary: 0, backlog: 0 } })));
    render(<RegisteredCandidatesWidget role="examination-staff" />);
    expect(await screen.findByText("No registered candidates yet")).toBeTruthy();
  });

  it("does not offer a retry that cannot help (403)", async () => {
    vi.stubGlobal("fetch", api({}, 403));
    render(<RegisteredCandidatesWidget role="examination-staff" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("retries when the service is not available yet", async () => {
    const fetchMock = api({}, 503);
    vi.stubGlobal("fetch", fetchMock);
    render(<RegisteredCandidatesWidget role="examination-staff" />);
    expect(await screen.findByText("Enrolment data is not available yet.")).toBeTruthy();
    fetchMock.mockImplementation(async () => ({ ok: true, status: 200, statusText: "", json: async () => report() }));
    fireEvent.click(screen.getByRole("button"));
    expect(await screen.findByLabelText("Registered candidates summary")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
