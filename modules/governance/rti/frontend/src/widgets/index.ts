import type { DashboardWidget } from "@eos/ui-kit";
import { NearingDeadlineWidget } from "./NearingDeadlineWidget";

/**
 * Dashboard widgets exported by rti.
 * Ids are "rti.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "rti.nearing-deadline",
    title: "RTI requests nearing a deadline",
    permission: "rti:stats:read",
    size: "1x1",
    kind: "list",
    subtitle: "Overdue and due soon",
    component: NearingDeadlineWidget,
  },
];
