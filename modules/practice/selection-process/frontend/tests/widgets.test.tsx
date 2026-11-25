import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Candidate, CandidatePage, Process, ProcessPage, Slot } from "../src/api/client";
import { widgets } from "../src/widgets";
import { MyApplicationsWidget } from "../src/widgets/MyApplicationsWidget";
import { OpenCallsWidget } from "../src/widgets/OpenCallsWidget";
import { ToJudgeWidget } from "../src/widgets/ToJudgeWidget";
import { UpcomingWidget } from "../src/widgets/UpcomingWidget";

const proc = (over: Partial<Process> = {}): Process => ({
  id: "proc-1",
  organisation_id: "o-1",
  type_id: "t-1",
  title: "Lead Role Audition 2026",
  status: "open",
  stages: [],
  panels: [],
  candidate_count: 0,
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
  ...over,
});

const cand = (over: Partial<Candidate> = {}): Candidate => ({
  id: "c1234567-aaaa",
  process_id: "proc-1",
  organisation_id: "o-1",
  person_id: "pe123456-bbbb",
  status: "registered",
  decisions: [],
  registered_at: "2026-11-02T10:00:00Z",
  ...over,
});

const procPage = (items: Process[]): ProcessPage => ({ items, total: items.length, page: 1, page_size: 5 });
const candPage = (items: Candidate[]): CandidatePage => ({ items, total: items.length, page: 1, page_size: 5 });

type Route = { match: string; body: unknown; status?: number };
/** A fetch that answers by URL substring, first match wins; unmatched URLs are 404. */
function routes(rs: Route[]) {
  return vi.fn().mockImplementation(async (url: string) => {
    const r = rs.find((x) => String(url).includes(x.match));
    const status = r ? (r.status ?? 200) : 404;
    return { ok: status < 400, status, statusText: "", json: async () => r?.body };
  });
}
const api = (body: unknown, status = 200) => routes([{ match: "/", body, status }]);
const urls = (m: ReturnType<typeof vi.fn>) => m.mock.calls.map((c) => String(c[0]));

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("selection-process widgets export", () => {
  it("exports the ids, permissions, kind and size the dashboards and the contract expect", () => {
    expect(widgets.map((w) => [w.id, w.permission])).toEqual([
      ["selection-process.my-applications", "selection-process:candidate:read"],
      ["selection-process.open-calls", "selection-process:process:read"],
      ["selection-process.to-judge", "selection-process:decision:write"],
      ["selection-process.upcoming", "selection-process:candidate:read"],
    ]);
    for (const w of widgets) expect(w).toMatchObject({ kind: "list", size: "1x1" });
    expect(widgets.map((w) => w.component)).toEqual([MyApplicationsWidget, OpenCallsWidget, ToJudgeWidget, UpcomingWidget]);
  });
});

describe("selection-process.open-calls", () => {
  it("lists open processes with stage and candidate counts, singular and plural", async () => {
    const fetchMock = api(
      procPage([
        proc({ stages: [{ id: "s1", process_id: "proc-1", name: "Round 1", sequence: 1 }], candidate_count: 1 }),
        proc({ id: "proc-2", title: "Squad Trials", stages: [], candidate_count: 12 }),
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<OpenCallsWidget role="research-office" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    const rows = await screen.findAllByRole("listitem");
    expect(rows[0]?.textContent).toContain("Lead Role Audition 2026");
    expect(rows[0]?.textContent).toContain("1 stage • 1 candidate");
    expect(rows[0]?.textContent).toContain("Open");
    expect(rows[1]?.textContent).toContain("0 stages • 12 candidates");
    expect(urls(fetchMock)[0]).toBe("/api/v1/selection-process/processes?status=open&page_size=6");
    expect((fetchMock.mock.calls[0]?.[1] as { headers: Record<string, string> }).headers.Authorization).toBe("Bearer test-token");
  });

  it("has an empty state", async () => {
    vi.stubGlobal("fetch", api(procPage([])));
    render(<OpenCallsWidget role="research-office" />);
    expect(await screen.findByText("No open calls right now")).toBeTruthy();
  });

  it("does not offer a retry on 403, and retries when unavailable", async () => {
    vi.stubGlobal("fetch", api({}, 403));
    render(<OpenCallsWidget role="research-office" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
    cleanup();
    const fetchMock = api({}, 503);
    vi.stubGlobal("fetch", fetchMock);
    render(<OpenCallsWidget role="research-office" />);
    expect(await screen.findByText("Open calls are not available yet.")).toBeTruthy();
    fetchMock.mockImplementation(async () => ({ ok: true, status: 200, statusText: "", json: async () => procPage([proc()]) }));
    fireEvent.click(screen.getByRole("button"));
    expect(await screen.findByText("Lead Role Audition 2026")).toBeTruthy();
  });
});

describe("selection-process.my-applications", () => {
  it("collects my candidacies across open processes, with a status badge", async () => {
    const fetchMock = routes([
      { match: "/processes/proc-1/candidates", body: candPage([cand({ status: "selected" })]) },
      { match: "/processes/proc-2/candidates", body: candPage([cand({ id: "d7654321-cccc", status: "waitlisted" })]) },
      { match: "/processes?", body: procPage([proc(), proc({ id: "proc-2" })]) },
    ]);
    vi.stubGlobal("fetch", fetchMock);
    render(<MyApplicationsWidget role="research-scholar" />);
    const rows = await screen.findAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.textContent).toContain("Application #c1234567");
    expect(rows[0]?.textContent).toContain("Selected");
    expect(rows[1]?.textContent).toContain("Waitlisted");
    expect(urls(fetchMock)).toContain("/api/v1/selection-process/processes/proc-1/candidates?scope=mine&page_size=5");
  });

  it("skips a process whose candidacies cannot be read instead of failing the widget", async () => {
    vi.stubGlobal(
      "fetch",
      routes([
        { match: "/processes/proc-1/candidates", body: {}, status: 403 },
        { match: "/processes/proc-2/candidates", body: candPage([cand({ status: "rejected" })]) },
        { match: "/processes?", body: procPage([proc(), proc({ id: "proc-2" })]) },
      ]),
    );
    render(<MyApplicationsWidget role="research-scholar" />);
    const rows = await screen.findAllByRole("listitem");
    expect(rows).toHaveLength(1);
    expect(rows[0]?.textContent).toContain("Not Selected");
  });

  it("has an empty state when there is no open process, and an error when processes cannot be listed", async () => {
    vi.stubGlobal("fetch", api(procPage([])));
    render(<MyApplicationsWidget role="research-scholar" />);
    expect(await screen.findByText("No active applications")).toBeTruthy();
    cleanup();
    vi.stubGlobal("fetch", api({}, 401));
    render(<MyApplicationsWidget role="research-scholar" />);
    expect(await screen.findByText("Sign in again to see this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("selection-process.to-judge", () => {
  it("lists candidates awaiting a decision from the managed scope of each open process", async () => {
    const fetchMock = routes([
      {
        match: "/processes/proc-1/candidates",
        body: candPage([cand({ status: "in_progress", current_stage_id: "st123456-dddd" }), cand({ id: "x", person_id: "zz999999-eeee" })]),
      },
      { match: "/processes?", body: procPage([proc()]) },
    ]);
    vi.stubGlobal("fetch", fetchMock);
    render(<ToJudgeWidget role="design-mentor" />);
    const rows = await screen.findAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.textContent).toContain("Candidate #pe123456");
    expect(rows[0]?.textContent).toContain("Stage: st123456");
    expect(rows[0]?.textContent).toContain("Pending Decision");
    expect(rows[1]?.textContent).toContain("Stage: Pending");
    expect(urls(fetchMock)).toContain(
      "/api/v1/selection-process/processes/proc-1/candidates?scope=managed&status=registered,in_progress&page_size=5",
    );
  });

  it("ignores processes the judge is not on, and has an empty state", async () => {
    vi.stubGlobal(
      "fetch",
      routes([
        { match: "/candidates", body: {}, status: 403 },
        { match: "/processes?", body: procPage([proc()]) },
      ]),
    );
    render(<ToJudgeWidget role="design-mentor" />);
    expect(await screen.findByText("No candidates awaiting review")).toBeTruthy();
  });

  it("shows an error with a retry when the service is not available", async () => {
    vi.stubGlobal("fetch", api({}, 502));
    render(<ToJudgeWidget role="design-mentor" />);
    expect(await screen.findByText("Judging tasks are not available yet.")).toBeTruthy();
    expect(screen.getByRole("button")).toBeTruthy();
  });
});

describe("selection-process.upcoming", () => {
  const slot = (over: Partial<Slot> = {}): Slot => ({
    id: "sl-1",
    process_id: "proc-1",
    title: "Jury round",
    starts_at: "2026-12-05T09:30:00Z",
    ends_at: "2026-12-05T10:30:00Z",
    status: "scheduled",
    location: "Studio 2",
    ...over,
  });

  it("lists upcoming slots with date, time and location when there is one", async () => {
    const fetchMock = api([slot(), slot({ id: "sl-2", title: "Audition", location: null })]);
    vi.stubGlobal("fetch", fetchMock);
    render(<UpcomingWidget role="musician" />);
    const rows = await screen.findAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.textContent).toContain("Jury round");
    expect(rows[0]?.textContent).toContain(new Date("2026-12-05T09:30:00Z").toLocaleDateString());
    expect(rows[0]?.textContent).toContain("• Studio 2");
    expect(rows[1]?.textContent).not.toContain("•");
    expect(rows[1]?.textContent).toContain("Scheduled");
    expect(urls(fetchMock)[0]).toBe("/api/v1/selection-process/slots/upcoming?limit=6");
  });

  it("has an empty state and a no-retry 403", async () => {
    vi.stubGlobal("fetch", api([]));
    render(<UpcomingWidget role="musician" />);
    expect(await screen.findByText("No upcoming selection rounds")).toBeTruthy();
    cleanup();
    vi.stubGlobal("fetch", api({}, 403));
    render(<UpcomingWidget role="musician" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
