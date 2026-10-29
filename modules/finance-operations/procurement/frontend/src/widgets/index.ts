import type { DashboardWidget } from "@eos/ui-kit";
import { PurchaseOrdersPending } from "./PurchaseOrdersPending";
import "./widgets.css";

/**
 * Dashboard widgets exported by procurement.
 * Ids are "procurement.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 *
 * Endpoints and permissions per contracts/openapi.yaml and contracts/permissions.yaml.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "procurement.purchase-orders-pending",
    title: "Purchase orders pending",
    permission: "procurement:report:read",
    kind: "panel",
    size: "2x1",
    component: PurchaseOrdersPending,
  },
];
