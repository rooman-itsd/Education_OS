import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getMyExamSchedule, today } from "../src/api/client";
import type { MyExamSessionItem } from "../src/api/types";
import { widgets } from "../src/widgets";
import { EXAM_LIMIT, UpcomingAssessments } from "../src/widgets/UpcomingAssessments";

const fetchMock = vi.fn();

function respond(status: number, body: unknown) {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  localStorage.setItem("eos.token", "t0ken");
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const calledUrl = () => new URL(fetchMock.mock.calls[0]![0] as string, "http://localhost");

function exam(over: Partial<MyExamSessionItem> = {}): MyExamSessionItem {
  return {
    exam_session_id: "s1",
    exam_cycle_id: "c1",
    starts_at: "2026-11-25T09:00:00Z",
    ends_at: "2026-11-25T12:00:00Z",
    venue_label: "Hall A",
    exam_paper_id: "p1",
    course_offering_id: "o1",
    course_code: "CS201",
    course_title: "Data Structures",
    component_code: "END",
    eligibility_status: "eligible",
    hall_ticket_status: null,
    ...over,
  };
}

describe("examinations.upcoming-assessments registration", () => {
  it("is a Student list widget guarded by session:read-own", () => {
    const w = widgets.find((x) => x.id === "examinations.upcoming-assessments");
    expect(w).toMatchObject({
      title: "Upcoming assessments",
      permission: "examinations:session:read-own",
      kind: "list",
      component: UpcomingAssessments,
    });
  });
});

describe("getMyExamSchedule (GET /me/exam-schedule)", () => {
  it("asks from today with the session token", async () => {
    respond(200, { items: [] });
    await getMyExamSchedule();
    const url = calledUrl();
    expect(url.pathname).toBe("/api/v1/examinations/me/exam-schedule");
    expect(url.searchParams.get("date_from")).toBe(today());
    expect((fetchMock.mock.calls[0]![1] as RequestInit).headers).toEqual({ Authorization: "Bearer t0ken" });
  });

  it("returns the body as the contract shapes it", async () => {
    const body = { items: [exam()] };
    respond(200, body);
    await expect(getMyExamSchedule()).resolves.toEqual(body);
  });
});

describe("examinations.upcoming-assessments", () => {
  it("shows loading, then the exams the student sits", async () => {
    respond(200, { items: [exam()] });
    render(<UpcomingAssessments role="student" />);
    expect(screen.getByLabelText("Loading").getAttribute("aria-busy")).toBe("true");
    const row = (await screen.findByText("CS201 · END")).closest("li")!;
    expect(within(row).getByText("Hall A")).toBeTruthy();
    expect(within(row).getByText("Eligible")).toBeTruthy();
    expect(within(row).getByText(/\d{1,2}:\d{2}.*–.*\d{1,2}:\d{2}/)).toBeTruthy();
    expect(screen.getByRole("list", { name: "Upcoming exams" })).toBeTruthy();
    expect(screen.queryByLabelText("Loading")).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("keeps the order of the server and labels each eligibility status", async () => {
    respond(200, {
      items: [
        exam({ exam_paper_id: "p1", venue_label: "Hall Z", eligibility_status: "pending" }),
        exam({ exam_paper_id: "p2", venue_label: "Hall B", eligibility_status: "ineligible" }),
      ],
    });
    render(<UpcomingAssessments role="student" />);
    await screen.findByText("Hall Z");
    const rows = screen.getAllByRole("listitem");
    expect(rows.map((li) => li.getAttribute("data-eligibility"))).toEqual(["pending", "ineligible"]);
    expect(rows[0]!.textContent).toContain("Hall Z");
    expect(screen.getByText("Eligibility pending")).toBeTruthy();
    expect(screen.getByText("Not eligible")).toBeTruthy();
  });

  it("falls back to the title, or to a plain label, when the course code is not known, and never invents one", async () => {
    respond(200, {
      items: [
        exam({ exam_paper_id: "p1", course_code: undefined, component_code: undefined }),
        exam({ exam_paper_id: "p2", course_code: undefined, course_title: undefined, component_code: undefined }),
      ],
    });
    render(<UpcomingAssessments role="student" />);
    expect(await screen.findByText("Data Structures")).toBeTruthy();
    expect(screen.getByText("Exam")).toBeTruthy();
  });

  it("renders missing session details without crashing or inventing them", async () => {
    respond(200, {
      items: [exam({ starts_at: "not a date", ends_at: "nope", venue_label: null }), exam({ exam_paper_id: "p2", venue_label: "" })],
    });
    render(<UpcomingAssessments role="student" />);
    await waitFor(() => expect(screen.getAllByText("Venue not set")).toHaveLength(2));
    expect(screen.getByText("Date not set")).toBeTruthy();
    expect(screen.getByText("Time not set")).toBeTruthy();
  });

  it("lists at most EXAM_LIMIT exams and says how many there are", async () => {
    const items = Array.from({ length: EXAM_LIMIT + 3 }, (_, i) => exam({ exam_paper_id: `p${i}`, venue_label: `Hall ${i}` }));
    respond(200, { items });
    render(<UpcomingAssessments role="student" />);
    await screen.findByText("Hall 0");
    expect(screen.getAllByRole("listitem")).toHaveLength(EXAM_LIMIT);
    expect(screen.getByText(`Showing ${EXAM_LIMIT} of ${EXAM_LIMIT + 3} upcoming exams`)).toBeTruthy();
  });

  it("shows an empty state", async () => {
    respond(200, { items: [] });
    render(<UpcomingAssessments role="student" />);
    expect(await screen.findByText("No upcoming exams.")).toBeTruthy();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it.each([404, 502, 503])("reports a %i as not available yet, not as an empty schedule", async (status) => {
    respond(status, { detail: "down" });
    render(<UpcomingAssessments role="student" />);
    expect(await screen.findByText("Examinations data is not available yet.")).toBeTruthy();
    expect(screen.queryByText("No upcoming exams.")).toBeNull();
  });

  it("reports a network failure as unavailable", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("offline"));
    render(<UpcomingAssessments role="student" />);
    expect(await screen.findByText("Examinations data is not available yet.")).toBeTruthy();
  });

  it("shows a permission error without a retry", async () => {
    respond(403, { code: "forbidden", message: "requires examinations:session:read-own" });
    render(<UpcomingAssessments role="student" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /try again|retry/i })).toBeNull();
  });

  it("asks to sign in again, without a retry, when the session has expired", async () => {
    respond(401, { detail: "missing bearer token" });
    render(<UpcomingAssessments role="student" />);
    expect(await screen.findByText("Sign in again to see this.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /try again|retry/i })).toBeNull();
  });

  it("shows the contract message for other failures and loads again when retry is pressed", async () => {
    respond(500, { code: "server_error", message: "Something broke" });
    respond(200, { items: [exam()] });
    render(<UpcomingAssessments role="student" />);
    expect(await screen.findByText("Something broke")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /try again|retry/i }));
    expect(await screen.findByText("Hall A")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not report a result after it unmounts", async () => {
    let release!: (r: Response) => void;
    fetchMock.mockReturnValueOnce(new Promise<Response>((r) => (release = r)));
    const { unmount } = render(<UpcomingAssessments role="student" />);
    unmount();
    release(new Response(JSON.stringify({ items: [exam()] }), { status: 200 }));
    await Promise.resolve();
    expect(screen.queryByText("Hall A")).toBeNull();
  });
});
