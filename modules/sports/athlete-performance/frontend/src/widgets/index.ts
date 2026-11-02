import type { DashboardWidget } from "@eos/ui-kit";
import { BodyCompositionTrend } from "./BodyCompositionTrend";
import { FitnessClearances } from "./FitnessClearances";
import { PerformanceTrend } from "./PerformanceTrend";
import { SquadOverview } from "./SquadOverview";
import "./widgets.css";

/**
 * Dashboard widgets exported by athlete-performance.
 * Ids are "athlete-performance.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's API client in ../api.
 *
 * Endpoints and permissions per contracts/openapi.yaml and contracts/permissions.yaml. The coach layout's
 * athlete-performance.session-plan and the athlete layout's athlete-performance.training-schedule are not built
 * here: this module has no training plans or sessions (they belong to training-video-analysis).
 */
export const widgets: DashboardWidget[] = [
  {
    id: "athlete-performance.squad-overview",
    title: "Squad overview",
    permission: "athlete-performance:report:read",
    kind: "list",
    size: "2x1",
    subtitle: "Latest results, trend and clearance",
    component: SquadOverview,
  },
  {
    id: "athlete-performance.fitness-clearances",
    title: "Fitness clearances",
    permission: "athlete-performance:clearance:read",
    kind: "list",
    size: "2x1",
    subtitle: "Not cleared and lapsing first",
    component: FitnessClearances,
  },
  {
    id: "athlete-performance.performance-trend",
    title: "Performance trend",
    permission: "athlete-performance:result:read",
    kind: "panel",
    size: "2x1",
    subtitle: "Your results over time",
    component: PerformanceTrend,
  },
  {
    id: "athlete-performance.body-composition-trend",
    title: "Body composition trend",
    permission: "athlete-performance:report:read",
    kind: "panel",
    size: "2x1",
    component: BodyCompositionTrend,
  },
];
