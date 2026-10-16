import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ExamSessionPage, HallTicketReport, ResultsPendingReport } from "../src/api/types";
import { today } from "../src/api/client";
import { widgets } from "../src/widgets";
import { ExamSchedule } from "../src/widgets/ExamSchedule";
import { HallTicketsIssued } from "../src/widgets/HallTicketsIssued";
import { ResultsPending } from "../src/widgets/ResultsPending";

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

describe("widget declarations", () => {
  it("export the three Examination Staff widgets with the contract's permission keys", () => {
    expect(widgets.map((w) => [w.id, w.permission])).toEqual([
      ["examinations.schedule", "examinations:session:read"],
      ["examinations.hall-tickets-issued", "examinations:hall-ticket:read-all"],
      ["examinations.results-pending", "examinations:report:read-all"],
    ]);
  });
});

describe("examinations.schedule", () => {
  const page: ExamSessionPage = {
    total: 9,
    items: [
      {
        id: "s1",
        organisation_id: "o1",
        exam_cycle_id: "c1",
        starts_at: "2026-11-02T04:00:00Z",
        ends_at: "2026-11-02T07:00:00Z",
        venue_label: "Hall A",
        status: "scheduled",
        papers: [{ exam_paper_id: "p1", course_offering_id: "co1", course_code: "SPS101", course_title: "Sports Physiology", component_code: "T" }],
        candidate_count: 120,
        invigilators_required: 4,
        invigilators_assigned: 3,
      },
      {
        id: "s2",
        organisation_id: "o1",
        exam_cycle_id: "c1",
        starts_at: "2026-11-03T04:00:00Z",
        ends_at: "2026-11-03T06:00:00Z",
        venue_label: null,
        status: "scheduled",
        papers: [{ exam_paper_id: "p2", course_offering_id: "co2" }],
        candidate_count: 40,
        invigilators_required: 2,
        invigilators_assigned: 2,
      },
    ],
  };

  it("shows loading, then asks for today's scheduled sessions with the session token", async () => {
    respond(200, page);
    render(<ExamSchedule role="examination-staff" />);
    expect(screen.getByLabelText("Loading").getAttribute("aria-busy")).toBe("true");
    await screen.findByText("Hall A");
    const url = calledUrl();
    expect(url.pathname).toBe("/api/v1/examinations/sessions");
    expect(url.searchParams.get("date_from")).toBe(today());
    expect(url.searchParams.get("status")).toBe("scheduled");
    expect((fetchMock.mock.calls[0]![1] as RequestInit).headers).toEqual({ Authorization: "Bearer t0ken" });
  });

  it("maps papers, venue, candidates and invigilators from the contract", async () => {
    respond(200, page);
    render(<ExamSchedule role="examination-staff" />);
    const first = (await screen.findByText("SPS101 · Sports Physiology (T)")).closest("li")!;
    expect(within(first).getByText("Hall A")).toBeTruthy();
    expect(within(first).getByText("120")).toBeTruthy();
    const invig = within(first).getByText("3/4 · short");
    expect(invig.closest("[data-warn]")).toBeTruthy();
    const second = screen.getByText("Paper").closest("li")!;
    expect(within(second).getByText("Venue not set")).toBeTruthy();
    expect(within(second).getByText("2/2").closest("[data-warn]")).toBeNull();
    expect(within(second).queryByText(/short/)).toBeNull();
    expect(screen.getByText("Showing 2 of 9 upcoming sessions")).toBeTruthy();
  });

  it("shows an empty state", async () => {
    respond(200, { items: [], total: 0 });
    render(<ExamSchedule role="examination-staff" />);
    expect(await screen.findByText("No upcoming exam sessions.")).toBeTruthy();
  });

  it("renders a session whose timestamps are not valid dates instead of crashing", async () => {
    respond(200, { total: 1, items: [{ ...page.items[0]!, starts_at: "not-a-date", ends_at: "" }] });
    render(<ExamSchedule role="examination-staff" />);
    const first = (await screen.findByText("SPS101 · Sports Physiology (T)")).closest("li")!;
    expect(within(first).getByText("Date not set")).toBeTruthy();
    expect(within(first).getByText("Time not set")).toBeTruthy();
    expect(first.textContent).not.toContain("Invalid Date");
  });

  it("says the data is not available while the examinations service is missing", async () => {
    respond(404, { detail: "Not Found" });
    render(<ExamSchedule role="examination-staff" />);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("Examinations data is not available yet.")).toBeTruthy();
  });

  it("reports a network failure as unavailable", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    render(<ExamSchedule role="examination-staff" />);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("Examinations data is not available yet.")).toBeTruthy();
  });

  it("loads again when the error state's retry is pressed", async () => {
    respond(503, { detail: "Service Unavailable" });
    respond(200, page);
    render(<ExamSchedule role="examination-staff" />);
    const alert = await screen.findByRole("alert");
    fireEvent.click(within(alert).getByRole("button", { name: "Try again" }));
    await screen.findByText("Hall A");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("examinations.hall-tickets-issued", () => {
  const report: HallTicketReport = {
    items: [
      {
        exam_cycle_id: "c1",
        exam_cycle_name: "Odd Semester 2026",
        eligible_students: 200,
        issued: 180,
        withheld: 12,
        revoked: 2,
        not_issued: 8,
        withheld_reasons: [
          { reason: "Attendance shortage", count: 9 },
          { reason: "Fee dues", count: 3 },
        ],
      },
    ],
  };

  it("maps eligible, issued, not issued, withheld, revoked and the withheld reasons", async () => {
    respond(200, report);
    render(<HallTicketsIssued role="examination-staff" />);
    const cycle = await screen.findByRole("region", { name: "Odd Semester 2026" });
    expect(calledUrl().pathname).toBe("/api/v1/examinations/reports/hall-tickets");
    const value = (label: string) => within(cycle).getByText(label).nextSibling?.textContent;
    expect([value("Eligible"), value("Issued"), value("Not issued"), value("Withheld"), value("Revoked")]).toEqual(["200", "180", "8", "12", "2"]);
    // the kit's ProgressBar reports the percentage issued (180 of 200)
    expect(within(cycle).getByRole("progressbar").getAttribute("aria-valuenow")).toBe("90");
    const reasons = within(cycle).getByRole("list", { name: "Withheld reasons" });
    expect(reasons.textContent).toBe("Attendance shortage9Fee dues3");
  });

  it("shows an empty state when no exam cycle is active", async () => {
    respond(200, { items: [] });
    render(<HallTicketsIssued role="examination-staff" />);
    expect(await screen.findByText("No exam cycle is scheduled or in progress.")).toBeTruthy();
  });

  it("shows a permission error from the API", async () => {
    respond(403, { code: "forbidden", message: "missing examinations:hall-ticket:read-all" });
    render(<HallTicketsIssued role="examination-staff" />);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("You do not have access to this.")).toBeTruthy();
    expect(within(alert).queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("asks to sign in again, without a retry, when the session has expired", async () => {
    respond(401, { code: "unauthenticated", message: "token expired" });
    render(<HallTicketsIssued role="examination-staff" />);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("Sign in again to see this.")).toBeTruthy();
    expect(within(alert).queryByRole("button", { name: "Try again" })).toBeNull();
  });
});

describe("examinations.results-pending", () => {
  const report: ResultsPendingReport = {
    items: [
      {
        exam_cycle_id: "c1",
        exam_cycle_name: "Odd Semester 2026",
        stages: [
          { stage: "awaiting_approval", count: 3, oldest_since: null },
          { stage: "marks_entry", count: 14, oldest_since: new Date(Date.now() - 5 * 86_400_000).toISOString() },
          { stage: "moderation", count: 1 },
        ],
      },
      { exam_cycle_id: "c2", exam_cycle_name: "Finished cycle", stages: [] },
    ],
  };

  it("lists every contract stage in pipeline order with its count, unit and age", async () => {
    respond(200, report);
    render(<ResultsPending role="examination-staff" />);
    const cycle = await screen.findByRole("region", { name: "Odd Semester 2026" });
    expect(calledUrl().pathname).toBe("/api/v1/examinations/reports/results-pending");
    const rows = within(cycle).getAllByRole("listitem");
    expect(rows.map((r) => r.querySelector(".eos-exam__stage-label")!.textContent)).toEqual([
      "Marks entry",
      "Moderation",
      "Awaiting lock",
      "Awaiting computation",
      "Awaiting approval",
      "Awaiting publication",
    ]);
    expect(rows[0]!.textContent).toBe("Marks entry14papers · oldest 5 d");
    expect(rows[1]!.textContent).toBe("Moderation1paper");
    expect(rows[2]!.textContent).toBe("Awaiting lock0none");
    expect(rows[4]!.textContent).toBe("Awaiting approval3course offerings");
    expect(rows[0]!.hasAttribute("data-pending")).toBe(true);
    expect(rows[2]!.hasAttribute("data-pending")).toBe(false);
    expect(screen.queryByRole("region", { name: "Finished cycle" })).toBeNull();
  });

  it("leaves out the age when oldest_since is not a valid timestamp", async () => {
    respond(200, {
      items: [{ exam_cycle_id: "c1", exam_cycle_name: "Odd Semester 2026", stages: [{ stage: "marks_entry", count: 4, oldest_since: "not-a-date" }] }],
    });
    render(<ResultsPending role="examination-staff" />);
    const cycle = await screen.findByRole("region", { name: "Odd Semester 2026" });
    const row = within(cycle).getAllByRole("listitem")[0]!;
    expect(row.textContent).toBe("Marks entry4papers");
    expect(cycle.textContent).not.toContain("NaN");
  });

  it("shows an empty state when nothing is pending", async () => {
    respond(200, { items: [{ exam_cycle_id: "c2", stages: [{ stage: "marks_entry", count: 0 }] }] });
    render(<ResultsPending role="examination-staff" />);
    expect(await screen.findByText("No results pending.")).toBeTruthy();
  });

  it("shows the contract's error message for other failures", async () => {
    respond(500, { code: "internal", message: "results report failed" });
    render(<ResultsPending role="examination-staff" />);
    await waitFor(() => expect(within(screen.getByRole("alert")).getByText("results report failed")).toBeTruthy());
    expect(within(screen.getByRole("alert")).getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
