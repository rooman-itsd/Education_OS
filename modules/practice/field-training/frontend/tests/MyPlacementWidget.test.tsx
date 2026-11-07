import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MyPlacementWidget } from "../src/widgets/MyPlacementWidget";
import { answer, failThenAnswer, firstCall, placement, useSession } from "./helpers";

useSession();

describe("field-training.my-placement widget", () => {
  it("lists the caller's placements from GET /me/placements with the session token", async () => {
    const fetchMock = answer(200, [
      placement(),
      placement({ id: "p2", status: "assigned", opening_title: "January rotation", starts_on: "2027-01-04" }),
      placement({ id: "p3", status: "requested", opening_title: "Spring rotation", starts_on: "2027-03-01" }),
      placement({ id: "p4", status: "requested", opening_title: "Not shown", starts_on: "2027-05-01" }),
    ]);
    vi.stubGlobal("fetch", fetchMock);
    render(<MyPlacementWidget role="medical-student" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("General rotation")).toBeTruthy();
    expect(screen.getByText("Active")).toBeTruthy();
    expect(screen.getByText("Upcoming")).toBeTruthy();
    expect(screen.getByText("Applied")).toBeTruthy();
    expect(screen.getByText(/12.5 of 40 h verified/)).toBeTruthy();
    expect(screen.queryByText("Not shown")).toBeNull();
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    const { url, auth } = firstCall(fetchMock);
    expect(url).toBe("/api/v1/field-training/me/placements");
    expect(auth).toBe("Bearer test-token");
  });

  it("shows an empty state when the caller has no placement", async () => {
    vi.stubGlobal("fetch", answer(200, []));
    render(<MyPlacementWidget role="medical-student" />);
    expect(await screen.findByText("No placement yet")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = failThenAnswer([placement()]);
    vi.stubGlobal("fetch", fetchMock);
    render(<MyPlacementWidget role="medical-student" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Field training data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("General rotation")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
