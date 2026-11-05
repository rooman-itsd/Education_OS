import { describe, expect, it } from "vitest";
import { widgets } from "../src/widgets";
import { ActivePlacementsWidget } from "../src/widgets/ActivePlacementsWidget";
import { HoursLoggedWidget } from "../src/widgets/HoursLoggedWidget";
import { MyPlacementWidget } from "../src/widgets/MyPlacementWidget";
import { PlacementsOpenWidget } from "../src/widgets/PlacementsOpenWidget";
import { TraineesToAssessWidget } from "../src/widgets/TraineesToAssessWidget";

describe("field-training widgets", () => {
  it("exports the five widgets the layouts name, each with the one key backing its endpoint", () => {
    expect(widgets.map((w) => [w.id, w.permission, w.size, w.kind, w.component])).toEqual([
      ["field-training.my-placement", "field-training:self:read", "2x1", "list", MyPlacementWidget],
      ["field-training.hours-logged", "field-training:self:read", "1x1", "panel", HoursLoggedWidget],
      ["field-training.trainees-to-assess", "field-training:supervision:read", "2x1", "list", TraineesToAssessWidget],
      ["field-training.placements-open", "field-training:opening:read", "2x1", "list", PlacementsOpenWidget],
      ["field-training.active-placements", "field-training:placement:read", "2x1", "list", ActivePlacementsWidget],
    ]);
    expect(widgets.every((w) => w.title.length > 0)).toBe(true);
  });
});
