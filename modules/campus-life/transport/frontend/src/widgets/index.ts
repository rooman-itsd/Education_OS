import type { DashboardWidget } from "@eos/ui-kit";
import { NoticesWidget } from "./NoticesWidget";

/**
 * Dashboard widgets exported by transport.
 * Ids are "transport.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "transport.notices",
    title: "Transport notices",
    permission: "transport:self:read",
    size: "2x1",
    kind: "list",
    subtitle: "Your routes and all routes",
    component: NoticesWidget,
  },
];
