import type { DashboardWidget } from "@eos/ui-kit";
import { LowStockWidget } from "./LowStockWidget";
import { MyLoansWidget } from "./MyLoansWidget";
import { OverdueLoansWidget } from "./OverdueLoansWidget";

/**
 * Dashboard widgets exported by inventory-equipment.
 * Ids are "inventory-equipment.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "inventory-equipment.low-stock",
    title: "Low stock",
    permission: "inventory-equipment:stock:read",
    size: "1x1",
    kind: "list",
    subtitle: "At or below reorder level",
    component: LowStockWidget,
  },
  {
    id: "inventory-equipment.my-loans",
    title: "My loans",
    permission: "inventory-equipment:loan:read",
    size: "1x1",
    kind: "list",
    subtitle: "Equipment you have borrowed",
    component: MyLoansWidget,
  },
  {
    id: "inventory-equipment.overdue-loans",
    title: "Overdue loans",
    permission: "inventory-equipment:loan:read-all",
    size: "1x1",
    kind: "list",
    subtitle: "Not back by their due date",
    component: OverdueLoansWidget,
  },
];
