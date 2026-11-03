import type { DashboardWidget } from "@eos/ui-kit";
import { ApprovalsPending } from "./ApprovalsPending";

/**
 * Dashboard widgets exported by workflow.
 * Ids are "workflow.<widget>". The role layouts in platform/identity/config/dashboards/*.yaml refer to
 * them by id (department-admin.yaml). A widget imports only from this service and packages/, and fetches
 * data through this service's API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "workflow.approvals-pending",
    title: "Approvals pending",
    permission: "workflow:request:read",
    size: "2x1",
    kind: "list",
    subtitle: "Items waiting for your review and sign-off",
    component: ApprovalsPending,
  },
];

