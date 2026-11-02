import type { DashboardWidget } from "@eos/ui-kit";
import { MyProgressWidget } from "./MyProgressWidget";

/**
 * Dashboard widgets exported by skill-progress.
 * Ids are "skill-progress.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "skill-progress.my-progress",
    title: "My progress",
    permission: "skill-progress:progress:read",
    size: "1x1",
    kind: "list",
    subtitle: "Your latest level on each skill",
    component: MyProgressWidget,
  },
];
