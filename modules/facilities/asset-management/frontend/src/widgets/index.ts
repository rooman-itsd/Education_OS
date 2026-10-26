import type { DashboardWidget } from "@eos/ui-kit";
import { AuditDueWidget } from "./AuditDueWidget";

/**
 * Dashboard widgets exported by asset-management.
 * Ids are "asset-management.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "asset-management.audit-due",
    title: "Asset verification due",
    permission: "asset-management:asset:read",
    size: "1x1",
    kind: "list",
    subtitle: "Overdue first, and open audits",
    component: AuditDueWidget,
  },
];
