import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TRAINEES_LIMIT, TraineesToAssessWidget } from "../src/widgets/TraineesToAssessWidget";
import { answer, failThenAnswer, firstCall, placement, useSession } from "./helpers";

useSession();

const rows = [
  { placement: placement({ trainee_name: "Trainee One", ends_on: "2026-11-09" }), entries_awaiting: 2, final_assessment_due: true },
  { placement: placement({ id: "p2", trainee_name: null }), entries_awaiting: 1, final_assessment_due: false },
];

describe("field-training.trainees-to-assess widget", () => {
  it("lists trainees needing action from GET /me/trainees, most urgent first", async () => {
    const fetchMock = answer(200, rows);
    vi.stubGlobal("fetch", fetchMock);
    render(<TraineesToAssessWidget role="clinical-supervisor" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Trainee One")).toBeTruthy();
    expect(screen.getByText("Trainee")).toBeTruthy();
    expect(screen.getByText("Final assessment due")).toBeTruthy();
    expect(screen.getByText("1 entry to verify")).toBeTruthy();
    expect(screen.getByText(/2 to verify/)).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    const { url, auth } = firstCall(fetchMock);
    expect(url).toBe(`/api/v1/field-training/me/trainees?limit=${TRAINEES_LIMIT}`);
    expect(auth).toBe("Bearer test-token");
  });

  it("shows an empty state when nothing needs action", async () => {
    vi.stubGlobal("fetch", answer(200, []));
    render(<TraineesToAssessWidget role="clinical-supervisor" />);
    expect(await screen.findByText("Nothing to assess right now")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = failThenAnswer(rows);
    vi.stubGlobal("fetch", fetchMock);
    render(<TraineesToAssessWidget role="clinical-supervisor" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Field training data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Trainee One")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
