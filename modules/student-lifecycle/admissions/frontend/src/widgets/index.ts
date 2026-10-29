import type { DashboardWidget } from "@eos/ui-kit";
import { ApplicationStatusWidget } from "./ApplicationStatusWidget";
import { FunnelWidget } from "./FunnelWidget";
import { PendingDocumentsWidget } from "./PendingDocumentsWidget";

/**
 * Dashboard widgets exported by admissions.
 * Ids are "admissions.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "admissions.application-status",
    title: "Latest applications",
    permission: "admissions:application:read",
    size: "1x1",
    kind: "list",
    subtitle: "Newest first, with their status",
    component: ApplicationStatusWidget,
  },
  {
    id: "admissions.funnel",
    title: "Admissions funnel",
    permission: "admissions:report:read",
    size: "2x1",
    kind: "chart",
    subtitle: "Applied, eligible, offered, accepted",
    component: FunnelWidget,
  },
  {
    id: "admissions.pending-documents",
    title: "Documents to verify",
    permission: "admissions:document:verify",
    size: "1x1",
    kind: "list",
    subtitle: "Longest waiting first",
    component: PendingDocumentsWidget,
  },
];
