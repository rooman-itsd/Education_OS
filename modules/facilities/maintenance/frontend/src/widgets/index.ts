import type { DashboardWidget } from "@eos/ui-kit";
import { TicketsWidget } from "./TicketsWidget";

/**
 * Dashboard widgets exported by maintenance.
 * Ids are "maintenance.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "maintenance.tickets",
    title: "Maintenance tickets",
    permission: "maintenance:ticket:read-all",
    size: "1x1",
    kind: "list",
    subtitle: "Open, past SLA and urgent first",
    component: TicketsWidget,
  },
];
