import type { DashboardWidget } from "@eos/ui-kit";
import { JoiningsAndExits } from "./JoiningsAndExits";
import { LeaveRequests } from "./LeaveRequests";
import { PayrollRunStatus } from "./PayrollRunStatus";
import "./widgets.css";

/**
 * Dashboard widgets exported by hr-payroll.
 * Ids are "hr-payroll.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 *
 * Endpoints and permissions per contracts/openapi.yaml and contracts/permissions.yaml (issue #336).
 */
export const widgets: DashboardWidget[] = [
  {
    id: "hr-payroll.leave-requests",
    title: "Leave requests pending",
    permission: "hr-payroll:leave:approve",
    kind: "panel",
    size: "2x1",
    component: LeaveRequests,
  },
  {
    id: "hr-payroll.payroll-run-status",
    title: "Payroll this month",
    permission: "hr-payroll:payroll:read",
    kind: "panel",
    size: "1x1",
    component: PayrollRunStatus,
  },
  {
    id: "hr-payroll.joinings-and-exits",
    title: "Joinings and exits",
    permission: "hr-payroll:report:read",
    kind: "panel",
    size: "2x1",
    component: JoiningsAndExits,
  },
];
