import type { DashboardWidget } from "@eos/ui-kit";
import { TopArticlesWidget } from "./TopArticlesWidget";

/**
 * Dashboard widgets exported by knowledge-base.
 * Ids are "knowledge-base.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "knowledge-base.top-articles",
    title: "Top articles",
    permission: "knowledge-base:stats:read",
    size: "1x1",
    kind: "list",
    subtitle: "Most read in the last 30 days",
    component: TopArticlesWidget,
  },
];
