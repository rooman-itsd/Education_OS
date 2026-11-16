import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ExaminationsApiError, listMyDuties } from "../src/api/client";
import type { ExamDuty, MyDutyPage } from "../src/api/types";
import { widgets } from "../src/widgets";
import { DUTY_LIMIT, ExamDuties } from "../src/widgets/ExamDuties";

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

const calledUrl = (n = 0) => new URL(fetchMock.mock.calls[n]![0] as string, "http://localhost");

function duty(over: Partial<ExamDuty> = {}): ExamDuty {
  return {
    id: "d1",
    organisation_id: "o1",
    exam_cycle_id: "c1",
    staff_id: "u1",
    duty_type: "invigilation",
    exam_session_id: "s1",
    exam_paper_id: null,
    status: "assigned",
    starts_at: "2026-11-02T04:00:00Z",
    ends_at: "2026-11-02T07:00:00Z",
    venue_label: "Hall A",
    ...over,
  };
}

describe("examinations.exam-duties registration", () => {
  it("is a Faculty list widget guarded by duty:read-own", () => {
    const w = widgets.find((x) => x.id === "examinations.exam-duties");
    expect(w).toBeDefined();
    expect(w).toMatchObject({
      title: "My exam duties",
      permission: "examinations:duty:read-own",
      kind: "list",
      component: ExamDuties,
    });
  });
});

describe("listMyDuties (GET /me/duties)", () => {
  it("asks for upcoming duties with the session token and no include_past", async () => {
    respond(200, { items: [] });
    await listMyDuties();
    const url = calledUrl();
    expect(url.pathname).toBe("/api/v1/examinations/me/duties");
    expect(url.searchParams.has("include_past")).toBe(false);
    expect((fetchMock.mock.calls[0]![1] as RequestInit).headers).toEqual({ Authorization: "Bearer t0ken" });
  });

  it("sends include_past=true only when asked", async () => {
    respond(200, { items: [] });
    await listMyDuties(true);
    expect(calledUrl().searchParams.get("include_past")).toBe("true");
  });

  it("returns the body as the contract shapes it", async () => {
    const page: MyDutyPage = { items: [duty()] };
    respond(200, page);
    await expect(listMyDuties()).resolves.toEqual(page);
  });

  it("throws the status and the contract message", async () => {
    respond(403, { code: "forbidden", message: "requires examinations:duty:read-own" });
    await expect(listMyDuties()).rejects.toMatchObject({ status: 403, message: "requires examinations:duty:read-own" });
  });

  it("falls back to the gateway detail", async () => {
    respond(502, { detail: "bad gateway" });
    await expect(listMyDuties()).rejects.toMatchObject({ status: 502, message: "bad gateway" });
  });

  it("turns a network failure into status 0", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("offline"));
    const error = await listMyDuties().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ExaminationsApiError);
    expect(error).toMatchObject({ status: 0 });
  });

  it("passes the abort signal on and lets an abort through unchanged", async () => {
    const ctrl = new AbortController();
    respond(200, { items: [] });
    await listMyDuties(false, ctrl.signal);
    expect((fetchMock.mock.calls[0]![1] as RequestInit).signal).toBe(ctrl.signal);
    fetchMock.mockRejectedValueOnce(Object.assign(new Error("aborted"), { name: "AbortError" }));
    await expect(listMyDuties()).rejects.toMatchObject({ name: "AbortError" });
  });
});

describe("examinations.exam-duties", () => {
  it("shows loading, then the duties of the caller from GET /me/duties", async () => {
    respond(200, { items: [duty()] });
    render(<ExamDuties role="faculty" />);
    expect(screen.getByLabelText("Loading").getAttribute("aria-busy")).toBe("true");
    await screen.findByText("Hall A");
    expect(calledUrl().pathname).toBe("/api/v1/examinations/me/duties");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.queryByLabelText("Loading")).toBeNull();
  });

  it("maps an invigilation duty: type, the session date and hours, venue and status", async () => {
    respond(200, { items: [duty()] });
    render(<ExamDuties role="faculty" />);
    const row = (await screen.findByText("Invigilation")).closest("li")!;
    expect(row.getAttribute("data-type")).toBe("invigilation");
    expect(within(row).getByText("Hall A")).toBeTruthy();
    expect(within(row).getByText("Assigned")).toBeTruthy();
    expect(within(row).getByText(/\d{1,2}:\d{2}.*–.*\d{1,2}:\d{2}/)).toBeTruthy();
  });

  it("maps evaluation and moderation duties: type, the course of the paper and no invented date", async () => {
    respond(200, {
      items: [
        duty({ id: "d2", duty_type: "evaluation", exam_session_id: null, exam_paper_id: "p1", course_code: "SPS101", starts_at: null, ends_at: null, venue_label: null }),
        duty({ id: "d3", duty_type: "moderation", exam_session_id: null, exam_paper_id: "p2", starts_at: null, ends_at: null, venue_label: null }),
      ],
    });
    render(<ExamDuties role="faculty" />);
    const evaluation = (await screen.findByText("Evaluation")).closest("li")!;
    expect(within(evaluation).getByText("SPS101")).toBeTruthy();
    expect(within(evaluation).getByText("No fixed date")).toBeTruthy();
    const moderation = screen.getByText("Moderation").closest("li")!;
    expect(within(moderation).getByText("Paper")).toBeTruthy(); // course_code absent: no made-up course
  });

  it("keeps the order of the server and shows a status other than assigned", async () => {
    respond(200, {
      items: [duty({ id: "late", venue_label: "Hall Z" }), duty({ id: "early", venue_label: "Hall B", status: "cancelled" })],
    });
    render(<ExamDuties role="faculty" />);
    await screen.findByText("Hall Z");
    expect(screen.getAllByRole("listitem").map((li) => li.getAttribute("data-status"))).toEqual(["assigned", "cancelled"]);
    expect(screen.getAllByRole("listitem")[0]!.textContent).toContain("Hall Z");
    expect(screen.getByText("Cancelled")).toBeTruthy();
  });

  it("renders missing session details without crashing or inventing them", async () => {
    respond(200, {
      items: [
        duty({ starts_at: null, ends_at: null, venue_label: null }),
        duty({ id: "d2", starts_at: "not a date", ends_at: "nope", venue_label: "" }),
      ],
    });
    render(<ExamDuties role="faculty" />);
    await waitFor(() => expect(screen.getAllByText("Venue not set")).toHaveLength(2));
    expect(screen.getAllByText("Date not set")).toHaveLength(2);
    expect(screen.getAllByText("Time not set")).toHaveLength(2);
  });

  it("shows an unknown status as it came, so a newer backend does not break it", async () => {
    respond(200, { items: [{ ...duty(), status: "paused" as ExamDuty["status"] }] });
    render(<ExamDuties role="faculty" />);
    expect(await screen.findByText("paused")).toBeTruthy();
  });

  it("lists at most DUTY_LIMIT duties and says how many there are", async () => {
    const items = Array.from({ length: DUTY_LIMIT + 3 }, (_, i) => duty({ id: `d${i}`, venue_label: `Hall ${i}` }));
    respond(200, { items });
    render(<ExamDuties role="faculty" />);
    await screen.findByText("Hall 0");
    expect(screen.getAllByRole("listitem")).toHaveLength(DUTY_LIMIT);
    expect(screen.getByText(`Showing ${DUTY_LIMIT} of ${DUTY_LIMIT + 3} upcoming duties`)).toBeTruthy();
  });

  it("shows an empty state", async () => {
    respond(200, { items: [] });
    render(<ExamDuties role="faculty" />);
    expect(await screen.findByText("No upcoming exam duties.")).toBeTruthy();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("says the data is not available while the endpoint is missing (404), as the other widgets do", async () => {
    respond(404, { detail: "Not Found" });
    render(<ExamDuties role="faculty" />);
    expect(await screen.findByText("Examinations data is not available yet.")).toBeTruthy();
    expect(screen.queryByText("No upcoming exam duties.")).toBeNull();
  });

  it.each([502, 503])("reports a %i from the gateway as not available yet", async (status) => {
    respond(status, { detail: "down" });
    render(<ExamDuties role="faculty" />);
    expect(await screen.findByText("Examinations data is not available yet.")).toBeTruthy();
  });

  it("reports a network failure as unavailable", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("offline"));
    render(<ExamDuties role="faculty" />);
    expect(await screen.findByText("Examinations data is not available yet.")).toBeTruthy();
  });

  it("shows a permission error without a retry", async () => {
    respond(403, { code: "forbidden", message: "requires examinations:duty:read-own" });
    render(<ExamDuties role="faculty" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /try again|retry/i })).toBeNull();
  });

  it("asks to sign in again, without a retry, when the session has expired", async () => {
    respond(401, { detail: "missing bearer token" });
    render(<ExamDuties role="faculty" />);
    expect(await screen.findByText("Sign in again to see this.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /try again|retry/i })).toBeNull();
  });

  it("shows the contract message for other failures and loads again when retry is pressed", async () => {
    respond(500, { code: "server_error", message: "Something broke" });
    respond(200, { items: [duty()] });
    render(<ExamDuties role="faculty" />);
    expect(await screen.findByText("Something broke")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /try again|retry/i }));
    expect(await screen.findByText("Hall A")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not report a result after it unmounts", async () => {
    let release!: (r: Response) => void;
    fetchMock.mockReturnValueOnce(new Promise<Response>((r) => (release = r)));
    const { unmount } = render(<ExamDuties role="faculty" />);
    unmount();
    release(new Response(JSON.stringify({ items: [duty()] }), { status: 200 }));
    await Promise.resolve();
    expect(screen.queryByText("Hall A")).toBeNull();
  });
});
