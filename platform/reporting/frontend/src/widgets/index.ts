import type { DashboardWidget } from "@eos/ui-kit";
import { AttendanceAndResultsByDepartment } from "./AttendanceAndResultsByDepartment";
import { DepartmentReports } from "./DepartmentReports";

/**
 * Dashboard widgets exported by reporting.
 * Ids are "reporting.<widget>". The role layouts in platform/identity/config/dashboards/*.yaml refer to
 * them by id (department-admin.yaml and management.yaml).
 */
export const widgets: DashboardWidget[] = [
  {
    id: "reporting.department-reports",
    title: "Department Reports",
    permission: "reporting:report:read",
    size: "2x1",
    kind: "list",
    subtitle: "Department metrics and recent generated reports",
    component: DepartmentReports,
  },
  {
    id: "reporting.attendance-and-results-by-department",
    title: "Attendance & Results by Department",
    permission: "reporting:report:read",
    size: "2x1",
    kind: "list",
    subtitle: "Cross-department attendance and academic results summary",
    component: AttendanceAndResultsByDepartment,
  },
];

