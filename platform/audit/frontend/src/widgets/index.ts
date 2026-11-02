import type { DashboardWidget } from "@eos/ui-kit";
import { RecentActivity } from "./RecentActivity";
import { SuperAdminActions } from "./SuperAdminActions";

/**
 * Dashboard widgets exported by audit.
 * Ids are "audit.<widget>". The role layouts in platform/identity/config/dashboards/*.yaml refer to
 * them by id (org-admin.yaml, super-admin.yaml). A widget imports only from this service and packages/,
 * and fetches data through this service's API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "audit.recent-activity",
    title: "Recent activity",
    permission: "audit:record:read",
    size: "2x1",
    kind: "list",
    subtitle: "Who changed what, most recent first",
    component: RecentActivity,
  },
  {
    id: "audit.super-admin-actions",
    title: "Super Admin actions",
    permission: "platform:audit:read",
    size: "2x1",
    kind: "list",
    subtitle: "Platform and cross-organisation administrative actions",
    component: SuperAdminActions,
  },
];
