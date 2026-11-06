import type { DashboardWidget } from "@eos/ui-kit";
import { ActionItemsWidget } from "./ActionItemsWidget";

/**
 * Dashboard widgets exported by iqac-accreditation.
 * Ids are "iqac-accreditation.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "iqac-accreditation.action-items",
    title: "IQAC action items",
    permission: "iqac-accreditation:stats:read",
    size: "1x1",
    kind: "list",
    subtitle: "Open, overdue and due soon",
    component: ActionItemsWidget,
  },
];
