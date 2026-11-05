import type { DashboardWidget } from "@eos/ui-kit";
import { LoansWidget } from "./LoansWidget";

/**
 * Dashboard widgets exported by library.
 * Ids are "library.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "library.loans",
    title: "Library loans",
    permission: "library:self:read",
    size: "1x1",
    kind: "list",
    subtitle: "Due dates and overdue books",
    component: LoansWidget,
  },
];
