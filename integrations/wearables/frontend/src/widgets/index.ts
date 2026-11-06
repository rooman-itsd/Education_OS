import type { DashboardWidget } from "@eos/ui-kit";
import { Alerts } from "./Alerts";
import "./widgets.css";

/**
 * Dashboard widgets exported by wearables.
 * Ids are "wearables.<widget>". The role layouts in platform/identity/config/dashboards/*.yaml refer to them by id
 * (coach.yaml lists wearables.alerts). A widget imports only from this integration and packages/, and fetches data through
 * this integration's API client in ../api.
 *
 * Endpoints and permissions per contracts/openapi.yaml and contracts/permissions.yaml.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "wearables.alerts",
    title: "Device alerts",
    permission: "wearables:alert:read",
    kind: "list",
    size: "1x1",
    component: Alerts,
  },
];
