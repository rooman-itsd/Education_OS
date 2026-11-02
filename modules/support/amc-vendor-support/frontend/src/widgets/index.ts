import type { DashboardWidget } from "@eos/ui-kit";
import { ContractsExpiringWidget } from "./ContractsExpiringWidget";

/**
 * Dashboard widgets exported by amc-vendor-support.
 * Ids are "amc-vendor-support.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "amc-vendor-support.contracts-expiring",
    title: "AMC contracts expiring",
    permission: "amc-vendor-support:contract:read",
    size: "1x1",
    kind: "list",
    subtitle: "Ending soon or expired",
    component: ContractsExpiringWidget,
  },
];
