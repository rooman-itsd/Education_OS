import type { DashboardWidget } from "@eos/ui-kit";
import { OpenByCommitteeWidget } from "./OpenByCommitteeWidget";
import { OpenWidget } from "./OpenWidget";

/**
 * Dashboard widgets exported by grievance.
 * Ids are "grievance.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "grievance.open-by-committee",
    title: "Open grievances by committee",
    permission: "grievance:stats:read",
    size: "1x1",
    kind: "list",
    subtitle: "Open and overdue cases per committee",
    component: OpenByCommitteeWidget,
  },
  {
    id: "grievance.open",
    title: "Open grievances",
    permission: "grievance:stats:read",
    size: "1x1",
    kind: "list",
    subtitle: "Open and overdue cases per track",
    component: OpenWidget,
  },
];
