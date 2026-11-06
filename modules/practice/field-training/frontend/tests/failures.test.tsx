import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentType } from "react";
import { describe, expect, it, vi } from "vitest";
import { describeFailure, FieldTrainingApiError } from "../src/api/client";
import type { WidgetProps } from "@eos/ui-kit";
import { ActivePlacementsWidget } from "../src/widgets/ActivePlacementsWidget";
import { HoursLoggedWidget } from "../src/widgets/HoursLoggedWidget";
import { MyPlacementWidget } from "../src/widgets/MyPlacementWidget";
import { PlacementsOpenWidget } from "../src/widgets/PlacementsOpenWidget";
import { TraineesToAssessWidget } from "../src/widgets/TraineesToAssessWidget";
import { answer, useSession } from "./helpers";

useSession();

const NOT_YET = "Field training data is not available yet.";

describe("describeFailure", () => {
  it.each([
    [new FieldTrainingApiError(404, ""), NOT_YET, true],
    [new FieldTrainingApiError(502, ""), NOT_YET, true],
    [new FieldTrainingApiError(503, ""), NOT_YET, true],
    [new TypeError("Failed to fetch"), NOT_YET, true],
    [new FieldTrainingApiError(401, ""), "Sign in again to see this.", false],
    [new FieldTrainingApiError(403, ""), "You do not have access to this.", false],
    [new FieldTrainingApiError(500, ""), "Could not load your hours", true],
  ])("%s -> %s", (error, title, retry) => {
    const f = describeFailure(error, "your hours");
    expect(f.title).toBe(title);
    expect(f.retry).toBe(retry);
  });
});

const WIDGETS: [string, ComponentType<WidgetProps>, string][] = [
  ["field-training.my-placement", MyPlacementWidget, "your placements"],
  ["field-training.hours-logged", HoursLoggedWidget, "your hours"],
  ["field-training.trainees-to-assess", TraineesToAssessWidget, "your trainees"],
  ["field-training.placements-open", PlacementsOpenWidget, "open placements"],
  ["field-training.active-placements", ActivePlacementsWidget, "active placements"],
];

describe.each(WIDGETS)("%s error states", (_id, Widget, what) => {
  it.each([
    [401, "Sign in again to see this."],
    [403, "You do not have access to this."],
  ])("on %i says why and offers no retry", async (status, text) => {
    vi.stubGlobal("fetch", answer(status, {}));
    render(<Widget role="test" />);
    expect((await screen.findByRole("alert")).textContent).toContain(text);
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it.each([404, 502])("on %i says the data is not available yet, with a retry", async (status) => {
    vi.stubGlobal("fetch", answer(status, {}));
    render(<Widget role="test" />);
    expect((await screen.findByRole("alert")).textContent).toContain(NOT_YET);
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("on a network failure says the data is not available yet, with a retry", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<Widget role="test" />);
    expect((await screen.findByRole("alert")).textContent).toContain(NOT_YET);
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("on another server error names what failed and retries", async () => {
    const fetchMock = answer(500, {});
    vi.stubGlobal("fetch", fetchMock);
    render(<Widget role="test" />);
    expect((await screen.findByRole("alert")).textContent).toContain(`Could not load ${what}`);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByRole("alert");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
