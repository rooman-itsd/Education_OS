import type { DashboardWidget } from "@eos/ui-kit";
import { CalendarWidget } from "./CalendarWidget";
import { DueWidget } from "./DueWidget";

/**
 * Dashboard widgets exported by regulatory-reports.
 * Ids are "regulatory-reports.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "regulatory-reports.due",
    title: "Regulatory filings due",
    permission: "regulatory-reports:stats:read",
    size: "1x1",
    kind: "list",
    subtitle: "Overdue and due soon",
    component: DueWidget,
  },
  {
    id: "regulatory-reports.compliance-calendar",
    title: "Compliance calendar",
    permission: "regulatory-reports:data:read",
    size: "1x1",
    kind: "list",
    subtitle: "Filings due in the next 90 days",
    component: CalendarWidget,
  },
];
