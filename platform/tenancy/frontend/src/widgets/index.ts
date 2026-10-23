import type { DashboardWidget } from "@eos/ui-kit";
import { EnabledModules } from "./EnabledModules";

/**
 * Dashboard widgets exported by tenancy.
 * Ids are "tenancy.<widget>". The role layouts in platform/identity/config/dashboards/*.yaml refer to
 * them by id (org-admin.yaml). A widget imports only from this service and packages/, and fetches data
 * through this service's API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "tenancy.enabled-modules",
    title: "Enabled modules",
    permission: "tenancy:organisation:read",
    size: "2x1",
    kind: "list",
    subtitle: "What this organisation can use now",
    component: EnabledModules,
  },
];
