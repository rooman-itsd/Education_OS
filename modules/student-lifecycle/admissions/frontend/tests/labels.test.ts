import { describe, expect, it } from "vitest";
import { describeFailure, AdmissionsApiError } from "../src/api/client";
import { percent, statusLabel, statusTone, waitingFor } from "../src/components/labels";

describe("labels", () => {
  it("names every contract status in words", () => {
    const statuses = ["submitted", "under_review", "eligible", "ineligible", "offered", "accepted", "declined", "rejected", "withdrawn"] as const;
    for (const s of statuses) expect(statusLabel(s)).not.toBe(s);
    expect(statusTone("accepted")).toBe("success");
    expect(statusTone("rejected")).toBe("danger");
  });

  it("says how long something has waited", () => {
    const now = new Date("2026-10-28T12:00:00Z");
    expect(waitingFor("2026-10-28T11:59:30Z", now)).toBe("1 minute");
    expect(waitingFor("2026-10-28T11:15:00Z", now)).toBe("45 minutes");
    expect(waitingFor("2026-10-28T09:00:00Z", now)).toBe("3 hours");
    expect(waitingFor("2026-10-27T11:00:00Z", now)).toBe("1 day");
    expect(waitingFor("2026-10-20T12:00:00Z", now)).toBe("8 days");
  });

  it("rounds shares to one decimal and survives zero", () => {
    expect(percent(1, 3)).toBe(33.3);
    expect(percent(0, 0)).toBe(0);
  });

  it("words failures the way other modules do", () => {
    expect(describeFailure(new TypeError("network"), "x")).toEqual({ title: "Admissions data is not available yet.", retry: true });
    expect(describeFailure(new AdmissionsApiError(403, ""), "x").retry).toBe(false);
    expect(describeFailure(new AdmissionsApiError(500, ""), "x").title).toBe("Could not load x");
  });
});
