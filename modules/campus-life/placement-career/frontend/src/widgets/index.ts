import type { DashboardWidget } from "@eos/ui-kit";
import { Drives } from "./Drives";
import { Openings } from "./Openings";
import { OpeningsSummary } from "./OpeningsSummary";
import "./widgets.css";

/**
 * Dashboard widgets exported by placement-career.
 * Ids are "placement-career.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's API client in ../api.
 *
 * Each widget declares one permission and calls one endpoint (owner decision P8 on #337,
 * contracts/openapi.yaml and contracts/permissions.yaml):
 * - openings: learner layouts (they extend `student`), placement-career:self:read, GET /me/openings
 * - openings-summary: placement-officer, industry-coordinator, practicum-coordinator, industry-liaison,
 *   placement-career:report:read, GET /reports/openings-summary
 * - drives: placement-officer, placement-career:report:read, GET /reports/drives-upcoming
 */
export const widgets: DashboardWidget[] = [
  {
    id: "placement-career.openings",
    title: "Job openings",
    permission: "placement-career:self:read",
    kind: "panel",
    size: "2x1",
    component: Openings,
  },
  {
    id: "placement-career.openings-summary",
    title: "Placement openings",
    permission: "placement-career:report:read",
    kind: "panel",
    size: "2x1",
    component: OpeningsSummary,
  },
  {
    id: "placement-career.drives",
    title: "Upcoming drives",
    permission: "placement-career:report:read",
    kind: "panel",
    size: "1x1",
    component: Drives,
  },
];
