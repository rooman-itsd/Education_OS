import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ACTIVE_LIMIT, ActivePlacementsWidget } from "../src/widgets/ActivePlacementsWidget";
import { answer, failThenAnswer, firstCall, placement, useSession } from "./helpers";

useSession();

const page = {
  items: [placement({ trainee_name: "Trainee One" }), placement({ id: "p2", required_hours: 0, verified_hours: 6 })],
  next_cursor: null,
};

describe("field-training.active-placements widget", () => {
  it("lists placements under way from GET /placements?status=active", async () => {
    const fetchMock = answer(200, page);
    vi.stubGlobal("fetch", fetchMock);
    render(<ActivePlacementsWidget role="hospital-coordinator" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Trainee One")).toBeTruthy();
    expect(screen.getByText("Trainee")).toBeTruthy();
    expect(screen.getByText("12.5 of 40 h")).toBeTruthy();
    expect(screen.getByText("6 h")).toBeTruthy();
    expect(screen.queryByText(/More placements/)).toBeNull();
    const { url, auth } = firstCall(fetchMock);
    expect(url).toBe(`/api/v1/field-training/placements?status=active&limit=${ACTIVE_LIMIT}`);
    expect(auth).toBe("Bearer test-token");
  });

  it("shows an empty state when no placement is active", async () => {
    vi.stubGlobal("fetch", answer(200, { items: [], next_cursor: null }));
    render(<ActivePlacementsWidget role="hospital-coordinator" />);
    expect(await screen.findByText("No placements under way")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = failThenAnswer({ ...page, next_cursor: "NQ==" });
    vi.stubGlobal("fetch", fetchMock);
    render(<ActivePlacementsWidget role="hospital-coordinator" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Field training data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Trainee One")).toBeTruthy();
    expect(screen.getByText("More placements are under way than shown here.")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
