import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { OpenByCommittee, OpenByTrack } from "../src/api/client";
import { widgets } from "../src/widgets";
import { OpenByCommitteeWidget } from "../src/widgets/OpenByCommitteeWidget";
import { OpenWidget } from "../src/widgets/OpenWidget";
import { describeFailure, openLabel, overdueLabel, statusSummary } from "../src/widgets/shared";
import { GrievanceApiError } from "../src/api/client";

const byCommittee = (over: Partial<OpenByCommittee> = {}): OpenByCommittee => ({
  total_open: 3,
  committees: [
    {
      committee_id: "c1",
      name: "Campus SGRC",
      kind: "sgrc",
      open: 2,
      overdue: 1,
      by_status: [
        { status: "submitted", count: 1 },
        { status: "under_inquiry", count: 1 },
      ],
    },
    { committee_id: "c2", name: "ICC", kind: "icc", open: 1, overdue: 0, by_status: [{ status: "acknowledged", count: 1 }] },
    { committee_id: "c3", name: "Ombudsperson", kind: "ombudsperson", open: 0, overdue: 0, by_status: [] },
  ],
  ...over,
});

const byTrack = (over: Partial<OpenByTrack> = {}): OpenByTrack => ({
  total_open: 4,
  overdue: 1,
  tracks: [
    { track: "student_grievance", open: 3, overdue: 1 },
    { track: "ragging", open: 1, overdue: 0 },
    { track: "sexual_harassment", open: 0, overdue: 0 },
  ],
  ...over,
});

function answer(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({ ok: status < 400, status, statusText: "", json: async () => body });
}

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("grievance widgets", () => {
  it("are exported with the ids and permission the layouts and the contract expect", () => {
    const committee = widgets.find((w) => w.id === "grievance.open-by-committee");
    const open = widgets.find((w) => w.id === "grievance.open");
    expect(widgets).toHaveLength(2);
    expect(committee?.permission).toBe("grievance:stats:read");
    expect(committee?.component).toBe(OpenByCommitteeWidget);
    expect(open?.permission).toBe("grievance:stats:read");
    expect(open?.component).toBe(OpenWidget);
  });

  it("word counts and statuses", () => {
    expect(openLabel(1)).toBe("1 open case");
    expect(openLabel(3)).toBe("3 open cases");
    expect(overdueLabel(0)).toBe("None overdue");
    expect(overdueLabel(2)).toBe("2 overdue");
    expect(statusSummary([{ status: "appeal_decided", count: 2 }, { status: "submitted", count: 1 }])).toBe(
      "2 appeal decided · 1 submitted",
    );
  });

  it("says what went wrong without blaming the connection when the service is missing", () => {
    expect(describeFailure(new GrievanceApiError(503, ""), "x")).toEqual({
      title: "Grievance data is not available yet.",
      retry: true,
    });
    expect(describeFailure(new TypeError("Failed to fetch"), "x").retry).toBe(true);
    expect(describeFailure(new GrievanceApiError(401, ""), "x")).toMatchObject({ title: "Sign in again to see this.", retry: false });
    expect(describeFailure(new GrievanceApiError(403, ""), "x")).toMatchObject({ title: "You do not have access to this.", retry: false });
    expect(describeFailure(new GrievanceApiError(500, ""), "open grievances")).toMatchObject({
      title: "Could not load open grievances",
      retry: true,
    });
  });
});

describe("grievance.open-by-committee", () => {
  it("lists committees with their open and overdue counts from GET /stats/open-by-committee", async () => {
    const fetchMock = answer(200, byCommittee());
    vi.stubGlobal("fetch", fetchMock);
    render(<OpenByCommitteeWidget role="governance" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Campus SGRC")).toBeTruthy();
    expect(screen.getByText("3 open cases · 1 overdue")).toBeTruthy();
    expect(screen.getByText("2 open · 1 overdue")).toBeTruthy();
    expect(screen.getByText("1 open · None overdue")).toBeTruthy();
    expect(screen.getByText(/1 submitted · 1 under inquiry/)).toBeTruthy();
    expect(screen.getByRole("list", { name: "Open cases by committee" }).querySelectorAll("li")).toHaveLength(3);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/grievance/stats/open-by-committee");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("is empty before any committee exists", async () => {
    vi.stubGlobal("fetch", answer(200, byCommittee({ total_open: 0, committees: [] })));
    render(<OpenByCommitteeWidget role="governance" />);
    expect(await screen.findByText("No committees yet")).toBeTruthy();
  });

  it("offers a retry that loads again after a server error", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 500, statusText: "Server Error", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => byCommittee() });
    vi.stubGlobal("fetch", fetchMock);
    render(<OpenByCommitteeWidget role="governance" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load open grievances");
    fireEvent.click(screen.getByRole("button", { name: /retry|try again/i }));
    expect(await screen.findByText("Campus SGRC")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("says so, with no retry, when the caller may not see the counts", async () => {
    vi.stubGlobal("fetch", answer(403, {}));
    render(<OpenByCommitteeWidget role="governance" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("treats a network failure as not available yet", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<OpenByCommitteeWidget role="governance" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Grievance data is not available yet.");
  });
});

describe("grievance.open", () => {
  it("lists the tracks with their open and overdue counts from GET /stats/open", async () => {
    const fetchMock = answer(200, byTrack());
    vi.stubGlobal("fetch", fetchMock);
    render(<OpenWidget role="management" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Student grievances")).toBeTruthy();
    expect(screen.getByText("4 open cases · 1 overdue")).toBeTruthy();
    expect(screen.getByText("3 open")).toBeTruthy();
    expect(screen.getByText("Sexual harassment complaints")).toBeTruthy();
    expect(screen.getByRole("list", { name: "Open cases by track" }).querySelectorAll("li")).toHaveLength(3);
    expect((fetchMock.mock.calls[0] as [string])[0]).toBe("/api/v1/grievance/stats/open");
  });

  it("is empty when nothing is open", async () => {
    vi.stubGlobal("fetch", answer(200, byTrack({ total_open: 0, overdue: 0, tracks: [] })));
    render(<OpenWidget role="management" />);
    expect(await screen.findByText("No open cases")).toBeTruthy();
  });

  it("shows the error state with retry on a 500 and without it on a 401", async () => {
    vi.stubGlobal("fetch", answer(500, {}));
    render(<OpenWidget role="management" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load open grievances");
    expect(screen.getByRole("button", { name: /retry|try again/i })).toBeTruthy();
    cleanup();
    vi.stubGlobal("fetch", answer(401, {}));
    render(<OpenWidget role="management" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button")).toBeNull();
  });
});
