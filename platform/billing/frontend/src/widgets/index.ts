import type { DashboardWidget } from "@eos/ui-kit";
import { Invoices } from "./Invoices";
import { PlanAndTrial } from "./PlanAndTrial";
import { UsageVsLimits } from "./UsageVsLimits";
import "./widgets.css";

/**
 * Dashboard widgets exported by billing.
 * Ids are "billing.<widget>". The role layouts in platform/identity/config/dashboards/*.yaml refer to
 * them by id (org-admin.yaml). A widget imports only from this service and packages/, and fetches data
 * through this service's API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "billing.plan-and-trial",
    title: "Plan and trial",
    permission: "billing:subscription:read",
    size: "2x1",
    kind: "panel",
    subtitle: "Your subscription and the plans you can switch to",
    component: PlanAndTrial,
  },
  {
    id: "billing.usage-vs-limits",
    title: "Usage against limits",
    permission: "billing:subscription:read",
    size: "1x1",
    kind: "panel",
    component: UsageVsLimits,
  },
  {
    id: "billing.invoices",
    title: "Invoices",
    permission: "billing:subscription:read",
    size: "1x1",
    kind: "list",
    subtitle: "One per paid period",
    component: Invoices,
  },
];
