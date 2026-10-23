import type { DashboardWidget } from "@eos/ui-kit";
import { UsersAndRoles } from "./UsersAndRoles";

/**
 * Dashboard widgets exported by identity.
 * Ids are "identity.<widget>". The role layouts in platform/identity/config/dashboards/*.yaml refer to
 * them by id (org-admin.yaml). A widget imports only from this service and packages/, and fetches data
 * through this service's API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "identity.users-and-roles",
    title: "Users and roles",
    permission: "identity:user:read",
    size: "1x1",
    kind: "list",
    component: UsersAndRoles,
  },
];
