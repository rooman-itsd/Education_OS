import type { DashboardWidget } from "@eos/ui-kit";
import { Reconciliation } from "./Reconciliation";
import "./widgets.css";

/**
 * Dashboard widgets exported by payment-sbiepay.
 * Ids are "payment-sbiepay.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this integration and packages/, and fetches data
 * through this integration's API client in ../api.
 *
 * Endpoints and permissions per contracts/openapi.yaml and contracts/permissions.yaml.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "payment-sbiepay.reconciliation",
    title: "Online payments reconciliation",
    permission: "payment-sbiepay:payment:read",
    kind: "panel",
    size: "1x1",
    component: Reconciliation,
  },
];
