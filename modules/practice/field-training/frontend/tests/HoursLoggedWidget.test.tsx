import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { HoursSummary } from "../src/api/client";
import { HoursLoggedWidget } from "../src/widgets/HoursLoggedWidget";
import { answer, failThenAnswer, firstCall, useSession } from "./helpers";

useSession();

const summary = (over: Partial<HoursSummary> = {}): HoursSummary => ({
  placement_id: "p1",
  required_hours: 40,
  verified_hours: 10,
  pending_hours: 2.5,
  returned_hours: 3,
  by_date: [
    { date: "2026-11-02", verified_hours: 6, pending_hours: 0 },
    { date: "2026-11-03", verified_hours: 4, pending_hours: 2.5 },
  ],
  ...over,
});

describe("field-training.hours-logged widget", () => {
  it("shows verified hours against the requirement from GET /me/hours", async () => {
    const fetchMock = answer(200, summary());
    vi.stubGlobal("fetch", fetchMock);
    render(<HoursLoggedWidget role="medical-student" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText(/of 40 hours verified/)).toBeTruthy();
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("25");
    expect(screen.getByText("Awaiting verification: 2.5 h")).toBeTruthy();
    expect(screen.getByText("Returned for correction: 3 h")).toBeTruthy();
    expect(screen.getByText("Logged in the last 14 days: 12.5 h")).toBeTruthy();
    const { url, auth } = firstCall(fetchMock);
    expect(url).toBe("/api/v1/field-training/me/hours");
    expect(auth).toBe("Bearer test-token");
  });

  it("shows no bar when the placement has no requirement, and no returned line when none", async () => {
    vi.stubGlobal("fetch", answer(200, summary({ required_hours: 0, returned_hours: 0 })));
    render(<HoursLoggedWidget role="medical-student" />);
    expect(await screen.findByText(/hours verified/)).toBeTruthy();
    expect(screen.queryByRole("progressbar")).toBeNull();
    expect(screen.queryByText(/Returned/)).toBeNull();
  });

  it("shows an empty state when the caller has no placement", async () => {
    vi.stubGlobal(
      "fetch",
      answer(200, summary({ placement_id: null, required_hours: 0, verified_hours: 0, pending_hours: 0, returned_hours: 0, by_date: [] })),
    );
    render(<HoursLoggedWidget role="medical-student" />);
    expect(await screen.findByText("No hours to show yet")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = failThenAnswer(summary());
    vi.stubGlobal("fetch", fetchMock);
    render(<HoursLoggedWidget role="medical-student" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Field training data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(/of 40 hours verified/)).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
