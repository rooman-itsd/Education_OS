import type { DashboardWidget } from "@eos/ui-kit";
import { ApprovalQueue } from "./ApprovalQueue";
import { EnabledModules } from "./EnabledModules";
import { OrganisationsByStatus } from "./OrganisationsByStatus";
import { RecentRegistrations } from "./RecentRegistrations";
import "./widgets.css";

/**
 * Dashboard widgets exported by tenancy.
 * Ids are "tenancy.<widget>". The role layouts in platform/identity/config/dashboards/*.yaml refer to
 * them by id (org-admin.yaml, super-admin.yaml). A widget imports only from this service and packages/, and
 * fetches data through this service's API client in ../api. The super admin's widgets need
 * platform:organisations:read, which only the super admin holds.
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
  {
    id: "tenancy.approval-queue",
    title: "Approval queue",
    permission: "platform:organisations:read",
    size: "2x1",
    kind: "list",
    subtitle: "Registrations and package changes, oldest first",
    component: ApprovalQueue,
  },
  {
    id: "tenancy.organisations-by-status",
    title: "Organisations by status",
    permission: "platform:organisations:read",
    size: "1x1",
    kind: "list",
    component: OrganisationsByStatus,
  },
  {
    id: "tenancy.recent-registrations",
    title: "Recent registrations",
    permission: "platform:organisations:read",
    size: "1x1",
    kind: "list",
    subtitle: "The five newest organisations",
    component: RecentRegistrations,
  },
];
