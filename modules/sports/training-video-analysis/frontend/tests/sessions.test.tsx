import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { TrainingSession } from "../src/api/client";
import { widgets } from "../src/widgets";
import { localToday, sessions } from "../src/widgets/format";
import { SessionPlan, SHOWN, TrainingSchedule } from "../src/widgets/UpcomingSessions";

const BASE = "/api/v1/training-video-analysis";
type Reply = { status: number; body: unknown };

/** Stubs fetch: only `/sessions` answers; any other request fails the test. */
function stubApi(reply: Reply | (() => Reply)) {
  const fetchMock = vi.fn(async (input: string, _init?: RequestInit) => {
    const url = new URL(input, "http://localhost");
    if (url.pathname.slice(BASE.length) !== "/sessions") throw new Error(`unexpected request ${input}`);
    const r = typeof reply === "function" ? reply() : reply;
    return { ok: r.status < 400, status: r.status, statusText: "", json: async () => r.body };
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const session = (id: string, title: string, over: Partial<TrainingSession> = {}): TrainingSession => ({
  id,
  coach_id: "c-1",
  title,
  scheduled_start: "2026-11-05T06:30:00",
  scheduled_end: "2026-11-05T08:00:00",
  status: "scheduled",
  location: "Main ground",
  ...over,
});
const page = <T,>(items: T[], total = items.length) => ({ items, total });

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("session-plan and training-schedule declarations", () => {
  it.each([
    ["training-video-analysis.session-plan", "Session plan", "2x1", SessionPlan],
    ["training-video-analysis.training-schedule", "Training schedule", "1x1", TrainingSchedule],
  ])("%s needs session:read, which the coach and athlete roles hold", (id, title, size, component) => {
    const w = widgets.find((x) => x.id === id)!;
    expect(w.title).toBe(title);
    expect(w.permission).toBe("training-video-analysis:session:read");
    expect(w.kind).toBe("list");
    expect(w.size).toBe(size);
    expect(w.component).toBe(component);
  });
});

describe("upcoming sessions", () => {
  it("asks for the scheduled sessions from today, earliest first, in one request", async () => {
    const fetchMock = stubApi({ status: 200, body: page([session("s-1", "Speed and agility")]) });
    render(<SessionPlan role="coach" />);
    await screen.findByText("Speed and agility");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const url = new URL(String(fetchMock.mock.calls[0]![0]), "http://localhost");
    expect(url.pathname).toBe(`${BASE}/sessions`);
    expect(url.searchParams.get("status")).toBe("scheduled");
    expect(url.searchParams.get("from_date")).toBe(localToday());
    expect(url.searchParams.get("limit")).toBe(String(SHOWN));
    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("lists each session with its day, time and place, and the number scheduled in all", async () => {
    stubApi({ status: 200, body: page([session("s-1", "Speed and agility"), session("s-2", "Recovery", { location: null })], 9) });
    render(<SessionPlan role="coach" />);
    expect(await screen.findByText("Speed and agility")).toBeTruthy();
    expect(screen.getByText("Recovery")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows[0]!.textContent).toContain("Main ground");
    expect(rows[1]!.textContent).not.toContain("Main ground");
    expect(screen.getByLabelText("Session summary").textContent).toContain("9");
    expect(screen.getByText(`and ${sessions(7)} more`)).toBeTruthy();
  });

  it("says nothing is scheduled, in the coach's words and the athlete's", async () => {
    stubApi({ status: 200, body: page([]) });
    const coach = render(<SessionPlan role="coach" />);
    expect(await screen.findByText("No sessions scheduled")).toBeTruthy();
    coach.unmount();
    render(<TrainingSchedule role="athlete" />);
    expect(await screen.findByText("No training sessions scheduled")).toBeTruthy();
  });

  it("the athlete widget lists the athlete's sessions", async () => {
    stubApi({ status: 200, body: page([session("s-1", "Team drills")]) });
    render(<TrainingSchedule role="athlete" />);
    expect(await screen.findByText("Team drills")).toBeTruthy();
    expect(screen.getByLabelText("Schedule summary")).toBeTruthy();
  });

  it("says the data is not available when the service is missing, and retries", async () => {
    let calls = 0;
    const fetchMock = stubApi(() => (++calls === 1 ? { status: 404, body: {} } : { status: 200, body: page([session("s-1", "Back again")]) }));
    render(<SessionPlan role="coach" />);
    expect(await screen.findByText("Training video data is not available yet.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Back again")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("offers no retry when access is refused", async () => {
    stubApi({ status: 403, body: {} });
    render(<TrainingSchedule role="athlete" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});
