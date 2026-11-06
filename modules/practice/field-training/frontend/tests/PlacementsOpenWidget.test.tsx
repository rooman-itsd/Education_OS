import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { OPENINGS_LIMIT, PlacementsOpenWidget } from "../src/widgets/PlacementsOpenWidget";
import { answer, failThenAnswer, firstCall, opening, useSession } from "./helpers";

useSession();

const page = { items: [opening(), opening({ id: "op2", title: "Night rotation", seats: 2, seats_filled: 1 })], next_cursor: "NQ==" };

describe("field-training.placements-open widget", () => {
  it("lists open openings with seats left from GET /openings?status=open&has_seats=true", async () => {
    const fetchMock = answer(200, page);
    vi.stubGlobal("fetch", fetchMock);
    render(<PlacementsOpenWidget role="hospital-coordinator" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("General rotation")).toBeTruthy();
    expect(screen.getByText("Night rotation")).toBeTruthy();
    expect(screen.getByText("2 seats left")).toBeTruthy();
    expect(screen.getByText("1 seat left")).toBeTruthy();
    expect(screen.getAllByText(/North Ward · General/)).toHaveLength(2);
    expect(screen.getByText("More openings are open than shown here.")).toBeTruthy();
    const { url, auth } = firstCall(fetchMock);
    expect(url).toBe(`/api/v1/field-training/openings?status=open&has_seats=true&limit=${OPENINGS_LIMIT}`);
    expect(auth).toBe("Bearer test-token");
  });

  it("shows an empty state when no opening has a seat", async () => {
    vi.stubGlobal("fetch", answer(200, { items: [], next_cursor: null }));
    render(<PlacementsOpenWidget role="hospital-coordinator" />);
    expect(await screen.findByText("No open placements with seats")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = failThenAnswer({ items: [opening()], next_cursor: null });
    vi.stubGlobal("fetch", fetchMock);
    render(<PlacementsOpenWidget role="hospital-coordinator" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Field training data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("General rotation")).toBeTruthy();
    expect(screen.queryByText(/More openings/)).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
