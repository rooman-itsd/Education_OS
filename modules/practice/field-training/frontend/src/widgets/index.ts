import type { DashboardWidget } from "@eos/ui-kit";
import { ActivePlacementsWidget } from "./ActivePlacementsWidget";
import { HoursLoggedWidget } from "./HoursLoggedWidget";
import { MyPlacementWidget } from "./MyPlacementWidget";
import { PlacementsOpenWidget } from "./PlacementsOpenWidget";
import { TraineesToAssessWidget } from "./TraineesToAssessWidget";

/**
 * Dashboard widgets exported by field-training.
 * Ids are "field-training.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 * Each declares the one key that backs the endpoint it calls (contracts/openapi.yaml).
 */
export const widgets: DashboardWidget[] = [
  {
    id: "field-training.my-placement",
    title: "My placement",
    permission: "field-training:self:read",
    size: "2x1",
    kind: "list",
    subtitle: "Current, upcoming and applied",
    component: MyPlacementWidget,
  },
  {
    id: "field-training.hours-logged",
    title: "Hours logged",
    permission: "field-training:self:read",
    size: "1x1",
    kind: "panel",
    subtitle: "Verified against the requirement",
    component: HoursLoggedWidget,
  },
  {
    id: "field-training.trainees-to-assess",
    title: "Trainees to assess",
    permission: "field-training:supervision:read",
    size: "2x1",
    kind: "list",
    subtitle: "Entries to verify and final assessments due",
    component: TraineesToAssessWidget,
  },
  {
    id: "field-training.placements-open",
    title: "Open placements",
    permission: "field-training:opening:read",
    size: "2x1",
    kind: "list",
    subtitle: "Openings with seats left",
    component: PlacementsOpenWidget,
  },
  {
    id: "field-training.active-placements",
    title: "Active placements",
    permission: "field-training:placement:read",
    size: "2x1",
    kind: "list",
    subtitle: "Under way, with verified hours",
    component: ActivePlacementsWidget,
  },
];
